from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class _TriggerRequest:
    """Minimal stand-in for ChatRequest accepted by RuntimeService.submit_run."""

    def __init__(self, *, conversation_id: str, message: str):
        self.conversation_id = conversation_id
        self.message = message
        self.selected_documents: list = []


class TriggerDispatcher:
    """Dispatch external trigger events as normal runtime runs.

    Mirrors the SchedulerService pattern: calls RuntimeService.submit_run()
    and records deduplication state in TriggerEvent rows.
    """

    DISPATCH_LEASE_TTL_SECONDS: int = 120

    def __init__(self, runtime_service, db_ops=None):
        self._runtime_service = runtime_service
        self._db_ops = db_ops

    def _get_db_ops(self):
        if self._db_ops is not None:
            return self._db_ops
        from backend.database.operations import db_ops
        return db_ops

    def _resolve_conversation(
        self,
        trigger: Dict[str, Any],
        event_metadata: Dict[str, Any],
    ) -> str:
        """Return the conversation_id to inject the event into.

        TODO: Define workflow matching logic here.
        The matching algorithm should inspect event_metadata (e.g., Telegram
        reply_to_message_id, Gmail thread_id, webhook correlation_id) and
        compare against recent TriggerEvent rows to determine if this event
        continues an existing workflow.

        Until that logic is defined, this function always returns the trigger's
        default conversation_id, which causes every trigger event to start a
        new workflow.

        STUB: always falls through to new workflow — replace with real matching.
        """
        return str(trigger["conversation_id"])

    async def dispatch(
        self,
        trigger: Dict[str, Any],
        message: str,
        external_event_id: str,
        *,
        event_metadata: Optional[Dict[str, Any]] = None,
        dedup: bool = True,
    ) -> Optional[str]:
        """Dispatch an external event as a normal runtime run.

        Returns the run_id on successful dispatch. Returns None when no run is
        started — either because the event was deduplicated (already dispatched),
        or due to an operational failure such as a lease conflict, a submit_run
        failure, or a post-lease database error. Pre-lease DB calls
        (get_trigger_event, acquire_lease) are not wrapped in try/except and
        will propagate to the caller on transient DB failure. Callers should
        treat None as "no run started" and rely on structured logging to
        distinguish specific causes.

        Args:
            trigger: Serialized ExternalTrigger dict (from db_ops).
            message: Prompt string to inject as the user message.
            external_event_id: Stable ID from the external system for dedup.
                The (trigger_id, external_event_id) pair must be unique per
                logical event. Reusing the same value across distinct events
                will be rejected by the database unique constraint.
            event_metadata: Optional metadata for workflow matching in
                _resolve_conversation() — not used by the stub.
            dedup: If True (default), check for an existing TriggerEvent row.
                Only skip dispatch if that row has dispatched=True (already
                succeeded). A row with dispatched=False means a previous
                attempt failed; the dispatcher retries it. If False, the
                application-level check is skipped entirely, but the database
                unique constraint on (trigger_id, external_event_id) still
                applies. A duplicate insert is caught internally, logged, and
                causes the method to return None without dispatching a run.
        """
        db = self._get_db_ops()
        trigger_id = str(trigger["id"])
        meta = event_metadata or {}

        existing_event_row: Optional[Dict[str, Any]] = None

        if dedup:
            existing_event_row = db.get_trigger_event(trigger_id, external_event_id)
            if existing_event_row and existing_event_row.get("dispatched"):
                logger.info(
                    "Trigger event already dispatched — skipping",
                    extra={
                        "event": "trigger.dispatch.deduped",
                        "trigger_id": trigger_id,
                        "external_event_id": external_event_id,
                    },
                )
                return None

        # Acquire a dispatch lease to prevent double-dispatch across concurrent workers.
        lease_key = f"trigger_event:{trigger_id}:{external_event_id}"
        owner_id = str(uuid.uuid4())
        lease = db.acquire_lease(lease_key, owner_id, ttl_seconds=self.DISPATCH_LEASE_TTL_SECONDS)
        if lease is None:
            logger.info(
                "Trigger dispatch lease held by another worker — skipping",
                extra={
                    "event": "trigger.dispatch.lease_conflict",
                    "trigger_id": trigger_id,
                    "external_event_id": external_event_id,
                },
            )
            return None

        trigger_event_row: Optional[Dict[str, Any]] = None
        run_id: Optional[str] = None

        try:
            # Re-check dispatch state after acquiring the lease to close the race window
            # between the pre-lease dedup read and the point where we hold the lock.
            # Another worker may have dispatched successfully in that gap.
            # Run unconditionally when dedup=True: a concurrent worker may have
            # created AND dispatched a row even if no row existed pre-lease.
            if dedup:
                refreshed = db.get_trigger_event(trigger_id, external_event_id)
                if refreshed and refreshed.get("dispatched"):
                    logger.info(
                        "Trigger event dispatched by concurrent worker — skipping",
                        extra={
                            "event": "trigger.dispatch.deduped_post_lease",
                            "trigger_id": trigger_id,
                            "external_event_id": external_event_id,
                        },
                    )
                    return None
                existing_event_row = refreshed or existing_event_row

            # Reuse an existing undispatched row (retry path) or create a new one.
            if existing_event_row:
                trigger_event_row = existing_event_row
            else:
                try:
                    trigger_event_row = db.create_trigger_event(
                        trigger_id=trigger_id,
                        external_event_id=external_event_id,
                        dispatched=False,
                    )
                except IntegrityError:
                    # Duplicate-key collision in the race window — another worker
                    # created this row between our post-lease re-check and now.
                    # Log at warning (no stack trace needed; this is expected).
                    logger.warning(
                        "Trigger event row already exists — concurrent insert race",
                        extra={
                            "event": "trigger.dispatch.event_create_duplicate",
                            "trigger_id": trigger_id,
                            "external_event_id": external_event_id,
                        },
                    )
                    return None
                except Exception:
                    logger.exception(
                        "Failed to create trigger event row",
                        extra={
                            "event": "trigger.dispatch.event_create_error",
                            "trigger_id": trigger_id,
                            "external_event_id": external_event_id,
                        },
                    )
                    return None

            conversation_id = self._resolve_conversation(trigger, meta)

            try:
                request = _TriggerRequest(
                    conversation_id=conversation_id,
                    message=message,
                )
                result = await self._runtime_service.submit_run(request)
                run_id = result["run_id"]
                logger.info(
                    "Trigger event dispatched",
                    extra={
                        "event": "trigger.dispatch.dispatched",
                        "trigger_id": trigger_id,
                        "external_event_id": external_event_id,
                        "run_id": run_id,
                    },
                )
            except Exception:
                logger.exception(
                    "Trigger event dispatch failed",
                    extra={
                        "event": "trigger.dispatch.error",
                        "trigger_id": trigger_id,
                        "external_event_id": external_event_id,
                    },
                )
                return None

            # Mark the TriggerEvent as dispatched.
            # If this fails, return None rather than run_id: the dedup row remains
            # at dispatched=False with no run_id, so a future retry would see the
            # undispatched row and attempt dispatch again (creating a duplicate run).
            # Returning None signals an unconfirmed dispatch; the run IS running but
            # dedup state is uncommitted.
            try:
                db.mark_trigger_event_dispatched(trigger_event_row["id"], run_id)
            except Exception:
                logger.exception(
                    "Failed to mark trigger event dispatched — dedup state uncommitted",
                    extra={
                        "event": "trigger.dispatch.mark_error",
                        "trigger_id": trigger_id,
                        "external_event_id": external_event_id,
                        "run_id": run_id,
                    },
                )
                return None

            return run_id

        finally:
            try:
                released = db.release_lease(lease_key, owner_id)
                if not released:
                    logger.warning(
                        "Dispatch lease not released — may have expired and been re-acquired",
                        extra={
                            "event": "trigger.dispatch.lease_release_not_owned",
                            "trigger_id": trigger_id,
                            "external_event_id": external_event_id,
                        },
                    )
            except Exception:
                logger.exception(
                    "Failed to release trigger dispatch lease",
                    extra={
                        "event": "trigger.dispatch.lease_release_error",
                        "trigger_id": trigger_id,
                        "external_event_id": external_event_id,
                    },
                )
