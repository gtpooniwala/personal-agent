from __future__ import annotations

from contextlib import contextmanager
import logging
import sys
from typing import Any, Dict, Optional

from backend.config import settings
from backend.observability.context import push_context

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - optional dependency fallback
    Langfuse = None


class _NoopObservation:
    """Safe no-op object when Langfuse is disabled or unavailable."""

    trace_id = ""

    def update(self, **kwargs: Any) -> None:
        return None


class LangfuseClientManager:
    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._disabled_reason: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def initialize(self) -> None:
        """Initialize Langfuse client once at startup."""

        if not settings.langfuse_enabled:
            self._disabled_reason = "LANGFUSE_ENABLED is false"
            logger.info("Langfuse observability disabled", extra={"event": "langfuse.disabled"})
            return

        if Langfuse is None:
            self._disabled_reason = "langfuse package not installed"
            logger.warning(
                "Langfuse package unavailable; tracing disabled",
                extra={"event": "langfuse.unavailable"},
            )
            return

        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            self._disabled_reason = "missing Langfuse credentials"
            logger.warning(
                "Langfuse credentials missing; tracing disabled",
                extra={"event": "langfuse.missing_credentials"},
            )
            return

        try:
            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
                sample_rate=settings.langfuse_sample_rate,
                tracing_enabled=settings.langfuse_enabled,
                environment=settings.environment,
                release="personal-agent",
            )
            logger.info("Langfuse client initialized", extra={"event": "langfuse.initialized"})
        except Exception:
            self._client = None
            self._disabled_reason = "initialization_failed"
            logger.exception(
                "Failed to initialize Langfuse client",
                extra={"event": "langfuse.init_failed"},
            )

    def flush(self) -> None:
        if not self._client:
            return
        try:
            self._client.flush()
        except Exception:
            logger.exception("Langfuse flush failed", extra={"event": "langfuse.flush_failed"})

    def shutdown(self) -> None:
        if not self._client:
            return
        try:
            self._client.shutdown()
        except Exception:
            logger.exception("Langfuse shutdown failed", extra={"event": "langfuse.shutdown_failed"})

    @contextmanager
    def observe(
        self,
        *,
        name: str,
        as_type: str = "span",
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        usage_details: Optional[Dict[str, int]] = None,
        conversation_id: Optional[str] = None,
    ):
        """Create a Langfuse observation context and auto-attach trace ID to logs."""

        if not self._client:
            with push_context(conversation_id=conversation_id):
                yield _NoopObservation()
            return

        kwargs: Dict[str, Any] = {
            "name": name,
            "as_type": as_type,
        }
        if input_data is not None:
            kwargs["input"] = input_data
        if output_data is not None:
            kwargs["output"] = output_data
        if metadata is not None:
            kwargs["metadata"] = metadata
        if model is not None:
            kwargs["model"] = model
        if usage_details is not None:
            kwargs["usage_details"] = usage_details

        try:
            observation_cm = self._client.start_as_current_observation(**kwargs)
        except Exception:
            logger.exception(
                "Langfuse observation setup failed; continuing without trace",
                extra={"event": "langfuse.observe_setup_failed"},
            )
            with push_context(conversation_id=conversation_id):
                yield _NoopObservation()
            return

        try:
            observation = observation_cm.__enter__()
        except Exception:
            logger.exception(
                "Langfuse observation start failed; continuing without trace",
                extra={"event": "langfuse.observe_start_failed"},
            )
            with push_context(conversation_id=conversation_id):
                yield _NoopObservation()
            return

        trace_id = str(getattr(observation, "trace_id", "") or "")
        try:
            with push_context(conversation_id=conversation_id, trace_id=trace_id):
                yield observation
        finally:
            exc_type, exc_value, exc_tb = sys.exc_info()
            try:
                observation_cm.__exit__(exc_type, exc_value, exc_tb)
            except Exception:
                logger.exception(
                    "Langfuse observation close failed",
                    extra={"event": "langfuse.observe_close_failed"},
                )


langfuse_manager = LangfuseClientManager()
