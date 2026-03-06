from __future__ import annotations

from contextlib import contextmanager
import logging
from time import perf_counter
from typing import Any, Dict, Optional

from backend.database.operations import db_ops
from backend.observability.langfuse_client import langfuse_manager

logger = logging.getLogger(__name__)


def increment_counter(key: str, amount: int = 1) -> None:
    """Increment runtime counter without allowing observability failures to break requests."""

    try:
        value = db_ops.increment_runtime_counter(key=key, amount=amount)
        logger.debug(
            "Counter incremented",
            extra={
                "event": "counter.incremented",
                "counter_key": key,
                "counter_value": value,
            },
        )
    except Exception:
        logger.exception(
            "Failed to increment runtime counter",
            extra={"event": "counter.increment_failed", "counter_key": key},
        )


def update_observation(observation: Any, **kwargs: Any) -> None:
    """Safely update a Langfuse observation."""

    if observation is None:
        return
    update_fn = getattr(observation, "update", None)
    if not callable(update_fn):
        return

    try:
        update_fn(**kwargs)
    except Exception:
        logger.exception(
            "Failed to update Langfuse observation",
            extra={"event": "langfuse.update_failed"},
        )


@contextmanager
def observe_operation(
    *,
    name: str,
    counter_prefix: Optional[str] = None,
    as_type: str = "span",
    input_data: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
):
    """Unified wrapper for Langfuse observations + runtime counters + latency metrics."""

    if counter_prefix:
        increment_counter(f"{counter_prefix}.requests_total")

    start = perf_counter()

    with langfuse_manager.observe(
        name=name,
        as_type=as_type,
        input_data=input_data,
        metadata=metadata,
        conversation_id=conversation_id,
    ) as observation:
        try:
            yield observation
            if counter_prefix:
                increment_counter(f"{counter_prefix}.success_total")
        except Exception as exc:
            if counter_prefix:
                increment_counter(f"{counter_prefix}.error_total")
            update_observation(
                observation,
                status_message=str(exc),
                metadata={"error_type": type(exc).__name__},
            )
            raise
        finally:
            latency_ms = int((perf_counter() - start) * 1000)
            if counter_prefix:
                increment_counter(f"{counter_prefix}.latency_ms_total", amount=latency_ms)
            update_observation(observation, metadata={"latency_ms": latency_ms})
