"""API-level tests for scheduler routes using FastAPI TestClient.

Patches db_ops at the route module level to avoid real DB connections.
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

AVAILABLE = True
IMPORT_ERROR = ""

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import IntegrityError
    # Import scheduler_routes module so patch target is resolvable
    import backend.api.scheduler_routes as scheduler_routes_module
except (ImportError, ModuleNotFoundError) as exc:
    AVAILABLE = False
    IMPORT_ERROR = str(exc)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _make_task_dict(task_id="task-1", name="my-task", enabled=True, cron_expr="0 * * * *"):
    now = datetime.now(timezone.utc)
    return {
        "id": task_id,
        "name": name,
        "conversation_id": "conv-1",
        "message": "hello",
        "cron_expr": cron_expr,
        "enabled": enabled,
        "next_run_at": (now + timedelta(hours=1)).isoformat(),
        "last_run_at": None,
        "last_run_id": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def _build_client(mock_db):
    """Create a TestClient with db_ops replaced by mock_db."""
    from backend.api.scheduler_routes import scheduler_router
    app = FastAPI()
    app.include_router(scheduler_router)
    with patch.object(scheduler_routes_module, "db_ops", mock_db):
        return TestClient(app, raise_server_exceptions=True)


@unittest.skipUnless(AVAILABLE, f"API test dependencies unavailable: {IMPORT_ERROR}")
class TestSchedulerRoutes(unittest.TestCase):
    def _mock_db(self, **overrides):
        db = MagicMock()
        db.list_scheduled_tasks.return_value = []
        db.get_scheduled_task.return_value = None
        db.create_scheduled_task.return_value = _make_task_dict()
        db.update_scheduled_task.return_value = _make_task_dict()
        db.delete_scheduled_task.return_value = False
        for k, v in overrides.items():
            getattr(db, k).return_value = v
        return db

    def test_list_tasks_empty(self):
        db = self._mock_db(list_scheduled_tasks=[])
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.get("/scheduler/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_tasks_returns_items(self):
        task = _make_task_dict()
        db = self._mock_db(list_scheduled_tasks=[task])
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.get("/scheduler/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_create_task_valid_cron(self):
        task = _make_task_dict()
        db = self._mock_db(create_scheduled_task=task)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.post("/scheduler/tasks", json={
                "name": "my-task",
                "conversation_id": "conv-1",
                "message": "hello",
                "cron_expr": "0 * * * *",
            })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "my-task")
        self.assertEqual(data["cron_expr"], "0 * * * *")

    def test_create_task_invalid_cron_returns_422(self):
        db = self._mock_db()
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/scheduler/tasks", json={
                "name": "bad-task",
                "conversation_id": "conv-1",
                "message": "hi",
                "cron_expr": "not-a-cron",
            })
        self.assertEqual(resp.status_code, 422)

    def test_get_task_not_found(self):
        db = self._mock_db(get_scheduled_task=None)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/scheduler/tasks/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_get_task_found(self):
        task = _make_task_dict(task_id="task-999", name="found-task")
        db = self._mock_db(get_scheduled_task=task)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.get("/scheduler/tasks/task-999")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "task-999")

    def test_patch_task_update(self):
        updated = _make_task_dict(enabled=False)
        db = self._mock_db(update_scheduled_task=updated)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.patch("/scheduler/tasks/task-1", json={"enabled": False})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["enabled"])

    def test_patch_task_invalid_cron(self):
        db = self._mock_db()
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.patch("/scheduler/tasks/task-1", json={"cron_expr": "bad"})
        self.assertEqual(resp.status_code, 422)

    def test_patch_task_not_found(self):
        db = self._mock_db(update_scheduled_task=None)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.patch("/scheduler/tasks/missing", json={"enabled": True})
        self.assertEqual(resp.status_code, 404)

    def test_patch_task_duplicate_name_returns_409(self):
        db = self._mock_db()
        db.update_scheduled_task.side_effect = IntegrityError("statement", "params", Exception("unique"))
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.patch("/scheduler/tasks/task-1", json={"name": "duplicate-task"})
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"])

    def test_delete_task_not_found(self):
        db = self._mock_db(delete_scheduled_task=False)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.delete("/scheduler/tasks/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_delete_task_success(self):
        db = self._mock_db(delete_scheduled_task=True)
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app)
            resp = client.delete("/scheduler/tasks/task-1")
        self.assertEqual(resp.status_code, 204)

    def test_create_task_duplicate_name_returns_409(self):
        db = self._mock_db()
        db.create_scheduled_task.side_effect = IntegrityError("statement", "params", Exception("unique"))
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/scheduler/tasks", json={
                "name": "duplicate",
                "conversation_id": "conv-1",
                "message": "hi",
                "cron_expr": "0 * * * *",
            })
        self.assertEqual(resp.status_code, 409)
        self.assertIn("duplicate", resp.json()["detail"])

    def test_create_task_unexpected_db_error_returns_500(self):
        db = self._mock_db()
        db.create_scheduled_task.side_effect = RuntimeError("db exploded")
        with patch.object(scheduler_routes_module, "db_ops", db):
            from backend.api.scheduler_routes import scheduler_router
            app = FastAPI()
            app.include_router(scheduler_router)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/scheduler/tasks", json={
                "name": "ok-task",
                "conversation_id": "conv-1",
                "message": "hi",
                "cron_expr": "0 * * * *",
            })
        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
