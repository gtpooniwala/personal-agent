import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

STREAMING_TESTS_AVAILABLE = True
STREAMING_IMPORT_ERROR = ""
ROUTE_STREAMING_TESTS_AVAILABLE = True
ROUTE_STREAMING_IMPORT_ERROR = ""
STREAM_TEST_TIMEOUT_SECONDS = 1.0

try:
    from backend.api.sse import generate_run_sse
    from backend.runtime import RunNotFoundError
    from backend.runtime.store import InMemoryRunStore
except (ImportError, ModuleNotFoundError) as exc:
    STREAMING_TESTS_AVAILABLE = False
    STREAMING_IMPORT_ERROR = str(exc)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api import runtime_routes
except (ImportError, ModuleNotFoundError) as exc:
    ROUTE_STREAMING_TESTS_AVAILABLE = False
    ROUTE_STREAMING_IMPORT_ERROR = str(exc)


def parse_sse_message(message: str):
    event_type = None
    data = None
    for line in message.strip().splitlines():
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data = json.loads(line[len("data: ") :])
    return {"event": event_type, "data": data}


class FakeRuntimeService:
    def __init__(self, store):
        self._store = store

    async def get_run_status(self, run_id):
        return self._store.get_run(run_id).to_status_payload()

    async def get_run_events(self, *, run_id, after, limit):
        events, next_after, has_more = self._store.list_events(
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


class PrunedRunRuntimeService(FakeRuntimeService):
    def __init__(self, store):
        super().__init__(store)
        self._events_calls = 0

    async def get_run_events(self, *, run_id, after, limit):
        self._events_calls += 1
        if self._events_calls == 2:
            raise RunNotFoundError(f"Run '{run_id}' was not found")
        return await super().get_run_events(run_id=run_id, after=after, limit=limit)


@unittest.skipUnless(
    STREAMING_TESTS_AVAILABLE,
    f"Streaming test dependencies unavailable: {STREAMING_IMPORT_ERROR}",
)
class TestRunStreaming(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = InMemoryRunStore()
        self.runtime_service = FakeRuntimeService(self.store)

    async def test_generate_run_sse_replays_backlog_before_live_events(self):
        run = self.store.create_run(
            conversation_id="conv-stream-backlog",
            message="hello",
            selected_documents=[],
        )
        self.store.append_event(
            run_id=run.run_id,
            event_type="queued",
            status="queued",
            message="Run accepted and queued",
        )
        self.store.update_run(run_id=run.run_id, status="running")
        self.store.append_event(
            run_id=run.run_id,
            event_type="started",
            status="running",
            message="Run started",
        )

        stream = generate_run_sse(
            runtime_service=self.runtime_service,
            run_id=run.run_id,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=1.0,
        )

        first = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        second = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )

        self.assertEqual(first["event"], "run_event")
        self.assertEqual(first["data"]["event_type"], "queued")
        self.assertEqual(second["data"]["event_type"], "started")

        self.store.append_event(
            run_id=run.run_id,
            event_type="tool_result",
            status="running",
            message="Tool action completed",
            tool="calculator",
        )
        live = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        self.assertEqual(live["data"]["event_type"], "tool_result")
        self.assertEqual(live["data"]["payload"]["tool"], "calculator")

        self.store.update_run(run_id=run.run_id, status="succeeded", result="ok", error=None)
        self.store.append_event(
            run_id=run.run_id,
            event_type="succeeded",
            status="succeeded",
            message="Run completed successfully",
        )

        terminal_event = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        completion = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        self.assertEqual(terminal_event["data"]["event_type"], "succeeded")
        self.assertEqual(completion["event"], "run_complete")
        self.assertEqual(completion["data"]["status"], "succeeded")

    async def test_generate_run_sse_streams_live_events_after_connection(self):
        run = self.store.create_run(
            conversation_id="conv-stream-live",
            message="hello",
            selected_documents=[],
        )
        self.store.update_run(run_id=run.run_id, status="running")
        self.store.append_event(
            run_id=run.run_id,
            event_type="started",
            status="running",
            message="Run started",
        )

        stream = generate_run_sse(
            runtime_service=self.runtime_service,
            run_id=run.run_id,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=1.0,
        )

        initial = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        self.assertEqual(initial["data"]["event_type"], "started")

        async def publish_live_event():
            await asyncio.sleep(0.03)
            self.store.append_event(
                run_id=run.run_id,
                event_type="tool_result",
                status="running",
                message="Tool action completed",
                tool="time",
            )
            await asyncio.sleep(0.03)
            self.store.update_run(run_id=run.run_id, status="succeeded", result="done", error=None)
            self.store.append_event(
                run_id=run.run_id,
                event_type="succeeded",
                status="succeeded",
                message="Run completed successfully",
            )

        producer = asyncio.create_task(publish_live_event())
        try:
            live = parse_sse_message(
                await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
            )
            self.assertEqual(live["data"]["event_type"], "tool_result")
            self.assertEqual(live["data"]["payload"]["tool"], "time")

            terminal = parse_sse_message(
                await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
            )
            complete = parse_sse_message(
                await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
            )
            self.assertEqual(terminal["data"]["event_type"], "succeeded")
            self.assertEqual(complete["event"], "run_complete")
        finally:
            await producer

    async def test_generate_run_sse_closes_after_completion_signal(self):
        run = self.store.create_run(
            conversation_id="conv-stream-complete",
            message="hello",
            selected_documents=[],
        )
        self.store.update_run(run_id=run.run_id, status="failed", error="boom", result=None)
        self.store.append_event(
            run_id=run.run_id,
            event_type="failed",
            status="failed",
            message="boom",
        )

        stream = generate_run_sse(
            runtime_service=self.runtime_service,
            run_id=run.run_id,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=1.0,
        )

        terminal = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        completion = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )

        self.assertEqual(terminal["data"]["event_type"], "failed")
        self.assertEqual(completion["event"], "run_complete")
        self.assertEqual(completion["data"]["status"], "failed")

        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)

    async def test_generate_run_sse_sends_heartbeats_while_idle(self):
        run = self.store.create_run(
            conversation_id="conv-stream-heartbeat",
            message="hello",
            selected_documents=[],
        )
        self.store.update_run(run_id=run.run_id, status="running")
        disconnected = False

        async def is_disconnected():
            return disconnected

        stream = generate_run_sse(
            runtime_service=self.runtime_service,
            run_id=run.run_id,
            is_disconnected=is_disconnected,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=0.02,
        )

        heartbeat = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        self.assertEqual(heartbeat["event"], "heartbeat")
        self.assertEqual(heartbeat["data"], {})

        disconnected = True
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)

    async def test_generate_run_sse_closes_cleanly_if_run_is_pruned_mid_stream(self):
        run = self.store.create_run(
            conversation_id="conv-stream-pruned",
            message="hello",
            selected_documents=[],
        )
        self.store.append_event(
            run_id=run.run_id,
            event_type="queued",
            status="queued",
            message="Run accepted and queued",
        )
        self.store.update_run(run_id=run.run_id, status="succeeded", result="ok", error=None)

        stream = generate_run_sse(
            runtime_service=PrunedRunRuntimeService(self.store),
            run_id=run.run_id,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=1.0,
            events_limit=1,
        )

        first = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )
        completion = parse_sse_message(
            await asyncio.wait_for(anext(stream), timeout=STREAM_TEST_TIMEOUT_SECONDS)
        )

        self.assertEqual(first["event"], "run_event")
        self.assertEqual(first["data"]["event_type"], "queued")
        self.assertEqual(completion["event"], "run_complete")
        self.assertEqual(completion["data"]["status"], "unavailable")

@unittest.skipUnless(
    ROUTE_STREAMING_TESTS_AVAILABLE,
    f"Route streaming test dependencies unavailable: {ROUTE_STREAMING_IMPORT_ERROR}",
)
class TestRunStreamingRoute(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryRunStore()
        self.runtime_service = FakeRuntimeService(self.store)

    def test_runtime_route_stream_endpoint_returns_sse_payload(self):
        run = self.store.create_run(
            conversation_id="conv-stream-route",
            message="hello",
            selected_documents=[],
        )
        self.store.append_event(
            run_id=run.run_id,
            event_type="queued",
            status="queued",
            message="Run accepted and queued",
        )
        self.store.update_run(run_id=run.run_id, status="succeeded", result="ok", error=None)
        self.store.append_event(
            run_id=run.run_id,
            event_type="succeeded",
            status="succeeded",
            message="Run completed successfully",
        )

        app = FastAPI()
        app.include_router(runtime_routes.runtime_router)

        with patch.object(runtime_routes, "runtime_service", self.runtime_service):
            with TestClient(app) as client:
                response = client.get(f"/runs/{run.run_id}/stream")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        messages = [
            parse_sse_message(message)
            for message in response.text.strip().split("\n\n")
            if message.strip()
        ]
        self.assertEqual(messages[0]["event"], "run_event")
        self.assertEqual(messages[0]["data"]["event_type"], "queued")
        self.assertEqual(messages[-1]["event"], "run_complete")


if __name__ == "__main__":
    unittest.main()
