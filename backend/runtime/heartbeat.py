from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ORPHAN_ERROR_MESSAGE = "Run abandoned: process crashed or lease expired"


class HeartbeatService:
    """Background service that detects orphaned runs and marks them failed."""

    def __init__(self, run_store=None, poll_interval_seconds: int = 60, db_ops=None):
        # run_store kept for API compatibility; db_ops is injected for testability.
        self._db_ops = db_ops
        self._poll_interval = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None

    def _get_db_ops(self):
        if self._db_ops is not None:
            return self._db_ops
        from backend.database.operations import db_ops
        return db_ops

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
            try:
                db.update_run(run_id=run_id, status=RUN_STATUS_FAILED, error=ORPHAN_ERROR_MESSAGE)
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
