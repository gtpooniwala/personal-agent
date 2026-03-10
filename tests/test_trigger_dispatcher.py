"""Unit tests for TriggerDispatcher.

Uses injected fake db_ops and runtime service so no real database is required.
"""
import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

AVAILABLE = True
IMPORT_ERROR = ""

try:
    from backend.runtime.trigger_dispatcher import TriggerDispatcher, _TriggerRequest
except (ImportError, ModuleNotFoundError) as exc:
    AVAILABLE = False
    IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRuntimeService:
    def __init__(self, run_id="run-abc", raise_on_submit=False):
        self._run_id = run_id
        self._raise = raise_on_submit
        self.submitted = []

    async def submit_run(self, request):
        if self._raise:
            raise RuntimeError("backend down")
        self.submitted.append(request)
        return {"run_id": self._run_id, "status": "queued", "conversation_id": request.conversation_id}


class FakeDbOps:
    def __init__(self, *, existing_event=None, lease_acquired=True, trigger_event_id="te-1"):
        self._existing_event = existing_event
        self._lease_acquired = lease_acquired
        self._trigger_event_id = trigger_event_id
        self.trigger_events_created = []
        self.dispatched_events = []
        self.leases: dict = {}
        self.released = []
        self.get_trigger_event_call_count = 0

    def get_trigger_event(self, trigger_id, external_event_id):
        self.get_trigger_event_call_count += 1
        return self._existing_event

    def acquire_lease(self, lease_key, owner_id, ttl_seconds):
        if not self._lease_acquired or lease_key in self.leases:
            return None
        self.leases[lease_key] = owner_id
        return {"lease_key": lease_key, "owner_id": owner_id}

    def release_lease(self, lease_key, owner_id):
        self.released.append(lease_key)
        self.leases.pop(lease_key, None)
        return True

    def create_trigger_event(self, *, trigger_id, external_event_id, dispatched=False):
        row = {
            "id": self._trigger_event_id,
            "trigger_id": trigger_id,
            "external_event_id": external_event_id,
            "run_id": None,
            "received_at": "2026-01-01T00:00:00+00:00",
            "dispatched": dispatched,
        }
        self.trigger_events_created.append(row)
        return row

    def mark_trigger_event_dispatched(self, event_id, run_id):
        self.dispatched_events.append((event_id, run_id))
        return None


def _make_trigger(conversation_id: str = "conv-1") -> dict:
    return {
        "id": "trigger-1",
        "type": "telegram",
        "name": "my-trigger",
        "conversation_id": conversation_id,
        "config": None,
        "enabled": True,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(AVAILABLE, f"Skipping — import failed: {IMPORT_ERROR}")
class TestTriggerDispatcher(unittest.IsolatedAsyncioTestCase):

    async def test_dispatch_creates_run(self):
        """First call dispatches and returns a run_id."""
        trigger = _make_trigger()
        db = FakeDbOps()
        rt = FakeRuntimeService(run_id="run-abc")
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="hello", external_event_id="ext-1")

        self.assertEqual(result, "run-abc")
        self.assertEqual(len(db.trigger_events_created), 1)
        self.assertEqual(db.trigger_events_created[0]["external_event_id"], "ext-1")
        self.assertEqual(db.dispatched_events, [("te-1", "run-abc")])
        self.assertEqual(len(db.released), 1)

    async def test_dispatch_dedup_skips_existing_event(self):
        """Second call with same external_event_id is skipped when dedup=True."""
        trigger = _make_trigger()
        existing = {
            "id": "te-1",
            "trigger_id": "trigger-1",
            "external_event_id": "ext-1",
            "run_id": "run-abc",
            "received_at": "2026-01-01T00:00:00+00:00",
            "dispatched": True,
        }
        db = FakeDbOps(existing_event=existing)
        rt = FakeRuntimeService()
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="hello", external_event_id="ext-1", dedup=True)

        self.assertIsNone(result)
        self.assertEqual(rt.submitted, [])
        self.assertEqual(db.trigger_events_created, [])

    async def test_dispatch_dedup_false_bypasses_dedup_check(self):
        """dedup=False skips the existing-event lookup and always dispatches."""
        trigger = _make_trigger()
        db = FakeDbOps()
        rt = FakeRuntimeService(run_id="run-new")
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="hello", external_event_id="ext-1", dedup=False)

        self.assertEqual(result, "run-new")
        # get_trigger_event should not have been called when dedup=False
        self.assertEqual(db.get_trigger_event_call_count, 0)
        self.assertEqual(len(rt.submitted), 1)

    async def test_dispatch_returns_none_when_lease_not_acquired(self):
        """Returns None without creating a run if the dispatch lease is held."""
        trigger = _make_trigger()
        db = FakeDbOps(lease_acquired=False)
        rt = FakeRuntimeService()
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="hello", external_event_id="ext-1")

        self.assertIsNone(result)
        self.assertEqual(rt.submitted, [])
        self.assertEqual(db.trigger_events_created, [])

    async def test_dispatch_returns_none_when_submit_run_raises(self):
        """Returns None if RuntimeService.submit_run raises; TriggerEvent row still created."""
        trigger = _make_trigger()
        db = FakeDbOps()
        rt = FakeRuntimeService(raise_on_submit=True)
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="hello", external_event_id="ext-1")

        self.assertIsNone(result)
        # TriggerEvent row created but mark_dispatched never called
        self.assertEqual(len(db.trigger_events_created), 1)
        self.assertEqual(db.dispatched_events, [])
        # Lease is always released
        self.assertEqual(len(db.released), 1)

    async def test_dispatch_retries_undispatched_existing_row(self):
        """An existing TriggerEvent with dispatched=False (prior failure) is retried."""
        trigger = _make_trigger()
        undispatched = {
            "id": "te-1",
            "trigger_id": "trigger-1",
            "external_event_id": "ext-1",
            "run_id": None,
            "received_at": "2026-01-01T00:00:00+00:00",
            "dispatched": False,
        }
        db = FakeDbOps(existing_event=undispatched)
        rt = FakeRuntimeService(run_id="run-retry")
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        result = await dispatcher.dispatch(trigger, message="retry me", external_event_id="ext-1", dedup=True)

        # Should dispatch (not skip) because dispatched=False
        self.assertEqual(result, "run-retry")
        # Existing row should be reused, not a new one created
        self.assertEqual(db.trigger_events_created, [])
        self.assertEqual(db.dispatched_events, [("te-1", "run-retry")])

    async def test_dispatch_injects_correct_conversation(self):
        """The submitted run uses the trigger's conversation_id (stub passthrough)."""
        trigger = _make_trigger(conversation_id="conv-xyz")
        db = FakeDbOps()
        rt = FakeRuntimeService()
        dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

        await dispatcher.dispatch(trigger, message="do it", external_event_id="ext-1")

        self.assertEqual(len(rt.submitted), 1)
        self.assertEqual(rt.submitted[0].conversation_id, "conv-xyz")
        self.assertEqual(rt.submitted[0].message, "do it")


@unittest.skipUnless(AVAILABLE, f"Skipping — import failed: {IMPORT_ERROR}")
class TestResolveConversation(unittest.TestCase):

    def test_stub_returns_trigger_default_conversation_id(self):
        """_resolve_conversation stub always returns trigger's conversation_id."""
        from unittest.mock import MagicMock
        trigger = _make_trigger(conversation_id="conv-xyz")
        dispatcher = TriggerDispatcher(runtime_service=MagicMock(), db_ops=MagicMock())
        result = dispatcher._resolve_conversation(trigger, {})
        self.assertEqual(result, "conv-xyz")


@unittest.skipUnless(AVAILABLE, f"Skipping — import failed: {IMPORT_ERROR}")
class TestTriggerRequest(unittest.TestCase):

    def test_attributes(self):
        req = _TriggerRequest(conversation_id="conv-1", message="do something")
        self.assertEqual(req.conversation_id, "conv-1")
        self.assertEqual(req.message, "do something")
        self.assertEqual(req.selected_documents, [])


if __name__ == "__main__":
    unittest.main()
