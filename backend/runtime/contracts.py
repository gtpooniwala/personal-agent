from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_RETRYING = "retrying"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLING = "cancelling"
RUN_STATUS_CANCELLED = "cancelled"

# TODO(#15): bind these contracts to durable runs/run_events tables.
# TODO(postgres-migration): verify enum/storage mapping for PostgreSQL.
RUN_STATUSES: Sequence[str] = (
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_RETRYING,
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_FAILED,
    RUN_STATUS_CANCELLING,
    RUN_STATUS_CANCELLED,
)

RUN_TERMINAL_STATUSES = {
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_FAILED,
    RUN_STATUS_CANCELLED,
}

RUN_EVENT_QUEUED = "queued"
RUN_EVENT_STARTED = "started"
RUN_EVENT_TOOL_CALL = "tool_call"
RUN_EVENT_TOOL_RESULT = "tool_result"
RUN_EVENT_RETRYING = "retrying"
RUN_EVENT_FAILED = "failed"
RUN_EVENT_SUCCEEDED = "succeeded"
RUN_EVENT_CANCELLED = "cancelled"

RUN_EVENT_TYPES: Sequence[str] = (
    RUN_EVENT_QUEUED,
    RUN_EVENT_STARTED,
    RUN_EVENT_TOOL_CALL,
    RUN_EVENT_TOOL_RESULT,
    RUN_EVENT_RETRYING,
    RUN_EVENT_FAILED,
    RUN_EVENT_SUCCEEDED,
    RUN_EVENT_CANCELLED,
)

DEFAULT_EVENTS_LIMIT = 50
MAX_EVENTS_LIMIT = 200


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RunRecord:
    run_id: str
    conversation_id: str
    status: str
    message: str
    selected_documents: Sequence[str] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    error: Optional[str] = None
    result: Optional[str] = None

    def to_status_payload(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "conversation_id": self.conversation_id,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
            "error": self.error,
            "result": self.result,
        }


@dataclass
class RunEventRecord:
    event_id: str
    run_id: str
    type: str
    status: str
    message: str
    created_at: datetime
    tool: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event_id": self.event_id,
            "type": self.type,
            "status": self.status,
            "message": self.message,
            "created_at": isoformat_utc(self.created_at),
            "tool": self.tool,
            "metadata": self.metadata,
        }
        return payload
