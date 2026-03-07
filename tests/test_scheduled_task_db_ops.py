"""DB integration tests for scheduled_tasks operations.

Requires TEST_DATABASE_URL env var pointing to a real Postgres instance.
Skipped automatically in unit-test-only CI runs.
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

AVAILABLE = bool(TEST_DATABASE_URL)
SKIP_REASON = "TEST_DATABASE_URL not set — skipping DB integration tests"

if AVAILABLE:
    try:
        import sqlalchemy  # noqa: F401
        from backend.database.operations import DatabaseOperations
        from backend.database.models import Base
    except (ImportError, ModuleNotFoundError) as exc:
        AVAILABLE = False
        SKIP_REASON = str(exc)


def _make_db():
    """Create a fresh DatabaseOperations pointing at the test database."""
    from backend.database.operations import DatabaseOperations
    return DatabaseOperations(database_url=TEST_DATABASE_URL)


def _utcnow():
    return datetime.now(timezone.utc)


@unittest.skipUnless(AVAILABLE, SKIP_REASON)
class TestScheduledTaskDbOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = _make_db()
        # Ensure the conversation required by FK exists
        cls.conversation_id = cls.db.create_conversation(title="test-scheduler-conv")

    def _unique_name(self, suffix=""):
        import uuid
        return f"test-task-{uuid.uuid4().hex[:8]}{suffix}"

    def _future(self, minutes=5):
        return _utcnow() + timedelta(minutes=minutes)

    def test_create_and_get(self):
        name = self._unique_name()
        task = self.db.create_scheduled_task(
            name=name,
            conversation_id=self.conversation_id,
            message="hello",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        self.assertEqual(task["name"], name)
        self.assertTrue(task["enabled"])

        fetched = self.db.get_scheduled_task(task["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], task["id"])

    def test_list_all_and_enabled_only(self):
        name_enabled = self._unique_name("-enabled")
        name_disabled = self._unique_name("-disabled")

        t1 = self.db.create_scheduled_task(
            name=name_enabled,
            conversation_id=self.conversation_id,
            message="msg",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        t2 = self.db.create_scheduled_task(
            name=name_disabled,
            conversation_id=self.conversation_id,
            message="msg",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        self.db.update_scheduled_task(t2["id"], enabled=False)

        all_tasks = self.db.list_scheduled_tasks()
        ids = [t["id"] for t in all_tasks]
        self.assertIn(t1["id"], ids)
        self.assertIn(t2["id"], ids)

        enabled_tasks = self.db.list_scheduled_tasks(enabled_only=True)
        enabled_ids = [t["id"] for t in enabled_tasks]
        self.assertIn(t1["id"], enabled_ids)
        self.assertNotIn(t2["id"], enabled_ids)

    def test_get_due_tasks(self):
        past = _utcnow() - timedelta(minutes=1)
        name = self._unique_name("-due")
        task = self.db.create_scheduled_task(
            name=name,
            conversation_id=self.conversation_id,
            message="due-msg",
            cron_expr="* * * * *",
            next_run_at=past,
        )
        due = self.db.get_due_scheduled_tasks(limit=100)
        due_ids = [t["id"] for t in due]
        self.assertIn(task["id"], due_ids)

    def test_advance_scheduled_task(self):
        name = self._unique_name("-advance")
        task = self.db.create_scheduled_task(
            name=name,
            conversation_id=self.conversation_id,
            message="msg",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        now = _utcnow()
        new_next = now + timedelta(hours=1)
        updated = self.db.advance_scheduled_task(
            task["id"],
            last_run_at=now,
            last_run_id="run-test-123",
            next_run_at=new_next,
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["last_run_id"], "run-test-123")

    def test_update_scheduled_task(self):
        name = self._unique_name("-update")
        task = self.db.create_scheduled_task(
            name=name,
            conversation_id=self.conversation_id,
            message="original",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        updated = self.db.update_scheduled_task(task["id"], message="updated", enabled=False)
        self.assertEqual(updated["message"], "updated")
        self.assertFalse(updated["enabled"])

    def test_delete_scheduled_task(self):
        name = self._unique_name("-delete")
        task = self.db.create_scheduled_task(
            name=name,
            conversation_id=self.conversation_id,
            message="msg",
            cron_expr="0 * * * *",
            next_run_at=self._future(),
        )
        result = self.db.delete_scheduled_task(task["id"])
        self.assertTrue(result)
        self.assertIsNone(self.db.get_scheduled_task(task["id"]))

    def test_delete_nonexistent_returns_false(self):
        result = self.db.delete_scheduled_task("nonexistent-id-xyz")
        self.assertFalse(result)

    def test_find_orphaned_runs_returns_list(self):
        # Just verify the query executes without error
        orphans = self.db.find_orphaned_runs()
        self.assertIsInstance(orphans, list)


if __name__ == "__main__":
    unittest.main()
