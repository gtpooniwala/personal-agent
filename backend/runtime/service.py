"""Runtime coordinator for asynchronous runs.

Pipeline overview:
1. FastAPI accepts a request and hands it to ``RuntimeService``.
2. ``RuntimeService`` performs run bookkeeping, leases, retries, and events.
3. ``OrchestrationExecutionPlane`` moves the blocking orchestrator attempt to
   a bounded worker pool.
4. ``CoreOrchestrator`` performs the heavy LLM/tool workflow inside that pool.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

from backend.observability import (
    increment_counter,
    observe_operation,
    push_context,
    update_observation,
)
from backend.runtime.contracts import (
    RUN_TERMINAL_STATUSES,
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
    utcnow,
)
from backend.runtime.orchestration import (
    OrchestrationAttempt,
    OrchestrationExecutionPlane,
)
from backend.runtime.blocking import offload_blocking_call
from backend.runtime.store import RunNotFoundError, RunStore

logger = logging.getLogger(__name__)

GENERIC_RUNTIME_FAILURE_MESSAGE = "Run failed due to an internal error."
SESSION_BUSY_MESSAGE = "Another operation is already running in this conversation."
MAX_RETRY_ATTEMPTS = 3
LEASE_TTL_SECONDS = 300
LEASE_RENEWAL_INTERVAL_SECONDS = LEASE_TTL_SECONDS // 2


@dataclass(frozen=True)
class RunExecution:
    """Control-plane input passed from submission into runtime execution."""

    run_id: str
    conversation_id: str
    message: str
    selected_documents: Sequence[str]


class RuntimeService:
    """Coordinates run lifecycle while delegating heavy work to the execution plane."""

    def __init__(
        self,
        *,
        orchestrator,
        run_store: RunStore,
        orchestrator_factory=None,
        orchestration_executor=None,
        orchestration_max_workers: int = 4,
    ):
        self._orchestrator = orchestrator
        self._run_store = run_store
        self._background_tasks: set[asyncio.Task] = set()
        self._execution_plane = OrchestrationExecutionPlane(
            orchestrator=orchestrator,
            orchestrator_factory=orchestrator_factory,
            orchestration_executor=orchestration_executor,
            orchestration_max_workers=orchestration_max_workers,
        )

    async def submit_run(self, request) -> Dict[str, str]:
        """Create a run record and hand execution to the runtime coordinator."""
        conversation_id = await self._ensure_conversation_id(request.conversation_id)
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
            run = await self._create_run_record(
                conversation_id=conversation_id,
                message=request.message,
                selected_documents=selected_documents,
            )
            await self._append_run_event(
                run_id=run.run_id,
                event_type=RUN_EVENT_QUEUED,
                status=RUN_STATUS_QUEUED,
                message="Run accepted and queued",
            )
            increment_counter("runtime.runs.queued_total")
            update_observation(
                observation,
                output={"run_id": run.run_id, "status": run.status},
            )

        execution = RunExecution(
            run_id=run.run_id,
            conversation_id=conversation_id,
            message=request.message,
            selected_documents=tuple(selected_documents),
        )

        # The API returns immediately; the runtime continues coordination in the background.
        self._track_background_task(asyncio.create_task(self._execute_run(execution)))

        return {
            "run_id": run.run_id,
            "status": run.status,
            "conversation_id": conversation_id,
        }

    async def _ensure_conversation_id(self, conversation_id: Optional[str]) -> str:
        """Keep submission bookkeeping on the event loop and offload DB-backed creation."""
        if conversation_id:
            return conversation_id

        return await self._execution_plane.run_orchestrator_method(
            self._orchestrator,
            "create_conversation",
        )

    async def get_run_status(self, run_id: str) -> Dict[str, object]:
        run = await self._get_run_record(run_id)
        return run.to_status_payload()

    async def get_run_events(
        self, *, run_id: str, after: Optional[str], limit: int
    ) -> Dict[str, object]:
        events, next_after, has_more = await self._list_run_events(
            run_id=run_id,
            after=after,
            limit=limit,
        )
        return {
            "run_id": run_id,
            "events": [event.to_payload() for event in events],
            "next_after": next_after,
            "has_more": has_more,
        }

    async def shutdown(self) -> None:
        await self._execution_plane.shutdown()

    def _track_background_task(self, task: asyncio.Task) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _execute_run(self, execution: RunExecution) -> None:
        """Runtime coordination stays on the event loop; heavy attempts do not."""
        lease_key = f"session:{execution.conversation_id}"
        owner_id = execution.run_id
        renewal_task: Optional[asyncio.Task] = None

        with observe_operation(
            name="runtime.execute_run",
            counter_prefix="runtime.execute_run",
            as_type="chain",
            conversation_id=execution.conversation_id,
            metadata={"component": "runtime", "run_id": execution.run_id},
        ) as observation:
            try:
                lease = await self._acquire_lease_with_retry(
                    lease_key,
                    owner_id,
                    max_attempts=3,
                )
                if lease is None:
                    await self._mark_run_failed(
                        run_id=execution.run_id,
                        error_message=SESSION_BUSY_MESSAGE,
                    )
                    update_observation(
                        observation,
                        output={"status": RUN_STATUS_FAILED, "run_id": execution.run_id},
                        status_message=SESSION_BUSY_MESSAGE,
                    )
                    return

                renewal_task = asyncio.create_task(
                    self._renew_lease_periodically(
                        lease_key,
                        owner_id,
                        LEASE_RENEWAL_INTERVAL_SECONDS,
                    )
                )

                for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
                    try:
                        await self._execute_attempt(execution, attempt)
                        break
                    except RunNotFoundError:
                        raise
                    except Exception as exc:
                        if attempt == MAX_RETRY_ATTEMPTS:
                            logger.exception(
                                "Run execution failed after max retries",
                                extra={
                                    "event": "runtime.run_crash",
                                    "run_id": execution.run_id,
                                    "attempt": attempt,
                                },
                            )
                            raise

                        logger.warning(
                            "Attempt failed, retrying",
                            extra={
                                "event": "runtime.run_retry",
                                "run_id": execution.run_id,
                                "attempt": attempt,
                            },
                            exc_info=True,
                        )
                        current_run = await self._get_run_record(execution.run_id)
                        if current_run.status not in RUN_TERMINAL_STATUSES:
                            await self._update_run_record(
                                run_id=execution.run_id,
                                status=RUN_STATUS_RETRYING,
                            )
                        await self._append_run_event(
                            run_id=execution.run_id,
                            event_type=RUN_EVENT_RETRYING,
                            status=RUN_STATUS_RETRYING,
                            message=f"Retrying after error: {type(exc).__name__}",
                        )

                try:
                    final_run = await self._get_run_record(execution.run_id)
                    update_observation(
                        observation,
                        output={"status": final_run.status, "run_id": execution.run_id},
                        status_message=final_run.error
                        if final_run.status == RUN_STATUS_FAILED
                        else None,
                    )
                except RunNotFoundError:
                    logger.warning(
                        "Run disappeared before updating final observation",
                        extra={"event": "runtime.run_missing", "run_id": execution.run_id},
                    )

            except RunNotFoundError:
                logger.warning(
                    "Run disappeared during execution",
                    extra={"event": "runtime.run_missing", "run_id": execution.run_id},
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected run execution failure",
                    extra={"event": "runtime.run_crash", "run_id": execution.run_id},
                )
                try:
                    await self._mark_run_failed(
                        run_id=execution.run_id,
                        error_message=GENERIC_RUNTIME_FAILURE_MESSAGE,
                    )
                except RunNotFoundError:
                    logger.warning(
                        "Run disappeared while storing failure",
                        extra={"event": "runtime.run_missing", "run_id": execution.run_id},
                    )
                update_observation(
                    observation,
                    output={"status": RUN_STATUS_FAILED, "run_id": execution.run_id},
                    status_message=GENERIC_RUNTIME_FAILURE_MESSAGE,
                    metadata={"error_type": type(exc).__name__},
                )
            finally:
                if renewal_task is not None:
                    renewal_task.cancel()
                    try:
                        await renewal_task
                    except asyncio.CancelledError:
                        pass

                try:
                    await self._release_lease(lease_key, owner_id)
                except Exception:
                    logger.exception(
                        "Failed to release lease",
                        extra={
                            "event": "runtime.lease_release_failed",
                            "lease_key": lease_key,
                        },
                    )

    async def _execute_attempt(self, execution: RunExecution, attempt: int) -> None:
        """A single orchestration attempt: bookkeeping here, heavy work in the pool."""
        update_run_kwargs = {
            "run_id": execution.run_id,
            "status": RUN_STATUS_RUNNING,
            "attempt_count": attempt,
            "completed_at": None,
            "error": None,
            "result": None,
        }
        if attempt == 1:
            update_run_kwargs["started_at"] = utcnow()

        await self._update_run_record(**update_run_kwargs)
        await self._append_run_event(
            run_id=execution.run_id,
            event_type=RUN_EVENT_STARTED,
            status=RUN_STATUS_RUNNING,
            message="Run started" if attempt == 1 else f"Run attempt {attempt} started",
        )
        if attempt == 1:
            increment_counter("runtime.runs.running_total")

        attempt_orchestrator = self._execution_plane.create_orchestrator()
        attempt_input = OrchestrationAttempt(
            user_request=execution.message,
            conversation_id=execution.conversation_id,
            selected_documents=execution.selected_documents,
            spawn_background_tasks=False,
        )

        with push_context(conversation_id=execution.conversation_id):
            result = await self._execution_plane.run_attempt(
                orchestrator=attempt_orchestrator,
                attempt=attempt_input,
            )

        if result.get("error", False):
            error_message = result.get("response") or "Run failed"
            await self._mark_run_failed(
                run_id=execution.run_id,
                error_message=error_message,
            )
            return

        for action in result.get("orchestration_actions") or []:
            tool_name = action.get("tool") or "unknown"
            await self._append_run_event(
                run_id=execution.run_id,
                event_type=RUN_EVENT_TOOL_RESULT,
                status=RUN_STATUS_RUNNING,
                message="Tool action completed",
                tool=tool_name,
            )

        response = result.get("response") or ""
        await self._update_run_record(
            run_id=execution.run_id,
            status=RUN_STATUS_SUCCEEDED,
            result=response,
            error=None,
            completed_at=utcnow(),
        )
        await self._append_run_event(
            run_id=execution.run_id,
            event_type=RUN_EVENT_SUCCEEDED,
            status=RUN_STATUS_SUCCEEDED,
            message="Run completed successfully",
        )
        increment_counter("runtime.runs.succeeded_total")

        self._track_background_task(
            asyncio.create_task(self._maybe_generate_title(execution.conversation_id))
        )
        self._track_background_task(
            asyncio.create_task(
                self._maybe_summarise_in_background(execution.conversation_id)
            )
        )

    async def _mark_run_failed(self, *, run_id: str, error_message: str) -> None:
        await self._update_run_record(
            run_id=run_id,
            status=RUN_STATUS_FAILED,
            error=error_message,
            result=None,
            completed_at=utcnow(),
        )
        await self._append_run_event(
            run_id=run_id,
            event_type=RUN_EVENT_FAILED,
            status=RUN_STATUS_FAILED,
            message=error_message,
        )
        increment_counter("runtime.runs.failed_total")

    async def _acquire_lease_with_retry(
        self,
        lease_key: str,
        owner_id: str,
        max_attempts: int = 3,
    ) -> Optional[Dict]:
        """Try to acquire a conversation lease with exponential backoff."""
        for attempt in range(max_attempts):
            try:
                lease = await self._acquire_lease(
                    lease_key,
                    owner_id,
                    LEASE_TTL_SECONDS,
                )
                if lease is not None:
                    return lease
            except Exception:
                logger.warning(
                    "Exception acquiring lease",
                    extra={
                        "event": "runtime.lease_acquire_failed",
                        "lease_key": lease_key,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    },
                    exc_info=True,
                )
                if attempt == max_attempts - 1:
                    raise

            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (2**attempt))

        return None

    async def _renew_lease_periodically(
        self,
        lease_key: str,
        owner_id: str,
        interval_seconds: int,
    ) -> None:
        """Keep the conversation lease alive while the run is active."""
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                result = await self._renew_lease(
                    lease_key,
                    owner_id,
                    LEASE_TTL_SECONDS,
                )
                if result is None:
                    logger.warning(
                        "Failed to renew lease",
                        extra={
                            "event": "runtime.lease_renew_failed",
                            "lease_key": lease_key,
                        },
                    )
                    break
        except asyncio.CancelledError:
            pass

    async def _maybe_generate_title(self, conversation_id: str) -> None:
        """Title generation stays on the shared orchestrator used by the app layer."""
        generate_title = getattr(self._orchestrator, "generate_conversation_title", None)
        if generate_title is None:
            return

        try:
            await generate_title(conversation_id)
        except Exception:
            logger.exception(
                "Background title generation failed",
                extra={
                    "event": "runtime.title_generation_failed",
                    "conversation_id": conversation_id,
                },
            )

    async def _maybe_summarise_in_background(self, conversation_id: str) -> None:
        """Run follow-up summarisation on the execution plane, not the event loop."""
        try:
            orchestrator = self._execution_plane.create_orchestrator()
            await self._execution_plane.run_orchestrator_follow_up(
                orchestrator,
                "maybe_summarise_conversation",
                conversation_id,
            )
        except Exception:
            logger.exception(
                "Background summarisation failed",
                extra={
                    "event": "runtime.summarisation_failed",
                    "conversation_id": conversation_id,
                },
            )

    async def _create_run_record(
        self,
        *,
        conversation_id: str,
        message: str,
        selected_documents: Sequence[str],
    ):
        return await offload_blocking_call(
            self._run_store.create_run,
            conversation_id=conversation_id,
            message=message,
            selected_documents=selected_documents,
        )

    async def _get_run_record(self, run_id: str):
        return await offload_blocking_call(self._run_store.get_run, run_id)

    async def _update_run_record(self, **kwargs):
        return await offload_blocking_call(self._run_store.update_run, **kwargs)

    async def _append_run_event(self, **kwargs):
        return await offload_blocking_call(self._run_store.append_event, **kwargs)

    async def _list_run_events(
        self,
        *,
        run_id: str,
        after: Optional[str],
        limit: int,
    ):
        return await offload_blocking_call(
            self._run_store.list_events,
            run_id=run_id,
            after=after,
            limit=limit,
        )

    @staticmethod
    def _db_ops():
        from backend.database.operations import db_ops

        return db_ops

    async def _acquire_lease(
        self,
        lease_key: str,
        owner_id: str,
        ttl_seconds: int,
    ) -> Optional[Dict]:
        return await offload_blocking_call(
            self._db_ops().acquire_lease,
            lease_key,
            owner_id,
            ttl_seconds,
        )

    async def _renew_lease(
        self,
        lease_key: str,
        owner_id: str,
        ttl_seconds: int,
    ) -> Optional[Dict]:
        return await offload_blocking_call(
            self._db_ops().renew_lease,
            lease_key,
            owner_id,
            ttl_seconds,
        )

    async def _release_lease(self, lease_key: str, owner_id: str) -> None:
        await offload_blocking_call(self._db_ops().release_lease, lease_key, owner_id)
