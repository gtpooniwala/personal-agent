from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional
from backend.observability import increment_counter, observe_operation, push_context, update_observation
from backend.runtime.contracts import (
    RUN_EVENT_FAILED,
    RUN_EVENT_QUEUED,
    RUN_EVENT_STARTED,
    RUN_EVENT_SUCCEEDED,
    RUN_EVENT_TOOL_RESULT,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SUCCEEDED,
)
from backend.runtime.store import RunNotFoundError, RunStore

logger = logging.getLogger(__name__)


class RuntimeService:
    def __init__(self, *, orchestrator, run_store: RunStore):
        self._orchestrator = orchestrator
        self._run_store = run_store

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
        asyncio.create_task(
            self._execute_run(
                run_id=run.run_id,
                conversation_id=conversation_id,
                message=request.message,
                selected_documents=selected_documents,
            )
        )

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
        with observe_operation(
            name="runtime.execute_run",
            counter_prefix="runtime.execute_run",
            as_type="chain",
            conversation_id=conversation_id,
            metadata={"component": "runtime", "run_id": run_id},
        ) as observation:
            try:
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
                    self._run_store.update_run(run_id=run_id, status=RUN_STATUS_FAILED, error=error_message)
                    self._run_store.append_event(
                        run_id=run_id,
                        event_type=RUN_EVENT_FAILED,
                        status=RUN_STATUS_FAILED,
                        message=error_message,
                    )
                    increment_counter("runtime.runs.failed_total")
                    update_observation(
                        observation,
                        output={"status": RUN_STATUS_FAILED, "run_id": run_id},
                        status_message=error_message,
                    )
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
                self._run_store.update_run(run_id=run_id, status=RUN_STATUS_SUCCEEDED, result=response)
                self._run_store.append_event(
                    run_id=run_id,
                    event_type=RUN_EVENT_SUCCEEDED,
                    status=RUN_STATUS_SUCCEEDED,
                    message="Run completed successfully",
                )
                increment_counter("runtime.runs.succeeded_total")
                update_observation(observation, output={"status": RUN_STATUS_SUCCEEDED, "run_id": run_id})
            except RunNotFoundError:
                logger.warning("Run disappeared during execution", extra={"event": "runtime.run_missing", "run_id": run_id})
            except Exception as exc:
                logger.exception("Unexpected run execution failure", extra={"event": "runtime.run_crash", "run_id": run_id})
                try:
                    self._run_store.update_run(run_id=run_id, status=RUN_STATUS_FAILED, error=str(exc))
                    self._run_store.append_event(
                        run_id=run_id,
                        event_type=RUN_EVENT_FAILED,
                        status=RUN_STATUS_FAILED,
                        message=f"Unexpected runtime failure: {exc}",
                    )
                except RunNotFoundError:
                    logger.warning("Run disappeared while storing failure", extra={"event": "runtime.run_missing", "run_id": run_id})
                increment_counter("runtime.runs.failed_total")
                update_observation(
                    observation,
                    output={"status": RUN_STATUS_FAILED, "run_id": run_id},
                    status_message=str(exc),
                    metadata={"error_type": type(exc).__name__},
                )
