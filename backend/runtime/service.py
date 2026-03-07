from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional
from backend.observability import increment_counter, observe_operation, push_context, update_observation
from backend.runtime.contracts import (
    RUN_EVENT_FAILED,
    RUN_EVENT_QUEUED,
    RUN_EVENT_RETRYING,
    RUN_EVENT_STARTED,
    RUN_EVENT_SUCCEEDED,
    RUN_EVENT_TOOL_RESULT,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RETRYING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SUCCEEDED,
)
from backend.runtime.store import RunNotFoundError, RunStore

logger = logging.getLogger(__name__)
GENERIC_RUNTIME_FAILURE_MESSAGE = "Run failed due to an internal error."
SESSION_BUSY_MESSAGE = "Another operation is already running in this conversation."
MAX_RETRY_ATTEMPTS = 3
LEASE_TTL_SECONDS = 300
LEASE_RENEWAL_INTERVAL_SECONDS = LEASE_TTL_SECONDS // 2


class RuntimeService:
    def __init__(self, *, orchestrator, run_store: RunStore):
        self._orchestrator = orchestrator
        self._run_store = run_store
        self._background_tasks: set[asyncio.Task] = set()

    async def submit_run(self, request) -> Dict[str, str]:
        conversation_id = request.conversation_id or self._orchestrator.create_conversation()
        selected_documents = request.selected_documents or []

        with observe_operation(
            name="runtime.submit_run",
            counter_prefix="runtime.submit_run",
            as_type="span",
            conversation_id=conversation_id,
            input_data={
                "message_chars": len(request.message or ""),
                "selected_documents_count": len(selected_documents),
            },
            metadata={"component": "runtime"},
        ) as observation:
            run = self._run_store.create_run(
                conversation_id=conversation_id,
                message=request.message,
                selected_documents=selected_documents,
            )
            self._run_store.append_event(
                run_id=run.run_id,
                event_type=RUN_EVENT_QUEUED,
                status=RUN_STATUS_QUEUED,
                message="Run accepted and queued",
            )
            increment_counter("runtime.runs.queued_total")
            update_observation(observation, output={"run_id": run.run_id, "status": run.status})

        # TODO(#16): Attach cancellation endpoint + worker-queue cancellation handling here.
        task = asyncio.create_task(
            self._execute_run(
                run_id=run.run_id,
                conversation_id=conversation_id,
                message=request.message,
                selected_documents=selected_documents,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return {
            "run_id": run.run_id,
            "status": run.status,
            "conversation_id": conversation_id,
        }

    async def get_run_status(self, run_id: str) -> Dict[str, Optional[str]]:
        run = self._run_store.get_run(run_id)
        return run.to_status_payload()

    async def get_run_events(self, *, run_id: str, after: Optional[str], limit: int) -> Dict[str, object]:
        events, next_after, has_more = self._run_store.list_events(run_id=run_id, after=after, limit=limit)
        return {
            "run_id": run_id,
            "events": [event.to_payload() for event in events],
            "next_after": next_after,
            "has_more": has_more,
        }

    async def _execute_run(
        self,
        *,
        run_id: str,
        conversation_id: str,
        message: str,
        selected_documents,
    ) -> None:
        lease_key = f"session:{conversation_id}"
        owner_id = run_id
        renewal_task: Optional[asyncio.Task] = None

        with observe_operation(
            name="runtime.execute_run",
            counter_prefix="runtime.execute_run",
            as_type="chain",
            conversation_id=conversation_id,
            metadata={"component": "runtime", "run_id": run_id},
        ) as observation:
            try:
                # 1. Acquire lease with retry backoff
                lease = await self._acquire_lease_with_retry(lease_key, owner_id, max_attempts=3)
                if lease is None:
                    # Another run is active for this conversation
                    self._run_store.update_run(
                        run_id=run_id,
                        status=RUN_STATUS_FAILED,
                        error=SESSION_BUSY_MESSAGE,
                        result=None,
                    )
                    self._run_store.append_event(
                        run_id=run_id,
                        event_type=RUN_EVENT_FAILED,
                        status=RUN_STATUS_FAILED,
                        message=SESSION_BUSY_MESSAGE,
                    )
                    increment_counter("runtime.runs.failed_total")
                    update_observation(
                        observation,
                        output={"status": RUN_STATUS_FAILED, "run_id": run_id},
                        status_message=SESSION_BUSY_MESSAGE,
                    )
                    return

                # 2. Start background lease renewal task
                renewal_task = asyncio.create_task(
                    self._renew_lease_periodically(lease_key, owner_id, LEASE_RENEWAL_INTERVAL_SECONDS)
                )

                # 3. Execute with retry cap
                for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
                    try:
                        await self._execute_attempt(run_id, conversation_id, message, selected_documents, attempt)
                        # Success path
                        break
                    except RunNotFoundError:
                        raise
                    except Exception as exc:
                        if attempt == MAX_RETRY_ATTEMPTS:
                            logger.exception("Run execution failed after max retries", extra={"event": "runtime.run_crash", "run_id": run_id, "attempt": attempt})
                            raise
                        else:
                            logger.warning(f"Attempt {attempt} failed, retrying...", extra={"event": "runtime.run_retry", "run_id": run_id, "attempt": attempt}, exc_info=True)
                            self._run_store.append_event(
                                run_id=run_id,
                                event_type=RUN_EVENT_RETRYING,
                                status=RUN_STATUS_RETRYING,
                                message=f"Retrying after error: {type(exc).__name__}",
                            )

            except RunNotFoundError:
                logger.warning("Run disappeared during execution", extra={"event": "runtime.run_missing", "run_id": run_id})
            except Exception as exc:
                logger.exception("Unexpected run execution failure", extra={"event": "runtime.run_crash", "run_id": run_id})
                try:
                    self._run_store.update_run(
                        run_id=run_id,
                        status=RUN_STATUS_FAILED,
                        error=GENERIC_RUNTIME_FAILURE_MESSAGE,
                        result=None,
                    )
                    self._run_store.append_event(
                        run_id=run_id,
                        event_type=RUN_EVENT_FAILED,
                        status=RUN_STATUS_FAILED,
                        message=GENERIC_RUNTIME_FAILURE_MESSAGE,
                    )
                except RunNotFoundError:
                    logger.warning("Run disappeared while storing failure", extra={"event": "runtime.run_missing", "run_id": run_id})
                increment_counter("runtime.runs.failed_total")
                update_observation(
                    observation,
                    output={"status": RUN_STATUS_FAILED, "run_id": run_id},
                    status_message=GENERIC_RUNTIME_FAILURE_MESSAGE,
                    metadata={"error_type": type(exc).__name__},
                )
            finally:
                # Release lease and cancel renewal task
                if renewal_task:
                    renewal_task.cancel()
                try:
                    from backend.database.operations import db_ops
                    db_ops.release_lease(lease_key, owner_id)
                except Exception:
                    logger.exception("Failed to release lease", extra={"event": "runtime.lease_release_failed", "lease_key": lease_key})

    async def _acquire_lease_with_retry(self, lease_key: str, owner_id: str, max_attempts: int = 3) -> Optional[Dict]:
        """Try to acquire a lease with exponential backoff."""
        from backend.database.operations import db_ops

        for attempt in range(max_attempts):
            lease = db_ops.acquire_lease(lease_key, owner_id, LEASE_TTL_SECONDS)
            if lease is not None:
                return lease
            if attempt < max_attempts - 1:
                # Exponential backoff: 0.5s, 1s, etc.
                await asyncio.sleep(0.5 * (2 ** attempt))
        return None

    async def _renew_lease_periodically(self, lease_key: str, owner_id: str, interval_seconds: int) -> None:
        """Periodically renew the lease."""
        from backend.database.operations import db_ops

        try:
            while True:
                await asyncio.sleep(interval_seconds)
                result = db_ops.renew_lease(lease_key, owner_id, LEASE_TTL_SECONDS)
                if result is None:
                    logger.warning("Failed to renew lease", extra={"event": "runtime.lease_renew_failed", "lease_key": lease_key})
                    break
        except asyncio.CancelledError:
            pass

    async def _execute_attempt(
        self,
        run_id: str,
        conversation_id: str,
        message: str,
        selected_documents,
        attempt: int,
    ) -> None:
        """Execute a single attempt of the run."""
        self._run_store.update_run(run_id=run_id, status=RUN_STATUS_RUNNING)
        self._run_store.append_event(
            run_id=run_id,
            event_type=RUN_EVENT_STARTED,
            status=RUN_STATUS_RUNNING,
            message="Run started",
        )
        increment_counter("runtime.runs.running_total")

        with push_context(conversation_id=conversation_id):
            result = await self._orchestrator.process_request(
                user_request=message,
                conversation_id=conversation_id,
                selected_documents=selected_documents,
            )

        if result.get("error", False):
            error_message = result.get("response") or "Run failed"
            self._run_store.update_run(
                run_id=run_id,
                status=RUN_STATUS_FAILED,
                error=error_message,
                result=None,
            )
            self._run_store.append_event(
                run_id=run_id,
                event_type=RUN_EVENT_FAILED,
                status=RUN_STATUS_FAILED,
                message=error_message,
            )
            increment_counter("runtime.runs.failed_total")
            return

        for action in result.get("orchestration_actions") or []:
            tool_name = action.get("tool") or "unknown"
            self._run_store.append_event(
                run_id=run_id,
                event_type=RUN_EVENT_TOOL_RESULT,
                status=RUN_STATUS_RUNNING,
                message="Tool action completed",
                tool=tool_name,
            )

        response = result.get("response") or ""
        self._run_store.update_run(
            run_id=run_id,
            status=RUN_STATUS_SUCCEEDED,
            result=response,
            error=None,
        )
        self._run_store.append_event(
            run_id=run_id,
            event_type=RUN_EVENT_SUCCEEDED,
            status=RUN_STATUS_SUCCEEDED,
            message="Run completed successfully",
        )
        increment_counter("runtime.runs.succeeded_total")
