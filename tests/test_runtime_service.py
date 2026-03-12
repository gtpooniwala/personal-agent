import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import sys
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

RUNTIME_SERVICE_TESTS_AVAILABLE = True
RUNTIME_SERVICE_IMPORT_ERROR = ""

try:
    from backend.runtime.service import RuntimeService
    from backend.runtime.service import RunExecution
    from backend.runtime.store import InMemoryRunStore
except (ImportError, ModuleNotFoundError) as exc:
    RUNTIME_SERVICE_TESTS_AVAILABLE = False
    RUNTIME_SERVICE_IMPORT_ERROR = str(exc)


class RuntimeRequest:
    def __init__(self, message, conversation_id=None, selected_documents=None):
        self.message = message
        self.conversation_id = conversation_id
        self.selected_documents = selected_documents or []


class MockDbOps:
    def __init__(self):
        self._leases = {}

    def acquire_lease(self, key, owner_id, ttl_seconds):
        if key in self._leases:
            return None
        self._leases[key] = owner_id
        return {"key": key, "owner_id": owner_id}

    def release_lease(self, key, owner_id):
        if self._leases.get(key) == owner_id:
            del self._leases[key]

    def renew_lease(self, key, owner_id, ttl_seconds):
        if self._leases.get(key) == owner_id:
            return {"key": key, "owner_id": owner_id}
        return None

    def increment_runtime_counter(self, key, amount=1):
        return 0


class BaseTestOrchestrator:
    def create_conversation(self):
        return "conv-generated"

    async def generate_conversation_title(self, conversation_id):
        return None

    async def maybe_summarise_conversation(self, conversation_id, **kwargs):
        return False


def build_factory(orchestrator_cls):
    return lambda: orchestrator_cls()


class SuccessfulOrchestrator(BaseTestOrchestrator):
    async def process_request(self, user_request, conversation_id, selected_documents=None):
        await asyncio.sleep(0)
        return {
            "response": "ok",
            "conversation_id": conversation_id,
            "orchestration_actions": [
                {"tool": "calculator", "input": "2+2", "output": "4"},
            ],
            "token_usage": 4,
        }


class FailingOrchestrator(BaseTestOrchestrator):
    async def process_request(self, user_request, conversation_id, selected_documents=None):
        await asyncio.sleep(0)
        return {
            "response": "something failed",
            "conversation_id": conversation_id,
            "error": True,
        }


class RecordingRunStore(InMemoryRunStore):
    def __init__(self):
        super().__init__()
        self.running_update_kwargs = []

    def update_run(self, **kwargs):
        if kwargs.get("status") == "running":
            self.running_update_kwargs.append(dict(kwargs))
        return super().update_run(**kwargs)


class SlowReadRunStore(InMemoryRunStore):
    def __init__(self, delay_seconds=0.15):
        super().__init__()
        self.delay_seconds = delay_seconds

    def get_run(self, run_id: str):
        time.sleep(self.delay_seconds)
        return super().get_run(run_id)

    def list_events(self, *, run_id: str, after, limit: int):
        time.sleep(self.delay_seconds)
        return super().list_events(run_id=run_id, after=after, limit=limit)


@unittest.skipUnless(
    RUNTIME_SERVICE_TESTS_AVAILABLE,
    f"Runtime service test dependencies unavailable: {RUNTIME_SERVICE_IMPORT_ERROR}",
)
class TestRuntimeService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._mock_db_ops = MockDbOps()
        self._services = []
        self._db_ops_patcher = patch(
            "backend.database.operations.db_ops", self._mock_db_ops
        )
        self._tracking_db_ops_patcher = patch(
            "backend.observability.tracking.db_ops", self._mock_db_ops
        )
        self._db_ops_patcher.start()
        self._tracking_db_ops_patcher.start()

    async def asyncTearDown(self):
        while self._services:
            service = self._services.pop()
            await service.shutdown()
        self._db_ops_patcher.stop()
        self._tracking_db_ops_patcher.stop()

    def _make_service(self, **kwargs):
        service = RuntimeService(**kwargs)
        self._services.append(service)
        return service

    async def test_submit_run_transitions_to_succeeded(self):
        service = self._make_service(
            orchestrator=SuccessfulOrchestrator(),
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-1", selected_documents=[]))

        self.assertEqual(submitted["status"], "queued")
        run_id = submitted["run_id"]

        status = await self._wait_for_terminal(service, run_id)
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(status["result"], "ok")
        self.assertEqual(status["attempt_count"], 1)
        self.assertIsNotNone(status["started_at"])
        self.assertIsNotNone(status["completed_at"])

        events = await service.get_run_events(run_id=run_id, after=None, limit=100)
        event_types = [event["type"] for event in events["events"]]
        self.assertIn("started", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("succeeded", event_types)

    async def test_submit_run_triggers_background_title_generation(self):
        orchestrator = SuccessfulOrchestrator()
        title_generated = asyncio.Event()

        async def generate_title(conversation_id):
            title_generated.set()
            return "Generated Title"

        orchestrator.generate_conversation_title = AsyncMock(side_effect=generate_title)
        service = self._make_service(
            orchestrator=orchestrator,
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(
            RuntimeRequest(message="hello", conversation_id="conv-1", selected_documents=[])
        )

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "succeeded")

        await asyncio.wait_for(title_generated.wait(), timeout=1.0)
        orchestrator.generate_conversation_title.assert_awaited_once_with("conv-1")

    async def test_submit_run_transitions_to_failed(self):
        service = self._make_service(
            orchestrator=FailingOrchestrator(),
            orchestrator_factory=build_factory(FailingOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-1", selected_documents=[]))

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "something failed")
        self.assertEqual(status["attempt_count"], 1)
        self.assertIsNotNone(status["started_at"])
        self.assertIsNotNone(status["completed_at"])

    async def test_concurrent_runs_to_same_conversation_are_rejected(self):
        """Two concurrent runs to same conversation should result in one failing with session_busy."""
        proceed_event = threading.Event()

        class BlockingOrchestrator(BaseTestOrchestrator):
            async def process_request(self, user_request, conversation_id, selected_documents=None):
                if not proceed_event.wait(timeout=5.0):
                    raise TimeoutError("test orchestrator did not receive proceed signal")
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=BlockingOrchestrator(),
            orchestrator_factory=build_factory(BlockingOrchestrator),
            run_store=InMemoryRunStore(),
        )

        # Submit first run (will block waiting for event)
        submitted1 = await service.submit_run(RuntimeRequest(message="hello", conversation_id="shared-conv", selected_documents=[]))
        run_id1 = submitted1["run_id"]

        # Give first task time to reach orchestrator
        await self._wait_until_running(service, run_id1)

        # Submit second run to same conversation while first is blocked
        submitted2 = await service.submit_run(RuntimeRequest(message="hello again", conversation_id="shared-conv", selected_documents=[]))
        run_id2 = submitted2["run_id"]

        status2 = await self._wait_for_terminal(service, run_id2, timeout=5.0)
        proceed_event.set()
        status1 = await self._wait_for_terminal(service, run_id1, timeout=5.0)

        self.assertEqual(status1["status"], "succeeded")
        self.assertEqual(status2["status"], "failed")
        self.assertEqual(
            status2["error"],
            "Another operation is already running in this conversation.",
        )
        self.assertEqual(status2["attempt_count"], 0)
        self.assertIsNone(status2["started_at"])
        self.assertIsNotNone(status2["completed_at"])

    async def test_orchestrator_exception_is_retried(self):
        """Orchestrator exceptions should trigger retries up to MAX_RETRY_ATTEMPTS."""
        # Create an orchestrator that fails once then succeeds
        attempt_count = [0]

        class RetryableOrchestrator(BaseTestOrchestrator):
            async def process_request(self, user_request, conversation_id, selected_documents=None):
                await asyncio.sleep(0)
                attempt_count[0] += 1
                if attempt_count[0] < 2:
                    raise RuntimeError("Temporary failure")
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=RetryableOrchestrator(),
            orchestrator_factory=build_factory(RetryableOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-retry", selected_documents=[]))

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(attempt_count[0], 2)
        self.assertEqual(status["attempt_count"], 2)
        self.assertIsNotNone(status["started_at"])
        self.assertIsNotNone(status["completed_at"])
        started_at = datetime.fromisoformat(status["started_at"].replace("Z", "+00:00"))
        completed_at = datetime.fromisoformat(status["completed_at"].replace("Z", "+00:00"))
        self.assertLessEqual(started_at, completed_at)

        # Check that retrying event was logged
        events = await service.get_run_events(run_id=submitted["run_id"], after=None, limit=100)
        event_types = [event["type"] for event in events["events"]]
        self.assertIn("retrying", event_types)
        self.assertEqual(event_types.count("started"), 2)

    async def test_retry_attempt_sets_running_status_and_attempt_count(self):
        second_attempt_started = threading.Event()
        allow_second_attempt_to_finish = threading.Event()
        attempts = [0]

        class RetryBlockingOrchestrator(BaseTestOrchestrator):
            async def process_request(
                self, user_request, conversation_id, selected_documents=None
            ):
                attempts[0] += 1
                if attempts[0] == 1:
                    raise RuntimeError("temporary failure")

                second_attempt_started.set()
                if not allow_second_attempt_to_finish.wait(timeout=5.0):
                    raise TimeoutError("test orchestrator did not receive finish signal")
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=RetryBlockingOrchestrator(),
            orchestrator_factory=build_factory(RetryBlockingOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(
            RuntimeRequest(
                message="hello",
                conversation_id="conv-retry-running-status",
                selected_documents=[],
            )
        )

        await asyncio.to_thread(second_attempt_started.wait, 1.0)
        self.assertTrue(second_attempt_started.is_set())

        status = await service.get_run_status(submitted["run_id"])
        self.assertEqual(status["status"], "running")
        self.assertEqual(status["attempt_count"], 2)
        self.assertIsNotNone(status["started_at"])
        self.assertIsNone(status["completed_at"])

        allow_second_attempt_to_finish.set()
        terminal_status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(terminal_status["status"], "succeeded")

    async def test_retry_attempt_clears_terminal_fields_when_returning_to_running(self):
        store = RecordingRunStore()
        service = self._make_service(
            orchestrator=SuccessfulOrchestrator(),
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=store,
        )
        run = store.create_run(
            conversation_id="conv-retry-field-reset",
            message="hello",
            selected_documents=[],
        )
        store.update_run(
            run_id=run.run_id,
            status="failed",
            error="stale error",
            result="stale result",
            completed_at=datetime.now(timezone.utc),
        )

        await service._execute_attempt(
            RunExecution(
                run_id=run.run_id,
                conversation_id="conv-retry-field-reset",
                message="hello",
                selected_documents=(),
            ),
            attempt=2,
        )

        running_updates = [
            kwargs for kwargs in store.running_update_kwargs if kwargs.get("attempt_count") == 2
        ]
        self.assertEqual(len(running_updates), 1)
        self.assertIsNone(running_updates[0]["completed_at"])
        self.assertIsNone(running_updates[0]["error"])
        self.assertIsNone(running_updates[0]["result"])

    async def test_status_polling_remains_prompt_during_blocking_attempt(self):
        started_event = threading.Event()

        class BlockingOrchestrator(BaseTestOrchestrator):
            async def process_request(
                self, user_request, conversation_id, selected_documents=None
            ):
                started_event.set()
                time.sleep(0.35)
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=BlockingOrchestrator(),
            orchestrator_factory=build_factory(BlockingOrchestrator),
            run_store=InMemoryRunStore(),
            orchestration_max_workers=1,
        )
        submitted = await service.submit_run(
            RuntimeRequest(
                message="hello",
                conversation_id="conv-responsive-status",
                selected_documents=[],
            )
        )
        run_id = submitted["run_id"]

        await self._wait_until_running(service, run_id)
        await asyncio.to_thread(started_event.wait, 1.0)
        self.assertTrue(started_event.is_set())

        latencies = []
        for _ in range(5):
            started = time.perf_counter()
            status = await asyncio.wait_for(service.get_run_status(run_id), timeout=0.1)
            latencies.append(time.perf_counter() - started)
            self.assertIn(status["status"], {"running", "succeeded"})
            await asyncio.sleep(0.01)

        self.assertTrue(all(latency < 0.1 for latency in latencies), latencies)

        status = await self._wait_for_terminal(service, run_id)
        self.assertEqual(status["status"], "succeeded")

    async def test_events_polling_remains_prompt_during_blocking_attempt(self):
        started_event = threading.Event()

        class BlockingOrchestrator(BaseTestOrchestrator):
            async def process_request(
                self, user_request, conversation_id, selected_documents=None
            ):
                started_event.set()
                time.sleep(0.35)
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=BlockingOrchestrator(),
            orchestrator_factory=build_factory(BlockingOrchestrator),
            run_store=InMemoryRunStore(),
            orchestration_max_workers=1,
        )
        submitted = await service.submit_run(
            RuntimeRequest(
                message="hello",
                conversation_id="conv-responsive-events",
                selected_documents=[],
            )
        )
        run_id = submitted["run_id"]

        await self._wait_until_running(service, run_id)
        await asyncio.to_thread(started_event.wait, 1.0)
        self.assertTrue(started_event.is_set())

        latencies = []
        for _ in range(5):
            started = time.perf_counter()
            events = await asyncio.wait_for(
                service.get_run_events(run_id=run_id, after=None, limit=100),
                timeout=0.1,
            )
            latencies.append(time.perf_counter() - started)
            event_types = [event["type"] for event in events["events"]]
            self.assertIn("started", event_types)
            await asyncio.sleep(0.01)

        self.assertTrue(all(latency < 0.1 for latency in latencies), latencies)

        status = await self._wait_for_terminal(service, run_id)
        self.assertEqual(status["status"], "succeeded")

        events = await service.get_run_events(run_id=run_id, after=None, limit=100)
        event_types = [event["type"] for event in events["events"]]
        self.assertIn("succeeded", event_types)

    async def test_get_run_status_offloads_slow_store_reads(self):
        store = SlowReadRunStore()
        run = store.create_run(
            conversation_id="conv-slow-status",
            message="hello",
            selected_documents=[],
        )
        service = self._make_service(
            orchestrator=SuccessfulOrchestrator(),
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=store,
        )

        status_task = asyncio.create_task(service.get_run_status(run.run_id))
        await asyncio.sleep(0)

        loop_latency = await self._measure_sleep_window()
        status = await status_task

        self.assertEqual(status["run_id"], run.run_id)
        self.assertLess(loop_latency, 0.12, loop_latency)

    async def test_get_run_events_offloads_slow_store_reads(self):
        store = SlowReadRunStore()
        run = store.create_run(
            conversation_id="conv-slow-events",
            message="hello",
            selected_documents=[],
        )
        store.append_event(
            run_id=run.run_id,
            event_type="queued",
            status="queued",
            message="Run accepted",
        )
        service = self._make_service(
            orchestrator=SuccessfulOrchestrator(),
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=store,
        )

        events_task = asyncio.create_task(
            service.get_run_events(run_id=run.run_id, after=None, limit=100)
        )
        await asyncio.sleep(0)

        loop_latency = await self._measure_sleep_window()
        events = await events_task

        self.assertEqual(events["run_id"], run.run_id)
        self.assertEqual(len(events["events"]), 1)
        self.assertLess(loop_latency, 0.12, loop_latency)

    async def test_submit_run_offloads_blocking_conversation_creation(self):
        started_event = threading.Event()

        class BlockingConversationOrchestrator(BaseTestOrchestrator):
            def create_conversation(self):
                started_event.set()
                time.sleep(0.35)
                return "conv-created-in-worker"

            async def process_request(
                self, user_request, conversation_id, selected_documents=None
            ):
                await asyncio.sleep(0)
                return {
                    "response": "ok",
                    "conversation_id": conversation_id,
                    "orchestration_actions": [],
                    "token_usage": 4,
                }

        service = self._make_service(
            orchestrator=BlockingConversationOrchestrator(),
            orchestrator_factory=build_factory(BlockingConversationOrchestrator),
            run_store=InMemoryRunStore(),
            orchestration_max_workers=1,
        )

        submit_task = asyncio.create_task(
            service.submit_run(
                RuntimeRequest(
                    message="hello",
                    conversation_id=None,
                    selected_documents=[],
                )
            )
        )

        await asyncio.to_thread(started_event.wait, 1.0)
        self.assertTrue(started_event.is_set())

        latencies = []
        for _ in range(5):
            started = time.perf_counter()
            await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.1)
            latencies.append(time.perf_counter() - started)

        self.assertTrue(all(latency < 0.1 for latency in latencies), latencies)

        submitted = await asyncio.wait_for(submit_task, timeout=1.0)
        self.assertEqual(submitted["conversation_id"], "conv-created-in-worker")

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "succeeded")

    async def test_requires_factory_for_multi_worker_execution(self):
        with self.assertRaisesRegex(
            ValueError,
            "orchestrator_factory is required when orchestration_max_workers > 1",
        ):
            RuntimeService(
                orchestrator=SuccessfulOrchestrator(),
                run_store=InMemoryRunStore(),
            )

    async def test_custom_executor_allows_shared_orchestrator_configuration(self):
        executor = ThreadPoolExecutor(max_workers=2)
        service = None
        try:
            service = self._make_service(
                orchestrator=SuccessfulOrchestrator(),
                orchestration_executor=executor,
                run_store=InMemoryRunStore(),
            )
            submitted = await service.submit_run(
                RuntimeRequest(
                    message="hello",
                    conversation_id="conv-custom-executor",
                    selected_documents=[],
                )
            )
            status = await self._wait_for_terminal(service, submitted["run_id"])
            self.assertEqual(status["status"], "succeeded")
        finally:
            executor.shutdown(wait=False, cancel_futures=False)

    async def test_shutdown_allows_owned_executor_to_restart_on_next_submission(self):
        service = self._make_service(
            orchestrator=SuccessfulOrchestrator(),
            orchestrator_factory=build_factory(SuccessfulOrchestrator),
            run_store=InMemoryRunStore(),
            orchestration_max_workers=1,
        )

        first_submission = await service.submit_run(
            RuntimeRequest(
                message="first",
                conversation_id="conv-restartable-service",
                selected_documents=[],
            )
        )
        first_status = await self._wait_for_terminal(service, first_submission["run_id"])
        self.assertEqual(first_status["status"], "succeeded")

        await service.shutdown()

        second_submission = await service.submit_run(
            RuntimeRequest(
                message="second",
                conversation_id="conv-restartable-service",
                selected_documents=[],
            )
        )
        second_status = await self._wait_for_terminal(
            service, second_submission["run_id"]
        )
        self.assertEqual(second_status["status"], "succeeded")

    async def _wait_until_running(self, service, run_id):
        for _ in range(80):
            status = await service.get_run_status(run_id)
            if status["status"] == "running":
                return status
            await asyncio.sleep(0.01)
        self.fail(f"run {run_id} did not reach running state")

    async def _wait_for_terminal(self, service, run_id, timeout=0.8):
        terminal = {"succeeded", "failed", "cancelled"}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = await service.get_run_status(run_id)
            if status["status"] in terminal:
                return status
            await asyncio.sleep(0.01)
        self.fail(f"run {run_id} did not complete")

    async def _measure_sleep_window(self, samples=5, delay=0.01):
        started = time.perf_counter()
        for _ in range(samples):
            await asyncio.sleep(delay)
        return time.perf_counter() - started


if __name__ == "__main__":
    unittest.main()
