from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.config import dictConfig
from typing import Any, Dict

from backend.observability.context import get_log_context


class JsonFormatter(logging.Formatter):
    """JSON formatter with request/tracing context for reliable parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
        }

        payload.update(get_log_context())

        # Add common optional fields if provided via logger extra.
        optional_fields = (
            "method",
            "path",
            "status_code",
            "latency_ms",
            "error_type",
            "counter_key",
            "counter_value",
        )
        for field in optional_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def configure_logging(log_level: str) -> None:
    """Configure app-wide structured JSON logging."""

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "backend.observability.logging.JsonFormatter",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": log_level.upper(),
            },
        }
    )
