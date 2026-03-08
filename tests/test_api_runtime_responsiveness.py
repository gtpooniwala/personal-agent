"""Runtime API responsiveness tests for blocking orchestration attempts."""

import asyncio
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

API_TESTS_AVAILABLE = True
API_IMPORT_ERROR = ""

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api import runtime_routes
    from backend.runtime.service import RuntimeService
    from backend.runtime.store import InMemoryRunStore
except (ImportError, ModuleNotFoundError) as exc:
    API_TESTS_AVAILABLE = False
    API_IMPORT_ERROR = str(exc)


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


class BlockingOrchestrator:
    def __init__(self, started_event, block_seconds=0.35):
        self._started_event = started_event
        self._block_seconds = block_seconds

    def create_conversation(self):
        return "conv-generated"

    async def process_request(self, user_request, conversation_id, selected_documents=None):
        self._started_event.set()
        time.sleep(self._block_seconds)
        return {
            "response": "ok",
            "conversation_id": conversation_id,
            "orchestration_actions": [],
            "token_usage": 4,
        }

    async def generate_conversation_title(self, conversation_id):
        return None

    async def maybe_summarise_conversation(self, conversation_id, **kwargs):
        return False


@unittest.skipUnless(
    API_TESTS_AVAILABLE,
    f"API test dependencies unavailable: {API_IMPORT_ERROR}",
)
class TestRuntimeRouteResponsiveness(unittest.TestCase):
    def test_status_and_events_endpoints_remain_prompt_during_blocking_run(self):
        started_event = threading.Event()
        service = RuntimeService(
            orchestrator=BlockingOrchestrator(started_event),
            orchestrator_factory=lambda: BlockingOrchestrator(started_event),
            orchestration_max_workers=1,
            run_store=InMemoryRunStore(),
        )

        app = FastAPI()
        app.include_router(runtime_routes.runtime_router)
        mock_db_ops = MockDbOps()

        try:
            with patch("backend.database.operations.db_ops", mock_db_ops):
                with patch("backend.observability.tracking.db_ops", mock_db_ops):
                    with patch.object(runtime_routes, "runtime_service", service):
                        with TestClient(app) as client:
                            response = client.post(
                                "/runs",
                                json={
                                    "message": "hello",
                                    "conversation_id": "conv-api-responsive",
                                    "selected_documents": [],
                                },
                            )
                            self.assertEqual(response.status_code, 200)
                            payload = response.json()
                            run_id = payload["run_id"]
                            self.assertEqual(payload["status"], "queued")

                            self.assertTrue(started_event.wait(timeout=1.0))
                            self._wait_until_running(client, run_id)

                            latencies = []
                            for _ in range(5):
                                started = time.perf_counter()
                                status_response = client.get(f"/runs/{run_id}/status")
                                latencies.append(time.perf_counter() - started)
                                self.assertEqual(status_response.status_code, 200)
                                self.assertIn(
                                    status_response.json()["status"],
                                    {"running", "succeeded"},
                                )

                                started = time.perf_counter()
                                events_response = client.get(
                                    f"/runs/{run_id}/events?limit=100"
                                )
                                latencies.append(time.perf_counter() - started)
                                self.assertEqual(events_response.status_code, 200)
                                event_types = [
                                    event["type"]
                                    for event in events_response.json()["events"]
                                ]
                                self.assertIn("started", event_types)
                                time.sleep(0.01)

                            self.assertTrue(
                                all(latency < 0.1 for latency in latencies),
                                latencies,
                            )

                            terminal_payload = self._wait_until_terminal(client, run_id)
                            self.assertEqual(terminal_payload["status"], "succeeded")
        finally:
            asyncio.run(service.shutdown())

    def _wait_until_running(self, client, run_id):
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            payload = client.get(f"/runs/{run_id}/status").json()
            if payload["status"] == "running":
                return
            time.sleep(0.01)
        self.fail(f"run {run_id} did not reach running state")

    def _wait_until_terminal(self, client, run_id):
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            payload = client.get(f"/runs/{run_id}/status").json()
            if payload["status"] in {"succeeded", "failed", "cancelled"}:
                return payload
            time.sleep(0.01)
        self.fail(f"run {run_id} did not reach terminal state")


if __name__ == "__main__":
    unittest.main()
