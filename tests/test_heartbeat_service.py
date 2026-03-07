"""Unit tests for HeartbeatService.

Uses injected fake db_ops so no real database is required.
"""
import sys
import unittest
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.runtime.heartbeat import HeartbeatService, ORPHAN_ERROR_MESSAGE
from backend.runtime.contracts import RUN_STATUS_FAILED, RUN_EVENT_FAILED


class FakeDbOps:
    """Minimal db_ops stand-in for heartbeat sweep tests."""

    def __init__(self, orphans=None, runs=None):
        self._orphans = list(orphans or [])
        seed_runs = list(runs or [])
        if runs is None:
            seed_runs = list(orphans or [])
            for run in seed_runs:
                if "status" not in run:
                    run["status"] = "running"
        self._runs = {str(r["id"]): r for r in seed_runs}
        self.updated = []
        self.events = []

    def find_orphaned_runs(self):
        return list(self._orphans)

    def update_run(self, run_id, status, error=None):
        self.updated.append({"run_id": run_id, "status": status, "error": error})

    def append_run_event(self, *, run_id, event_type, status, message):
        self.events.append({
            "run_id": run_id,
            "event_type": event_type,
            "status": status,
            "message": message,
        })

    def get_run(self, run_id):
        return self._runs.get(run_id)


class ErrorDbOps:
    def find_orphaned_runs(self):
        raise RuntimeError("db down")

class TestHeartbeatService(unittest.IsolatedAsyncioTestCase):
    async def test_sweep_marks_orphaned_runs_failed(self):
        orphans = [{"id": "run-1", "conversation_id": "conv-1", "status": "running"}]
        fake_db = FakeDbOps(orphans=orphans)
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=fake_db)

        await service._sweep()

        self.assertEqual(len(fake_db.updated), 1)
        self.assertEqual(fake_db.updated[0]["run_id"], "run-1")
        self.assertEqual(fake_db.updated[0]["status"], RUN_STATUS_FAILED)
        self.assertEqual(fake_db.updated[0]["error"], ORPHAN_ERROR_MESSAGE)

        self.assertEqual(len(fake_db.events), 1)
        self.assertEqual(fake_db.events[0]["run_id"], "run-1")
        self.assertEqual(fake_db.events[0]["status"], RUN_STATUS_FAILED)
        self.assertEqual(fake_db.events[0]["event_type"], RUN_EVENT_FAILED)

    async def test_sweep_noop_when_no_orphans(self):
        fake_db = FakeDbOps(orphans=[])
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=fake_db)

        await service._sweep()

        self.assertEqual(fake_db.updated, [])
        self.assertEqual(fake_db.events, [])

    async def test_sweep_handles_multiple_orphans(self):
        orphans = [
            {"id": "run-1", "conversation_id": "conv-1", "status": "running"},
            {"id": "run-2", "conversation_id": "conv-2", "status": "retrying"},
        ]
        fake_db = FakeDbOps(orphans=orphans)
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=fake_db)

        await service._sweep()

        self.assertEqual(len(fake_db.updated), 2)
        run_ids = {u["run_id"] for u in fake_db.updated}
        self.assertEqual(run_ids, {"run-1", "run-2"})

    async def test_sweep_skips_terminal_runs(self):
        orphans = [{"id": "run-1", "conversation_id": "conv-1", "status": "running"}]
        fake_db = FakeDbOps(
            orphans=orphans,
            runs=[{"id": "run-1", "status": "completed"}],
        )
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=fake_db)

        await service._sweep()

        self.assertEqual(fake_db.updated, [])
        self.assertEqual(fake_db.events, [])

    async def test_start_stop_lifecycle(self):
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=FakeDbOps())
        await service.start()
        self.assertIsNotNone(service._task)
        await service.stop()
        self.assertIsNone(service._task)

    async def test_sweep_query_error_does_not_raise(self):
        """A db error during find_orphaned_runs should be caught silently."""
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=ErrorDbOps())
        # Should not raise
        await service._sweep()

    async def test_stop_without_start_is_safe(self):
        service = HeartbeatService(poll_interval_seconds=9999, db_ops=FakeDbOps())
        await service.stop()  # no-op, no task running


if __name__ == "__main__":
    unittest.main()
