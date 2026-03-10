from __future__ import annotations

import json
import logging
from typing import List, NoReturn

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from backend.api.models import (
    ExternalTriggerCreate,
    ExternalTriggerResponse,
    ExternalTriggerUpdate,
    TriggerEventResponse,
)
from backend.database.operations import db_ops

logger = logging.getLogger(__name__)

trigger_router = APIRouter(prefix="/triggers", tags=["triggers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trigger_response(t: dict) -> ExternalTriggerResponse:
    config_raw = t.get("config")
    config = None
    if config_raw:
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            logger.warning(
                "Trigger config is not valid JSON — returning config=None",
                extra={"event": "trigger.config.decode_error", "trigger_id": t.get("id")},
            )
    return ExternalTriggerResponse(
        id=t["id"],
        type=t["type"],
        name=t["name"],
        conversation_id=t["conversation_id"],
        config=config,
        enabled=t["enabled"],
        created_at=t["created_at"],
        updated_at=t["updated_at"],
    )


def _event_response(e: dict) -> TriggerEventResponse:
    return TriggerEventResponse(
        id=e["id"],
        trigger_id=e["trigger_id"],
        external_event_id=e["external_event_id"],
        run_id=e.get("run_id"),
        received_at=e["received_at"],
        dispatched=e["dispatched"],
    )


def _handle_db_integrity_error(exc: IntegrityError, name: str, verb: str) -> NoReturn:
    orig = str(getattr(exc, "orig", exc)).lower()
    if "unique" in orig:
        raise HTTPException(status_code=409, detail=f"A trigger named {name!r} already exists")
    raise HTTPException(
        status_code=422,
        detail=f"Unable to {verb} trigger due to database constraint",
    )


# ---------------------------------------------------------------------------
# Webhook receivers (stubs)
# ---------------------------------------------------------------------------


@trigger_router.post("/telegram")
async def telegram_webhook(request: Request):
    """Telegram webhook receiver.

    Telegram calls this endpoint for every new message once the webhook URL
    is registered via the Bot API.  This stub logs the payload and returns 200.
    Real message parsing and dispatch land in #92.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    # Log only stable identifiers — avoid emitting message text or user IDs.
    logger.info(
        "Telegram webhook received",
        extra={
            "event": "trigger.webhook.telegram",
            "update_id": payload.get("update_id") if isinstance(payload, dict) else None,
            "has_message": isinstance(payload, dict) and "message" in payload,
        },
    )
    return {"status": "ok"}


@trigger_router.post("/email")
async def email_webhook(request: Request):
    """Gmail Pub/Sub push notification receiver.

    Google Pub/Sub delivers to this endpoint when mail arrives (after a Gmail
    API watch is registered).  This stub logs the payload and returns 200.
    Real email parsing and dispatch land in #91.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    # Log only stable identifiers — avoid emitting message content or base64 blobs.
    message_data = payload.get("message", {}) if isinstance(payload, dict) else {}
    logger.info(
        "Email webhook received",
        extra={
            "event": "trigger.webhook.email",
            "subscription": payload.get("subscription") if isinstance(payload, dict) else None,
            "message_id": message_data.get("messageId") if isinstance(message_data, dict) else None,
        },
    )
    return {"status": "ok"}


@trigger_router.post("/poll")
async def poll_sweep(request: Request):
    """Cloud Scheduler poll sweep endpoint.

    Cloud Scheduler calls this endpoint on a regular cadence to wake Cloud Run
    and trigger any polling-based checks (e.g., Gmail polling for new mail).
    This stub returns 200 immediately.  Actual poll logic lands in #91.
    """
    logger.info("Trigger poll sweep called", extra={"event": "trigger.poll"})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Trigger CRUD
# ---------------------------------------------------------------------------


@trigger_router.get("", response_model=List[ExternalTriggerResponse])
def list_triggers():
    """List all registered external triggers."""
    triggers = db_ops.list_external_triggers()
    return [_trigger_response(t) for t in triggers]


@trigger_router.post("", response_model=ExternalTriggerResponse, status_code=201)
def create_trigger(body: ExternalTriggerCreate):
    """Register a new external trigger."""
    config_json = json.dumps(body.config) if body.config is not None else None
    try:
        trigger = db_ops.create_external_trigger(
            type=body.type,
            name=body.name,
            conversation_id=body.conversation_id,
            config=config_json,
            enabled=body.enabled,
        )
    except IntegrityError as exc:
        _handle_db_integrity_error(exc, body.name, "create")  # always raises (NoReturn)
    except Exception:
        logger.exception("Failed to create external trigger")
        raise HTTPException(status_code=500, detail="Failed to create external trigger")
    return _trigger_response(trigger)  # type: ignore[possibly-undefined]  # trigger set in try


@trigger_router.get("/{trigger_id}", response_model=ExternalTriggerResponse)
def get_trigger(trigger_id: str):
    """Get a single external trigger by ID."""
    trigger = db_ops.get_external_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_response(trigger)


@trigger_router.patch("/{trigger_id}", response_model=ExternalTriggerResponse)
def update_trigger(trigger_id: str, body: ExternalTriggerUpdate):
    """Enable/disable or update a trigger."""
    updates = body.model_dump(exclude_none=True)
    if "config" in updates:
        updates["config"] = json.dumps(updates["config"])
    if not updates:
        trigger = db_ops.get_external_trigger(trigger_id)
        if not trigger:
            raise HTTPException(status_code=404, detail="Trigger not found")
        return _trigger_response(trigger)
    try:
        trigger = db_ops.update_external_trigger(trigger_id, **updates)
    except IntegrityError as exc:
        name = updates.get("name", trigger_id)
        _handle_db_integrity_error(exc, name, "update")  # always raises (NoReturn)
    if not trigger:  # type: ignore[possibly-undefined]  # trigger set in try
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_response(trigger)


@trigger_router.delete("/{trigger_id}", status_code=204)
def delete_trigger(trigger_id: str):
    """Delete an external trigger."""
    deleted = db_ops.delete_external_trigger(trigger_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trigger not found")


@trigger_router.get("/{trigger_id}/events", response_model=List[TriggerEventResponse])
def list_trigger_events(trigger_id: str, limit: int = 100):
    """Return the audit log of TriggerEvent rows for a trigger."""
    trigger = db_ops.get_external_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    events = db_ops.list_trigger_events(trigger_id, limit=limit)
    return [_event_response(e) for e in events]
