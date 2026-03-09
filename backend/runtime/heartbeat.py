from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Optional

from backend.runtime.contracts import utcnow

logger = logging.getLogger(__name__)

ORPHAN_ERROR_MESSAGE = "Run abandoned: process crashed or lease expired"


class HeartbeatService:
    """Background service that detects orphaned runs and marks them failed."""

    def __init__(self, poll_interval_seconds: int = 60, db_ops=None, run_store=None):
        self._db_ops = db_ops
        self._run_store = run_store
        self._poll_interval = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None

    def _get_db_ops(self):
        if self._db_ops is not None:
            return self._db_ops
        from backend.database.operations import db_ops
        return db_ops

    @staticmethod
    def _supports_completed_at(update_run) -> bool:
        try:
            parameters = inspect.signature(update_run).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "completed_at":
                return True
        return False

    async def start(self) -> None:
        logger.info("HeartbeatService starting", extra={"event": "heartbeat.start"})
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        logger.info("HeartbeatService stopping", extra={"event": "heartbeat.stop"})
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        # Run one sweep immediately on startup to clear pre-existing orphans.
        await self._sweep()
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._sweep()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("HeartbeatService sweep error", extra={"event": "heartbeat.sweep_error"})

    async def _sweep(self) -> None:
        from backend.runtime.contracts import RUN_EVENT_FAILED, RUN_STATUS_FAILED

        db = self._get_db_ops()
        try:
            orphans = db.find_orphaned_runs()
        except Exception:
            logger.exception("HeartbeatService failed to query orphaned runs", extra={"event": "heartbeat.query_error"})
            return

        if not orphans:
            return

        logger.info(
            "HeartbeatService found orphaned runs",
            extra={"event": "heartbeat.orphans_found", "count": len(orphans)},
        )

        for run in orphans:
            run_id = str(run["id"])
            run_status = (run.get("status") or "").lower()
            if run_status not in {"running", "retrying"}:
                continue

            current = db.get_run(run_id)
            if not current:
                continue
            if (current.get("status") or "").lower() not in {"running", "retrying"}:
                logger.info(
                    "Skipping terminal run in orphan sweep",
                    extra={"event": "heartbeat.orphan_skip", "run_id": run_id},
                )
                continue

            try:
                update_kwargs = {
                    "run_id": run_id,
                    "status": RUN_STATUS_FAILED,
                    "error": ORPHAN_ERROR_MESSAGE,
                }
                if self._supports_completed_at(db.update_run):
                    update_kwargs["completed_at"] = utcnow()
                db.update_run(**update_kwargs)
                db.append_run_event(
                    run_id=run_id,
                    event_type=RUN_EVENT_FAILED,
                    status=RUN_STATUS_FAILED,
                    message=ORPHAN_ERROR_MESSAGE,
                )
                logger.info(
                    "Marked orphaned run as failed",
                    extra={"event": "heartbeat.run_failed", "run_id": run_id},
                )
            except Exception:
                logger.exception(
                    "Failed to mark orphaned run",
                    extra={"event": "heartbeat.run_fail_error", "run_id": run_id},
                )
