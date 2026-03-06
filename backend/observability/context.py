from __future__ import annotations

from contextlib import contextmanager
import contextvars
from typing import Dict, Optional

_request_id_var = contextvars.ContextVar("request_id", default="")
_conversation_id_var = contextvars.ContextVar("conversation_id", default="")
_route_var = contextvars.ContextVar("route", default="")
_trace_id_var = contextvars.ContextVar("trace_id", default="")


@contextmanager
def push_context(
    *,
    request_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    route: Optional[str] = None,
    trace_id: Optional[str] = None,
):
    """Temporarily attach context fields for logs/traces in the current task context."""

    tokens = []
    if request_id is not None:
        tokens.append((_request_id_var, _request_id_var.set(request_id)))
    if conversation_id is not None:
        tokens.append((_conversation_id_var, _conversation_id_var.set(conversation_id)))
    if route is not None:
        tokens.append((_route_var, _route_var.set(route)))
    if trace_id is not None:
        tokens.append((_trace_id_var, _trace_id_var.set(trace_id)))

    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def get_log_context() -> Dict[str, str]:
    """Return current request-scoped context for structured logging."""

    context = {
        "request_id": _request_id_var.get() or "",
        "conversation_id": _conversation_id_var.get() or "",
        "route": _route_var.get() or "",
        "trace_id": _trace_id_var.get() or "",
    }
    return context
