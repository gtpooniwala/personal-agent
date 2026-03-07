"""Unit tests for SchedulerService.

Uses injected fake db_ops so no real database is required.
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

AVAILABLE = True
IMPORT_ERROR = ""

try:
    from backend.runtime.scheduler import SchedulerService, _next_run_at
except (ImportError, ModuleNotFoundError) as exc:
    AVAILABLE = False
    IMPORT_ERROR = str(exc)


class FakeRuntimeService:
    def __init__(self, run_id="run-abc", raise_on_submit=False):
        self._run_id = run_id
        self._raise = raise_on_submit
        self.submitted = []

    async def submit_run(self, request):
        if self._raise:
            raise RuntimeError("oops")
        self.submitted.append(request)
        return {"run_id": self._run_id, "status": "queued", "conversation_id": request.conversation_id}


class FakeDbOps:
    def __init__(self, due_tasks=None):
        self._due = list(due_tasks or [])
        self.leases: dict = {}
        self.advanced = []

    def get_due_scheduled_tasks(self, limit=50):
        return list(self._due)

    def acquire_lease(self, lease_key, owner_id, ttl_seconds):
        if lease_key in self.leases:
            return None
        self.leases[lease_key] = owner_id
        return {"lease_key": lease_key, "owner_id": owner_id}

    def release_lease(self, lease_key, owner_id):
        self.leases.pop(lease_key, None)
        return True

    def advance_scheduled_task(self, task_id, *, last_run_at, last_run_id, next_run_at):
        self.advanced.append({
            "task_id": task_id,
            "last_run_id": last_run_id,
            "next_run_at": next_run_at,
        })
        return {}


def _make_task(task_id="task-1", cron_expr="* * * * *"):
    return {
        "id": task_id,
        "name": "test-task",
        "conversation_id": "conv-1",
        "message": "hello",
        "cron_expr": cron_expr,
        "enabled": True,
        "next_run_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
    }


@unittest.skipUnless(AVAILABLE, f"SchedulerService unavailable: {IMPORT_ERROR}")
class TestSchedulerService(unittest.IsolatedAsyncioTestCase):
    def _make_service(self, due_tasks=None, run_id="run-abc", raise_on_submit=False):
        fake_runtime = FakeRuntimeService(run_id=run_id, raise_on_submit=raise_on_submit)
        fake_db = FakeDbOps(due_tasks=due_tasks)
        service = SchedulerService(runtime_service=fake_runtime, poll_interval_seconds=9999, db_ops=fake_db)
        return service, fake_runtime, fake_db

    async def test_dispatch_calls_submit_run(self):
        service, fake_runtime, _ = self._make_service(due_tasks=[_make_task()])
        await service._tick()

        self.assertEqual(len(fake_runtime.submitted), 1)
        req = fake_runtime.submitted[0]
        self.assertEqual(req.conversation_id, "conv-1")
        self.assertEqual(req.message, "hello")

    async def test_dispatch_advances_next_run_at(self):
        service, _, fake_db = self._make_service(
            due_tasks=[_make_task(cron_expr="0 * * * *")],
            run_id="run-xyz",
        )
        await service._tick()

        self.assertEqual(len(fake_db.advanced), 1)
        adv = fake_db.advanced[0]
        self.assertEqual(adv["last_run_id"], "run-xyz")
        self.assertIsInstance(adv["next_run_at"], datetime)
        self.assertIsNotNone(adv["next_run_at"].tzinfo)

    async def test_dispatch_skipped_when_lease_held(self):
        task = _make_task()
        service, fake_runtime, fake_db = self._make_service(due_tasks=[task])
        # Pre-hold the lease
        fake_db.leases[f"scheduled_task:{task['id']}"] = "someone-else"

        await service._tick()

        self.assertEqual(len(fake_runtime.submitted), 0)
        self.assertEqual(len(fake_db.advanced), 0)

    async def test_dispatch_advances_even_on_submit_error(self):
        """next_run_at should still advance if submit_run raises; last_run_id is None."""
        service, _, fake_db = self._make_service(
            due_tasks=[_make_task()],
            raise_on_submit=True,
        )
        await service._tick()

        self.assertEqual(len(fake_db.advanced), 1)
        self.assertIsNone(fake_db.advanced[0]["last_run_id"])

    async def test_multiple_due_tasks_all_dispatched(self):
        tasks = [_make_task("task-1"), _make_task("task-2")]
        service, fake_runtime, fake_db = self._make_service(due_tasks=tasks)
        await service._tick()

        self.assertEqual(len(fake_runtime.submitted), 2)
        self.assertEqual(len(fake_db.advanced), 2)

    async def test_start_stop_lifecycle(self):
        service, _, _ = self._make_service(due_tasks=[])
        await service.start()
        self.assertIsNotNone(service._task)
        await service.stop()
        self.assertIsNone(service._task)

    async def test_stop_without_start_is_safe(self):
        service, _, _ = self._make_service()
        await service.stop()  # no-op


@unittest.skipUnless(AVAILABLE, f"SchedulerService unavailable: {IMPORT_ERROR}")
class TestNextRunAt(unittest.TestCase):
    def test_returns_future_datetime_with_timezone(self):
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        nxt = _next_run_at("0 * * * *", now=now)
        self.assertIsInstance(nxt, datetime)
        self.assertIsNotNone(nxt.tzinfo)
        self.assertGreater(nxt, now)

    def test_every_minute_cron_fires_60s_later(self):
        now = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        nxt = _next_run_at("* * * * *", now=now)
        delta = (nxt - now).total_seconds()
        self.assertAlmostEqual(delta, 60, delta=1)

    def test_no_now_uses_current_time(self):
        nxt = _next_run_at("* * * * *")
        self.assertGreater(nxt, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
