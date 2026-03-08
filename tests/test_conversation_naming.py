"""Unit tests for check_conversation_maintenance and async_generate_title."""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

NAMING_TESTS_AVAILABLE = True
NAMING_IMPORT_ERROR = ""
try:
    from backend.api.routes import (
        check_conversation_maintenance,
        async_generate_title,
        _NAMING_DELAY_MINUTES,
        _NAMING_MAX_RETRIES,
        _NAMING_RETRY_DELAY_MINUTES,
    )
    from backend.database.operations import UNTITLED_CONVERSATION_PREFIXES
except Exception as exc:
    NAMING_TESTS_AVAILABLE = False
    NAMING_IMPORT_ERROR = str(exc)


def _make_conv(
    *,
    conversation_id="conv-1",
    title="Conversation abc",
    message_count=2,
    updated_minutes_ago=10,
    created_days_ago=0,
):
    """Helper to build a minimal conversation dict."""
    now = datetime.now()
    updated_at = now - timedelta(minutes=updated_minutes_ago)
    created_at = now - timedelta(days=created_days_ago)
    return {
        "id": conversation_id,
        "title": title,
        "message_count": message_count,
        "updated_at": updated_at.isoformat() + "Z",
        "created_at": created_at.isoformat() + "Z",
    }


@unittest.skipUnless(
    NAMING_TESTS_AVAILABLE, f"Naming test dependencies unavailable: {NAMING_IMPORT_ERROR}"
)
def _close_coro(coro):
    """Side-effect for mocked asyncio.create_task: close the coroutine to avoid ResourceWarning."""
    coro.close()


class TestCheckConversationMaintenance(unittest.TestCase):
    """Tests for check_conversation_maintenance scheduling logic."""

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_schedules_title_generation_for_untitled_old_enough(self, mock_create_task):
        conv = _make_conv(
            title=UNTITLED_CONVERSATION_PREFIXES[0] + "xyz",
            message_count=1,
            updated_minutes_ago=_NAMING_DELAY_MINUTES + 1,
        )
        check_conversation_maintenance([conv])
        mock_create_task.assert_called_once()

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_skips_title_generation_when_too_recent(self, mock_create_task):
        conv = _make_conv(
            title=UNTITLED_CONVERSATION_PREFIXES[0] + "xyz",
            message_count=1,
            updated_minutes_ago=0,  # just updated
        )
        check_conversation_maintenance([conv])
        mock_create_task.assert_not_called()

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_skips_title_generation_when_already_titled(self, mock_create_task):
        conv = _make_conv(
            title="My custom title",
            message_count=2,
            updated_minutes_ago=_NAMING_DELAY_MINUTES + 5,
        )
        check_conversation_maintenance([conv])
        mock_create_task.assert_not_called()

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_skips_title_generation_when_no_messages(self, mock_create_task):
        conv = _make_conv(
            title=UNTITLED_CONVERSATION_PREFIXES[0] + "xyz",
            message_count=0,
            updated_minutes_ago=_NAMING_DELAY_MINUTES + 5,
        )
        check_conversation_maintenance([conv])
        mock_create_task.assert_not_called()

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_schedules_deletion_for_old_empty_conversation(self, mock_create_task):
        conv = _make_conv(
            title="Conversation old",
            message_count=0,
            created_days_ago=2,
        )
        check_conversation_maintenance([conv])
        mock_create_task.assert_called_once()

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_all_untitled_prefixes_trigger_scheduling(self, mock_create_task):
        convs = [
            _make_conv(
                conversation_id=f"conv-{i}",
                title=prefix + "x",
                message_count=1,
                updated_minutes_ago=_NAMING_DELAY_MINUTES + 5,
            )
            for i, prefix in enumerate(UNTITLED_CONVERSATION_PREFIXES)
        ]
        check_conversation_maintenance(convs)
        self.assertEqual(mock_create_task.call_count, len(UNTITLED_CONVERSATION_PREFIXES))

    @patch("backend.api.routes.asyncio.create_task", side_effect=_close_coro)
    def test_empty_list_does_nothing(self, mock_create_task):
        check_conversation_maintenance([])
        mock_create_task.assert_not_called()


@unittest.skipUnless(
    NAMING_TESTS_AVAILABLE, f"Naming test dependencies unavailable: {NAMING_IMPORT_ERROR}"
)
class TestAsyncGenerateTitle(unittest.IsolatedAsyncioTestCase):
    """Tests for async_generate_title retry loop."""

    @patch("backend.api.routes.db_ops")
    @patch("backend.api.routes.orchestrator")
    async def test_returns_immediately_on_success(self, mock_orch, mock_db):
        mock_orch.generate_conversation_title = AsyncMock(return_value="Great Title")
        await async_generate_title("conv-1")
        mock_orch.generate_conversation_title.assert_awaited_once_with("conv-1")

    @patch("backend.api.routes.asyncio.sleep", new_callable=AsyncMock)
    @patch("backend.api.routes.asyncio.to_thread", new_callable=AsyncMock)
    @patch("backend.api.routes.orchestrator")
    async def test_exits_early_when_conversation_already_titled_between_retries(
        self, mock_orch, mock_to_thread, mock_sleep
    ):
        # First attempt returns empty; between retries, is_conversation_untitled returns False.
        mock_orch.generate_conversation_title = AsyncMock(return_value="")
        mock_to_thread.return_value = False  # already titled

        await async_generate_title("conv-1")

        mock_orch.generate_conversation_title.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    @patch("backend.api.routes.asyncio.sleep", new_callable=AsyncMock)
    @patch("backend.api.routes.asyncio.to_thread", new_callable=AsyncMock)
    @patch("backend.api.routes.orchestrator")
    async def test_retries_after_empty_result_and_succeeds(
        self, mock_orch, mock_to_thread, mock_sleep
    ):
        # First attempt empty, second attempt succeeds.
        mock_orch.generate_conversation_title = AsyncMock(
            side_effect=["", "My Title"]
        )
        mock_to_thread.return_value = True  # still untitled

        await async_generate_title("conv-1")

        self.assertEqual(mock_orch.generate_conversation_title.await_count, 2)
        mock_sleep.assert_awaited_once_with(_NAMING_RETRY_DELAY_MINUTES * 60)

    @patch("backend.api.routes.asyncio.sleep", new_callable=AsyncMock)
    @patch("backend.api.routes.asyncio.to_thread", new_callable=AsyncMock)
    @patch("backend.api.routes.orchestrator")
    async def test_exhausts_retries_on_repeated_exception_and_returns(
        self, mock_orch, mock_to_thread, mock_sleep
    ):
        # All attempts raise exceptions; should not propagate.
        mock_orch.generate_conversation_title = AsyncMock(
            side_effect=RuntimeError("llm error")
        )
        mock_to_thread.return_value = True

        # Should not raise.
        await async_generate_title("conv-1")

        self.assertEqual(
            mock_orch.generate_conversation_title.await_count, _NAMING_MAX_RETRIES
        )


if __name__ == "__main__":
    unittest.main()
