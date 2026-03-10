"""Unit tests for TriggerDispatcher."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.runtime.trigger_dispatcher import TriggerDispatcher, _TriggerRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_db_ops(
    *,
    existing_event=None,
    lease_acquired=True,
    trigger_event_row=None,
    run_id="run-abc",
):
    db = MagicMock()
    db.get_trigger_event.return_value = existing_event
    db.acquire_lease.return_value = {"lease_key": "k"} if lease_acquired else None
    db.create_trigger_event.return_value = trigger_event_row or {
        "id": "te-1",
        "trigger_id": "trigger-1",
        "external_event_id": "ext-1",
        "run_id": None,
        "received_at": "2026-01-01T00:00:00+00:00",
        "dispatched": False,
    }
    db.mark_trigger_event_dispatched.return_value = None
    db.release_lease.return_value = True
    return db


def _make_runtime(run_id: str = "run-abc"):
    rt = MagicMock()
    rt.submit_run = AsyncMock(return_value={"run_id": run_id})
    return rt


# ---------------------------------------------------------------------------
# Tests: basic dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_creates_run():
    """First call dispatches and returns a run_id."""
    trigger = _make_trigger()
    db = _make_db_ops()
    rt = _make_runtime(run_id="run-abc")
    dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

    result = await dispatcher.dispatch(
        trigger, message="hello", external_event_id="ext-1"
    )

    assert result == "run-abc"
    db.create_trigger_event.assert_called_once_with(
        trigger_id="trigger-1",
        external_event_id="ext-1",
        dispatched=False,
    )
    db.mark_trigger_event_dispatched.assert_called_once_with("te-1", "run-abc")
    db.release_lease.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_dedup_skips_existing_event():
    """Second call with same external_event_id is skipped (dedup=True)."""
    trigger = _make_trigger()
    existing = {
        "id": "te-1",
        "trigger_id": "trigger-1",
        "external_event_id": "ext-1",
        "run_id": "run-abc",
        "received_at": "2026-01-01T00:00:00+00:00",
        "dispatched": True,
    }
    db = _make_db_ops(existing_event=existing)
    rt = _make_runtime()
    dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

    result = await dispatcher.dispatch(
        trigger, message="hello", external_event_id="ext-1", dedup=True
    )

    assert result is None
    rt.submit_run.assert_not_called()
    db.create_trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_dedup_false_bypasses_dedup_check():
    """dedup=False skips the existing-event check and always dispatches."""
    trigger = _make_trigger()
    db = _make_db_ops()
    rt = _make_runtime(run_id="run-new")
    dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

    result = await dispatcher.dispatch(
        trigger, message="hello", external_event_id="ext-1", dedup=False
    )

    assert result == "run-new"
    db.get_trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_returns_none_when_lease_not_acquired():
    """Returns None without creating a run if the dispatch lease is held."""
    trigger = _make_trigger()
    db = _make_db_ops(lease_acquired=False)
    rt = _make_runtime()
    dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

    result = await dispatcher.dispatch(
        trigger, message="hello", external_event_id="ext-1"
    )

    assert result is None
    rt.submit_run.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_returns_none_when_submit_run_raises():
    """Returns None if RuntimeService.submit_run raises; TriggerEvent row exists."""
    trigger = _make_trigger()
    db = _make_db_ops()
    rt = MagicMock()
    rt.submit_run = AsyncMock(side_effect=RuntimeError("backend down"))
    dispatcher = TriggerDispatcher(runtime_service=rt, db_ops=db)

    result = await dispatcher.dispatch(
        trigger, message="hello", external_event_id="ext-1"
    )

    assert result is None
    # TriggerEvent row was created but mark_dispatched was not called
    db.create_trigger_event.assert_called_once()
    db.mark_trigger_event_dispatched.assert_not_called()
    # Lease is always released
    db.release_lease.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _resolve_conversation stub
# ---------------------------------------------------------------------------


def test_resolve_conversation_returns_trigger_default():
    """Stub always returns the trigger's conversation_id."""
    trigger = _make_trigger(conversation_id="conv-xyz")
    dispatcher = TriggerDispatcher(runtime_service=MagicMock(), db_ops=MagicMock())
    result = dispatcher._resolve_conversation(trigger, {})
    assert result == "conv-xyz"


# ---------------------------------------------------------------------------
# Tests: _TriggerRequest
# ---------------------------------------------------------------------------


def test_trigger_request_attributes():
    req = _TriggerRequest(conversation_id="conv-1", message="do something")
    assert req.conversation_id == "conv-1"
    assert req.message == "do something"
    assert req.selected_documents == []
