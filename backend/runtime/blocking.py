"""Helpers for offloading blocking work from async paths."""

from __future__ import annotations

import asyncio
import contextvars
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class BlockingCall:
    """Descriptor for one blocking function call."""

    func: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


async def offload_blocking_call(
    func: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run blocking work on a worker thread while preserving request context."""
    context = contextvars.copy_context()
    return await asyncio.to_thread(context.run, func, *args, **kwargs)


async def offload_blocking_calls(*calls: BlockingCall) -> tuple[Any, ...]:
    """Run independent blocking calls concurrently on worker threads."""
    results = await asyncio.gather(
        *[
            offload_blocking_call(call.func, *call.args, **call.kwargs)
            for call in calls
        ]
    )
    return tuple(results)
