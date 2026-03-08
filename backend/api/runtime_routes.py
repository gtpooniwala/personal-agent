from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.api.models import ChatRequest, RunEventsResponse, RunStatusResponse, RunSubmitResponse
from backend.api.sse import generate_run_sse
from backend.api.state import runtime_service
from backend.observability import observe_operation, update_observation
from backend.runtime import DEFAULT_EVENTS_LIMIT, MAX_EVENTS_LIMIT, InvalidEventsCursorError, RunNotFoundError

runtime_router = APIRouter()


@runtime_router.post("/chat", response_model=RunSubmitResponse)
async def submit_chat_run(request: ChatRequest):
    """Submit conversational work asynchronously and return a run handle."""
    with observe_operation(
        name="api.runtime.chat_submit",
        counter_prefix="api.runtime.chat_submit",
        as_type="chain",
        metadata={"component": "api", "endpoint": "/chat"},
    ) as observation:
        response_payload = await runtime_service.submit_run(request)
        update_observation(observation, output=response_payload)
        return RunSubmitResponse(**response_payload)


@runtime_router.post("/runs", response_model=RunSubmitResponse)
async def submit_run(request: ChatRequest):
    """Submit generic async work and return a run handle."""
    with observe_operation(
        name="api.runtime.runs_submit",
        counter_prefix="api.runtime.runs_submit",
        as_type="span",
        metadata={"component": "api", "endpoint": "/runs"},
    ) as observation:
        response_payload = await runtime_service.submit_run(request)
        update_observation(observation, output=response_payload)
        return RunSubmitResponse(**response_payload)


@runtime_router.get("/runs/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """Fetch the latest lifecycle snapshot for an asynchronous run."""
    payload = None
    not_found_error = None
    with observe_operation(
        name="api.runtime.run_status",
        counter_prefix="api.runtime.run_status",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/runs/{run_id}/status", "run_id": run_id},
    ) as observation:
        try:
            payload = await runtime_service.get_run_status(run_id)
        except RunNotFoundError as exc:
            not_found_error = exc
        else:
            update_observation(observation, output={"status": payload["status"]})

    if not_found_error is not None:
        raise HTTPException(status_code=404, detail=str(not_found_error)) from not_found_error
    return RunStatusResponse(**payload)


@runtime_router.get("/runs/{run_id}/events", response_model=RunEventsResponse)
async def get_run_events(
    run_id: str,
    after: Optional[str] = Query(default=None, description="Return events after this cursor"),
    limit: int = Query(default=DEFAULT_EVENTS_LIMIT, ge=1, le=MAX_EVENTS_LIMIT),
):
    """Fetch an ordered page of run events using cursor-based pagination."""
    payload = None
    not_found_error = None
    invalid_cursor_error = None
    with observe_operation(
        name="api.runtime.run_events",
        counter_prefix="api.runtime.run_events",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/runs/{run_id}/events", "run_id": run_id},
        input_data={"after": after, "limit": limit},
    ) as observation:
        try:
            payload = await runtime_service.get_run_events(run_id=run_id, after=after, limit=limit)
        except RunNotFoundError as exc:
            not_found_error = exc
        except InvalidEventsCursorError as exc:
            invalid_cursor_error = exc
        else:
            update_observation(observation, output={"events_count": len(payload.get("events", []))})

    if not_found_error is not None:
        raise HTTPException(status_code=404, detail=str(not_found_error)) from not_found_error
    if invalid_cursor_error is not None:
        raise HTTPException(status_code=400, detail=str(invalid_cursor_error)) from invalid_cursor_error
    return RunEventsResponse(**payload)


@runtime_router.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str, request: Request):
    """Stream ordered run events over SSE without changing the run ledger contract."""
    payload = None
    not_found_error = None
    with observe_operation(
        name="api.runtime.run_stream",
        counter_prefix="api.runtime.run_stream",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/runs/{run_id}/stream", "run_id": run_id},
    ) as observation:
        try:
            payload = await runtime_service.get_run_status(run_id)
        except RunNotFoundError as exc:
            not_found_error = exc
        else:
            update_observation(observation, output={"status": payload["status"], "stream": "opened"})

    if not_found_error is not None:
        raise HTTPException(status_code=404, detail=str(not_found_error)) from not_found_error

    # TODO(#121): Extract shared replay/polling mechanics once the polling and SSE transports can share one adapter.
    # TODO(#122): Keep this additive until the frontend prefers SSE with polling fallback.
    return StreamingResponse(
        generate_run_sse(
            runtime_service=runtime_service,
            run_id=run_id,
            is_disconnected=request.is_disconnected,
            initial_status=payload,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# TODO(#16): Attach cancellation endpoint + worker-queue cancellation handling here.
