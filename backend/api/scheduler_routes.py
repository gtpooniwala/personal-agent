from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from backend.api.models import ScheduledTaskCreate, ScheduledTaskResponse, ScheduledTaskUpdate
from backend.database.operations import db_ops
from backend.runtime.scheduler import _next_run_at

logger = logging.getLogger(__name__)

scheduler_router = APIRouter(prefix="/scheduler/tasks", tags=["scheduler"])


def _validate_cron(cron_expr: str) -> None:
    from croniter import croniter
    if not croniter.is_valid(cron_expr):
        raise HTTPException(status_code=422, detail=f"Invalid cron expression: {cron_expr!r}")


def _task_response(task: dict) -> ScheduledTaskResponse:
    return ScheduledTaskResponse(
        id=task["id"],
        name=task["name"],
        conversation_id=task["conversation_id"],
        message=task["message"],
        cron_expr=task["cron_expr"],
        enabled=task["enabled"],
        next_run_at=task["next_run_at"],
        last_run_at=task.get("last_run_at"),
        last_run_id=task.get("last_run_id"),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@scheduler_router.get("", response_model=List[ScheduledTaskResponse])
def list_tasks():
    tasks = db_ops.list_scheduled_tasks()
    return [_task_response(t) for t in tasks]


@scheduler_router.post("", response_model=ScheduledTaskResponse, status_code=201)
def create_task(body: ScheduledTaskCreate):
    _validate_cron(body.cron_expr)
    next_run = _next_run_at(body.cron_expr)
    try:
        task = db_ops.create_scheduled_task(
            name=body.name,
            conversation_id=body.conversation_id,
            message=body.message,
            cron_expr=body.cron_expr,
            next_run_at=next_run,
        )
    except IntegrityError as exc:
        orig = str(getattr(exc, "orig", exc)).lower()
        if "unique" in orig:
            raise HTTPException(status_code=409, detail=f"A scheduled task named {body.name!r} already exists")
        logger.exception("Integrity constraint violation creating scheduled task")
        raise HTTPException(status_code=422, detail="Database constraint violation")
    except Exception:
        logger.exception("Failed to create scheduled task")
        raise HTTPException(status_code=500, detail="Failed to create scheduled task")
    return _task_response(task)


@scheduler_router.get("/{task_id}", response_model=ScheduledTaskResponse)
def get_task(task_id: str):
    task = db_ops.get_scheduled_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return _task_response(task)


@scheduler_router.patch("/{task_id}", response_model=ScheduledTaskResponse)
def update_task(task_id: str, body: ScheduledTaskUpdate):
    updates = body.model_dump(exclude_none=True)
    if "cron_expr" in updates:
        _validate_cron(updates["cron_expr"])
        updates["next_run_at"] = _next_run_at(updates["cron_expr"])
    if not updates:
        task = db_ops.get_scheduled_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        return _task_response(task)
    task = db_ops.update_scheduled_task(task_id, **updates)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return _task_response(task)


@scheduler_router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str):
    deleted = db_ops.delete_scheduled_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
