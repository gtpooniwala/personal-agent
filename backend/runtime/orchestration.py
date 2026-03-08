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
import threading
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
        if (
            orchestrator_factory is None
            and orchestration_executor is None
            and orchestration_max_workers > 1
        ):
            raise ValueError(
                "orchestrator_factory is required when orchestration_max_workers > 1"
            )
        self._fallback_orchestrator = orchestrator
        self._orchestrator_factory = orchestrator_factory
        self._owns_executor = orchestration_executor is None
        self._orchestration_max_workers = orchestration_max_workers
        self._executor_lock = threading.Lock()
        self._executor = orchestration_executor or self._new_executor()

    async def shutdown(self) -> None:
        if not self._owns_executor:
            return

        # The app reuses a module-level RuntimeService across repeated FastAPI
        # lifespan starts in tests. Clearing the owned executor here lets the
        # next orchestration attempt recreate it cleanly.
        with self._executor_lock:
            executor = self._executor
            self._executor = None

        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=False)

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

    async def run_orchestrator_method(
        self,
        orchestrator,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run a lightweight orchestrator method in the bounded worker pool."""
        method = getattr(orchestrator, method_name)
        return await self._run_coroutine_in_executor(lambda: method(*args, **kwargs))

    async def _run_coroutine_in_executor(
        self,
        coroutine_factory: Callable[[], Any],
    ) -> Any:
        loop = asyncio.get_running_loop()
        context = contextvars.copy_context()
        executor = self._get_executor()

        def run_coroutine() -> Any:
            def runner() -> Any:
                result = coroutine_factory()
                if inspect.isawaitable(result):
                    return asyncio.run(result)
                return result

            return context.run(runner)

        return await loop.run_in_executor(executor, run_coroutine)

    def _get_executor(self) -> Executor:
        if not self._owns_executor:
            return self._executor

        with self._executor_lock:
            if self._executor is None:
                self._executor = self._new_executor()
            return self._executor

    def _new_executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=self._orchestration_max_workers,
            thread_name_prefix="orchestration",
        )
