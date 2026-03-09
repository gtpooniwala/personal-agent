"""Runtime-level shared constants and helpers."""

from backend.runtime.contracts import (
    DEFAULT_EVENTS_LIMIT,
    MAX_EVENTS_LIMIT,
    RUN_STATUSES,
    RUN_TERMINAL_STATUSES,
)
from backend.runtime.store import (
    DbRunStore,
    InMemoryRunStore,
    InvalidEventsCursorError,
    PostgresRunStorePlaceholder,
    RunNotFoundError,
    RunStore,
    SqliteRunStorePlaceholder,
)
from .lifecycle import (
    RUN_EVENT_TYPES,
    RUN_EVENT_TYPE_SET,
    RUN_STATUS_SET,
    TERMINAL_RUN_STATUSES as LIFECYCLE_TERMINAL_RUN_STATUSES,
)
from .heartbeat import HeartbeatService
from .scheduler import SchedulerService


def __getattr__(name: str):
    if name == "ConversationMaintenanceService":
        from .conversation_maintenance import ConversationMaintenanceService
        return ConversationMaintenanceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ConversationMaintenanceService",
    "DEFAULT_EVENTS_LIMIT",
    "DbRunStore",
    "HeartbeatService",
    "InMemoryRunStore",
    "InvalidEventsCursorError",
    "MAX_EVENTS_LIMIT",
    "PostgresRunStorePlaceholder",
    "RunNotFoundError",
    "RunStore",
    "RUN_STATUSES",
    "RUN_TERMINAL_STATUSES",
    "RUN_STATUS_SET",
    "RUN_EVENT_TYPES",
    "RUN_EVENT_TYPE_SET",
    "SchedulerService",
    "SqliteRunStorePlaceholder",
]
