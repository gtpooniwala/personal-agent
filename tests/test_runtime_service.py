import asyncio
import os
import sys
import unittest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

RUNTIME_SERVICE_TESTS_AVAILABLE = True
RUNTIME_SERVICE_IMPORT_ERROR = ""

try:
    from backend.runtime.service import RuntimeService
    from backend.runtime.store import InMemoryRunStore
except Exception as exc:
    RUNTIME_SERVICE_TESTS_AVAILABLE = False
    RUNTIME_SERVICE_IMPORT_ERROR = str(exc)


class RuntimeRequest:
    def __init__(self, message, conversation_id=None, selected_documents=None):
        self.message = message
        self.conversation_id = conversation_id
        self.selected_documents = selected_documents or []


class SuccessfulOrchestrator:
    def create_conversation(self):
        return "conv-generated"

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


class FailingOrchestrator:
    def create_conversation(self):
        return "conv-generated"

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
    async def test_submit_run_transitions_to_succeeded(self):
        service = RuntimeService(orchestrator=SuccessfulOrchestrator(), run_store=InMemoryRunStore())
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
        service = RuntimeService(orchestrator=FailingOrchestrator(), run_store=InMemoryRunStore())
        submitted = await service.submit_run(RuntimeRequest(message="hello", conversation_id="conv-1", selected_documents=[]))

        status = await self._wait_for_terminal(service, submitted["run_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "something failed")

    async def _wait_for_terminal(self, service, run_id):
        terminal = {"succeeded", "failed", "cancelled"}
        for _ in range(80):
            status = await service.get_run_status(run_id)
            if status["status"] in terminal:
                return status
            await asyncio.sleep(0.01)
        self.fail(f"run {run_id} did not complete")


if __name__ == "__main__":
    unittest.main()
