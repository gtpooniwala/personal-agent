"""Unit tests for ConversationMaintenanceService."""

import asyncio
import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.runtime.conversation_maintenance import ConversationMaintenanceService


class FakeDbOps:
    def __init__(self):
        self.title_candidates = []
        self.empty_candidates = []
        self.deleted = []
        self.released = []
        self._leases = {}
        self._untitled = {}
        self._history = {}
        self._untitled_errors = set()

    def find_conversations_needing_title(self, *, delay_minutes, limit):
        return list(self.title_candidates)

    def find_stale_empty_conversations(self, *, older_than_days, limit):
        return list(self.empty_candidates)

    def acquire_lease(self, lease_key, owner_id, ttl_seconds):
        if lease_key in self._leases:
            return None
        self._leases[lease_key] = owner_id
        return {"lease_key": lease_key, "owner_id": owner_id}

    def release_lease(self, lease_key, owner_id):
        self.released.append((lease_key, owner_id))
        if self._leases.get(lease_key) == owner_id:
            del self._leases[lease_key]
            return True
        return False

    def is_conversation_untitled(self, conversation_id):
        if conversation_id in self._untitled_errors:
            raise RuntimeError("db down")
        return self._untitled.get(conversation_id, True)

    def get_conversation_history(self, conversation_id):
        return list(self._history.get(conversation_id, []))

    def delete_conversation(self, conversation_id):
        self.deleted.append(conversation_id)
        return True


@contextmanager
def _noop_observation(*args, **kwargs):
    yield None


class TestConversationMaintenanceService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = FakeDbOps()
        self.orchestrator = type("Orchestrator", (), {})()
        self.orchestrator.generate_conversation_title = AsyncMock(return_value=None)
        self._counter_patcher = patch(
            "backend.runtime.conversation_maintenance.increment_counter"
        )
        self._observe_patcher = patch(
            "backend.runtime.conversation_maintenance.observe_operation",
            _noop_observation,
        )
        self._counter_patcher.start()
        self._observe_patcher.start()
        self.service = ConversationMaintenanceService(
            orchestrator=self.orchestrator,
            poll_interval_seconds=9999,
            db_ops=self.db,
        )

    async def asyncTearDown(self):
        await self.service.stop()
        self._counter_patcher.stop()
        self._observe_patcher.stop()

    async def _drain_background_tasks(self):
        pending = list(self.service._background_tasks)
        if pending:
            await asyncio.gather(*pending)

    async def test_sweep_generates_titles_for_stale_untitled_conversations(self):
        self.db.title_candidates = [{"id": "conv-1"}]
        self.db._untitled["conv-1"] = False
        self.orchestrator.generate_conversation_title = AsyncMock(
            return_value="Generated Title"
        )

        await self.service._sweep()
        await self._drain_background_tasks()

        self.orchestrator.generate_conversation_title.assert_awaited_once_with("conv-1")
        self.assertTrue(
            any(
                lease_key == "conversation-maintenance:title:conv-1"
                for lease_key, _ in self.db.released
            )
        )

    async def test_sweep_deletes_stale_empty_conversations(self):
        self.db.empty_candidates = [{"id": "conv-empty"}]

        await self.service._sweep()
        await self._drain_background_tasks()

        self.assertEqual(self.db.deleted, ["conv-empty"])
        self.assertTrue(
            any(
                lease_key == "conversation-maintenance:delete:conv-empty"
                for lease_key, _ in self.db.released
            )
        )

    async def test_title_retry_stops_cleanly_when_state_check_fails(self):
        self.db.title_candidates = [{"id": "conv-err"}]
        self.db._untitled_errors.add("conv-err")

        await self.service._sweep()
        await self._drain_background_tasks()

        self.orchestrator.generate_conversation_title.assert_awaited_once_with("conv-err")
        self.assertEqual(self.db.deleted, [])
        self.assertTrue(
            any(
                lease_key == "conversation-maintenance:title:conv-err"
                for lease_key, _ in self.db.released
            )
        )

    async def test_delete_skips_conversation_that_gained_messages(self):
        self.db.empty_candidates = [{"id": "conv-now-active"}]
        self.db._history["conv-now-active"] = [{"id": "msg-1", "content": "hi"}]

        await self.service._sweep()
        await self._drain_background_tasks()

        self.assertEqual(self.db.deleted, [])
        self.assertTrue(
            any(
                lease_key == "conversation-maintenance:delete:conv-now-active"
                for lease_key, _ in self.db.released
            )
        )

    async def test_start_stop_lifecycle(self):
        await self.service.start()
        self.assertIsNotNone(self.service._task)
        await self.service.stop()
        self.assertIsNone(self.service._task)


if __name__ == "__main__":
    unittest.main()
