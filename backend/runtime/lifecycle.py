"""Canonical run lifecycle vocabulary shared by schema and API layers."""

from __future__ import annotations

RUN_STATUSES = (
    "queued",
    "running",
    "retrying",
    "succeeded",
    "failed",
    "cancelling",
    "cancelled",
)

TERMINAL_RUN_STATUSES = (
    "succeeded",
    "failed",
    "cancelled",
)

RUN_EVENT_TYPES = (
    "queued",
    "started",
    "tool_call",
    "tool_result",
    "retrying",
    "failed",
    "succeeded",
    "cancelling",
    "cancelled",
)

RUN_STATUS_SET = frozenset(RUN_STATUSES)
RUN_EVENT_TYPE_SET = frozenset(RUN_EVENT_TYPES)
