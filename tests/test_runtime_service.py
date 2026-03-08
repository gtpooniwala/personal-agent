import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

RUNTIME_SERVICE_TESTS_AVAILABLE = True
RUNTIME_SERVICE_IMPORT_ERROR = ""

try:
    from backend.runtime.service import RuntimeService
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


@unittest.skipUnless(
    RUNTIME_SERVICE_TESTS_AVAILABLE,
    f"Runtime service test dependencies unavailable: {RUNTIME_SERVICE_IMPORT_ERROR}",
)
class TestRuntimeService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._mock_db_ops = MockDbOps()
        self._db_ops_patcher = patch(
            "backend.database.operations.db_ops", self._mock_db_ops
        )
        self._tracking_db_ops_patcher = patch(
            "backend.observability.tracking.db_ops", self._mock_db_ops
        )
        self._db_ops_patcher.start()
        self._tracking_db_ops_patcher.start()

    async def asyncTearDown(self):
        self._db_ops_patcher.stop()
        self._tracking_db_ops_patcher.stop()

    async def test_submit_run_transitions_to_succeeded(self):
        service = RuntimeService(
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

        events = await service.get_run_events(run_id=run_id, after=None, limit=100)
        event_types = [event["type"] for event in events["events"]]
        self.assertIn("started", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("succeeded", event_types)

    async def test_submit_run_transitions_to_failed(self):
        service = RuntimeService(
            orchestrator=FailingOrchestrator(),
            orchestrator_factory=build_factory(FailingOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-1", selected_documents=[]))

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "something failed")

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

        service = RuntimeService(
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

        service = RuntimeService(
            orchestrator=RetryableOrchestrator(),
            orchestrator_factory=build_factory(RetryableOrchestrator),
            run_store=InMemoryRunStore(),
        )
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-retry", selected_documents=[]))

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(attempt_count[0], 2)

        # Check that retrying event was logged
        events = await service.get_run_events(run_id=submitted["run_id"], after=None, limit=100)
        event_types = [event["type"] for event in events["events"]]
        self.assertIn("retrying", event_types)

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

        service = RuntimeService(
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

        service = RuntimeService(
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
            service = RuntimeService(
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
            if service is not None:
                await service.shutdown()
            executor.shutdown(wait=False, cancel_futures=False)

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


if __name__ == "__main__":
    unittest.main()
