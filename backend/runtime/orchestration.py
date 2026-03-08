"""Execution-plane helpers used by the runtime coordinator.

Pipeline overview:
1. FastAPI accepts requests and hands them to RuntimeService.
2. RuntimeService performs lightweight coordination on the event loop.
3. This module moves full orchestration attempts onto worker threads.
4. CoreOrchestrator performs the heavy LLM/tool workflow inside those workers.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence


@dataclass(frozen=True)
class OrchestrationAttempt:
    """Execution-plane input for a single orchestrator attempt."""

    user_request: str
    conversation_id: str
    selected_documents: Sequence[str]
    spawn_background_tasks: bool = False


class OrchestrationExecutionPlane:
    """Runs blocking orchestrator work on a bounded worker pool."""

    def __init__(
        self,
        *,
        orchestrator,
        orchestrator_factory: Optional[Callable[[], Any]] = None,
        orchestration_executor: Optional[Executor] = None,
        orchestration_max_workers: int = 4,
    ):
        if orchestrator_factory is None and orchestration_max_workers > 1:
            raise ValueError(
                "orchestrator_factory is required when orchestration_max_workers > 1"
            )
        self._fallback_orchestrator = orchestrator
        self._orchestrator_factory = orchestrator_factory
        self._owns_executor = orchestration_executor is None
        self._executor = orchestration_executor or ThreadPoolExecutor(
            max_workers=orchestration_max_workers,
            thread_name_prefix="orchestration",
        )

    async def shutdown(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=False)

    def create_orchestrator(self):
        if self._orchestrator_factory is None:
            return self._fallback_orchestrator
        return self._orchestrator_factory()

    async def run_attempt(
        self,
        *,
        orchestrator,
        attempt: OrchestrationAttempt,
    ) -> Dict[str, Any]:
        process_request = orchestrator.process_request
        process_request_kwargs = {
            "user_request": attempt.user_request,
            "conversation_id": attempt.conversation_id,
            "selected_documents": attempt.selected_documents,
        }
        if "spawn_background_tasks" in inspect.signature(process_request).parameters:
            process_request_kwargs["spawn_background_tasks"] = (
                attempt.spawn_background_tasks
            )

        return await self._run_coroutine_in_executor(
            lambda: process_request(**process_request_kwargs)
        )

    async def run_orchestrator_follow_up(
        self,
        orchestrator,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        method = getattr(orchestrator, method_name, None)
        if method is None:
            return None
        return await self._run_coroutine_in_executor(lambda: method(*args, **kwargs))

    async def _run_coroutine_in_executor(
        self,
        coroutine_factory: Callable[[], Any],
    ) -> Any:
        loop = asyncio.get_running_loop()
        context = contextvars.copy_context()

        def run_coroutine() -> Any:
            def runner() -> Any:
                result = coroutine_factory()
                if inspect.isawaitable(result):
                    return asyncio.run(result)
                return result

            return context.run(runner)

        return await loop.run_in_executor(self._executor, run_coroutine)
