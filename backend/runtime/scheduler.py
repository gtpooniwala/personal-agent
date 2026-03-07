from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _next_run_at(cron_expr: str, now: Optional[datetime] = None) -> datetime:
    from croniter import croniter

    base = now or datetime.now(timezone.utc)
    # croniter works with naive datetimes; feed UTC and re-attach tz.
    naive_base = base.replace(tzinfo=None)
    nxt = croniter(cron_expr, naive_base).get_next(datetime)
    return nxt.replace(tzinfo=timezone.utc)


class _SchedulerRequest:
    """Minimal stand-in for ChatRequest accepted by RuntimeService.submit_run."""

    def __init__(self, *, conversation_id: str, message: str):
        self.conversation_id = conversation_id
        self.message = message
        self.selected_documents: list = []


class SchedulerService:
    """Background service that fires agent runs on cron schedules."""

    def __init__(self, runtime_service, poll_interval_seconds: int = 30, db_ops=None):
        self._runtime_service = runtime_service
        self._poll_interval = poll_interval_seconds
        self._db_ops = db_ops
        self._task: Optional[asyncio.Task] = None

    def _get_db_ops(self):
        if self._db_ops is not None:
            return self._db_ops
        from backend.database.operations import db_ops
        return db_ops

    async def start(self) -> None:
        logger.info("SchedulerService starting", extra={"event": "scheduler.start"})
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        logger.info("SchedulerService stopping", extra={"event": "scheduler.stop"})
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SchedulerService tick error", extra={"event": "scheduler.tick_error"})

    async def _tick(self) -> None:
        db = self._get_db_ops()
        try:
            due = db.get_due_scheduled_tasks(limit=50)
        except Exception:
            logger.exception("SchedulerService failed to query due tasks", extra={"event": "scheduler.query_error"})
            return

        for task in due:
            await self._dispatch(task)

    async def _dispatch(self, task: Dict[str, Any]) -> None:
        db = self._get_db_ops()
        task_id = str(task["id"])
        lease_key = f"scheduled_task:{task_id}"
        owner_id = str(uuid.uuid4())

        # Prevent double-dispatch across concurrent workers
        lease = db.acquire_lease(lease_key, owner_id, ttl_seconds=120)
        if lease is None:
            logger.info(
                "Skipping task — dispatch lease held by another worker",
                extra={"event": "scheduler.task_skipped", "task_id": task_id},
            )
            return

        now = datetime.now(timezone.utc)
        run_id: Optional[str] = None

        try:
            request = _SchedulerRequest(
                conversation_id=str(task["conversation_id"]),
                message=str(task["message"]),
            )
            result = await self._runtime_service.submit_run(request)
            run_id = result["run_id"]
            logger.info(
                "Scheduled task dispatched",
                extra={"event": "scheduler.task_dispatched", "task_id": task_id, "run_id": run_id},
            )
        except Exception:
            logger.exception(
                "Scheduled task dispatch failed",
                extra={"event": "scheduler.task_dispatch_error", "task_id": task_id},
            )

        # Always advance next_run_at to prevent tight re-dispatch loop on failure
        try:
            next_run = _next_run_at(str(task["cron_expr"]), now)
            db.advance_scheduled_task(
                task_id,
                last_run_at=now,
                last_run_id=run_id or "",
                next_run_at=next_run,
            )
        except Exception:
            logger.exception(
                "Failed to advance scheduled task",
                extra={"event": "scheduler.task_advance_error", "task_id": task_id},
            )

        db.release_lease(lease_key, owner_id)
