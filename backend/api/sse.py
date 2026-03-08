from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

from backend.runtime import MAX_EVENTS_LIMIT
from backend.runtime.contracts import RUN_TERMINAL_STATUSES

SSE_POLL_INTERVAL_SECONDS = 0.25
SSE_HEARTBEAT_INTERVAL_SECONDS = 15.0


def format_sse(event_type: str, payload: Dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def build_run_event_payload(run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "event_id": event["event_id"],
        "event_type": event["type"],
        "status": event["status"],
        "timestamp": event["created_at"],
        "payload": {
            "message": event["message"],
            "tool": event.get("tool"),
            "metadata": event.get("metadata"),
        },
    }


def build_run_complete_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": status["run_id"],
        "conversation_id": status["conversation_id"],
        "status": status["status"],
        "timestamp": status["updated_at"],
        "result": status.get("result"),
        "error": status.get("error"),
    }


async def generate_run_sse(
    *,
    runtime_service,
    run_id: str,
    is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
    initial_status: Optional[Dict[str, Any]] = None,
    poll_interval_seconds: float = SSE_POLL_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = SSE_HEARTBEAT_INTERVAL_SECONDS,
    events_limit: int = MAX_EVENTS_LIMIT,
) -> AsyncIterator[str]:
    status = initial_status or await runtime_service.get_run_status(run_id)
    after = None
    last_sent_at = monotonic()

    async def client_disconnected() -> bool:
        if is_disconnected is None:
            return False
        return await is_disconnected()

    async def drain_new_events(cursor: Optional[str]) -> tuple[list[str], Optional[str], int]:
        emitted = 0
        chunks: list[str] = []
        while True:
            page = await runtime_service.get_run_events(
                run_id=run_id,
                after=cursor,
                limit=events_limit,
            )
            events = page["events"]
            if not events:
                return chunks, cursor, emitted

            for event in events:
                chunks.append(format_sse("run_event", build_run_event_payload(run_id, event)))
                emitted += 1
                cursor = event["event_id"]

            if not page["has_more"]:
                return chunks, cursor, emitted

    while True:
        if await client_disconnected():
            return

        chunks, after, _ = await drain_new_events(after)
        for chunk in chunks:
            yield chunk
            last_sent_at = monotonic()

        status = await runtime_service.get_run_status(run_id)
        if status["status"] in RUN_TERMINAL_STATUSES:
            final_chunks, after, final_emitted = await drain_new_events(after)
            for chunk in final_chunks:
                yield chunk
                last_sent_at = monotonic()

            if final_emitted == 0:
                yield format_sse("run_complete", build_run_complete_payload(status))
                return
            continue

        if monotonic() - last_sent_at >= heartbeat_interval_seconds:
            yield format_sse("heartbeat", {})
            last_sent_at = monotonic()

        await asyncio.sleep(poll_interval_seconds)
