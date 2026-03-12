from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from backend.runtime.contracts import (
    RunEventRecord,
    RunRecord,
    RUN_STATUS_QUEUED,
    RUN_TERMINAL_STATUSES,
    utcnow,
)


class RunStoreError(Exception):
    """Base runtime store error."""


class RunNotFoundError(RunStoreError):
    """Raised when a run cannot be found."""


class InvalidEventsCursorError(RunStoreError):
    """Raised when an events cursor is malformed."""


_UNSET = object()


class RunStore(ABC):
    @abstractmethod
    def create_run(
        self, *, conversation_id: str, message: str, selected_documents: Sequence[str]
    ) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def update_run(
        self,
        *,
        run_id: str,
        status: str,
        error: Any = _UNSET,
        result: Any = _UNSET,
        attempt_count: Optional[int] = None,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
    ) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunEventRecord:
        raise NotImplementedError

    @abstractmethod
    def list_events(
        self,
        *,
        run_id: str,
        after: Optional[str],
        limit: int,
    ) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        raise NotImplementedError


class InMemoryRunStore(RunStore):
    # TODO(#15): Replace temporary in-memory run store with durable runs/run_events persistence.
    MAX_STORED_RUNS = 500
    MAX_EVENTS_PER_RUN = 1000

    def __init__(self):
        self._runs: Dict[str, RunRecord] = {}
        self._events: Dict[str, List[RunEventRecord]] = {}
        self._event_sequence = 0
        self._lock = RLock()

    def create_run(
        self, *, conversation_id: str, message: str, selected_documents: Sequence[str]
    ) -> RunRecord:
        with self._lock:
            run_id = str(uuid4())
            now = utcnow()
            record = RunRecord(
                run_id=run_id,
                conversation_id=conversation_id,
                status=RUN_STATUS_QUEUED,
                message=message,
                selected_documents=tuple(selected_documents),
                created_at=now,
                updated_at=now,
            )
            self._runs[run_id] = record
            self._events[run_id] = []
            self._prune_runs_locked()
            return replace(record)

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                raise RunNotFoundError(f"Run '{run_id}' was not found")
            return replace(record)

    def update_run(
        self,
        *,
        run_id: str,
        status: str,
        error: Optional[str] = _UNSET,
        result: Optional[str] = _UNSET,
        attempt_count: Optional[int] = None,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
        ) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                raise RunNotFoundError(f"Run '{run_id}' was not found")
            if attempt_count is not None and attempt_count < 0:
                raise ValueError("attempt_count must be non-negative")
            if started_at is not _UNSET:
                self._validate_optional_timestamp("started_at", started_at)
            if completed_at is not _UNSET:
                self._validate_optional_timestamp("completed_at", completed_at)

            record.status = status
            record.updated_at = utcnow()
            if error is not _UNSET:
                record.error = error
            if result is not _UNSET:
                record.result = result
            if attempt_count is not None:
                record.attempt_count = attempt_count
            if started_at is not _UNSET:
                record.started_at = started_at
            if completed_at is not _UNSET:
                record.completed_at = completed_at
            self._prune_runs_locked()
            return replace(record)

    @staticmethod
    def _validate_optional_timestamp(field_name: str, value: Any) -> None:
        if value is not None and not (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.tzinfo.utcoffset(value) is not None
        ):
            raise ValueError(f"{field_name} must be a timezone-aware datetime or None")

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunEventRecord:
        with self._lock:
            if run_id not in self._runs:
                raise RunNotFoundError(f"Run '{run_id}' was not found")

            self._event_sequence += 1
            event = RunEventRecord(
                event_id=str(self._event_sequence),
                run_id=run_id,
                type=event_type,
                status=status,
                message=message,
                tool=tool,
                created_at=utcnow(),
                metadata=deepcopy(metadata) if metadata is not None else None,
            )
            self._events[run_id].append(event)
            if len(self._events[run_id]) > self.MAX_EVENTS_PER_RUN:
                self._events[run_id] = self._events[run_id][-self.MAX_EVENTS_PER_RUN :]
            return replace(
                event,
                metadata=deepcopy(event.metadata) if event.metadata is not None else None,
            )

    def list_events(
        self,
        *,
        run_id: str,
        after: Optional[str],
        limit: int,
    ) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        with self._lock:
            if run_id not in self._runs:
                raise RunNotFoundError(f"Run '{run_id}' was not found")

            events = self._events.get(run_id, [])
            if after is None:
                start_idx = 0
            else:
                try:
                    after_int = int(after)
                except ValueError as exc:
                    raise InvalidEventsCursorError("Invalid events cursor") from exc

                start_idx = 0
                for idx, event in enumerate(events):
                    if int(event.event_id) > after_int:
                        start_idx = idx
                        break
                else:
                    start_idx = len(events)

            page = events[start_idx : start_idx + limit]
            has_more = start_idx + limit < len(events)
            next_after = page[-1].event_id if page else after
            return [
                replace(
                    evt,
                    metadata=deepcopy(evt.metadata) if evt.metadata is not None else None,
                )
                for evt in page
            ], next_after, has_more

    def _prune_runs_locked(self) -> None:
        overflow = len(self._runs) - self.MAX_STORED_RUNS
        if overflow <= 0:
            return

        # Only prune terminal runs to avoid deleting active executions
        terminal_statuses = RUN_TERMINAL_STATUSES
        stale_run_ids = [
            run_id
            for run_id in list(self._runs.keys())
            if self._runs[run_id].status in terminal_statuses
        ][:overflow]
        for stale_run_id in stale_run_ids:
            self._runs.pop(stale_run_id, None)
            self._events.pop(stale_run_id, None)


class SqliteRunStorePlaceholder(RunStore):
    # TODO(#15): Replace temporary in-memory run store with durable runs/run_events persistence.
    # TODO(postgres-migration): Implement Postgres-backed RunStore using DATABASE_URL and migration tables.
    def create_run(
        self, *, conversation_id: str, message: str, selected_documents: Sequence[str]
    ) -> RunRecord:
        raise NotImplementedError(
            "Durable SQLite run store will land with issue #15 schema work"
        )

    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError(
            "Durable SQLite run store will land with issue #15 schema work"
        )

    def update_run(
        self,
        *,
        run_id: str,
        status: str,
        error: Any = _UNSET,
        result: Any = _UNSET,
        attempt_count: Optional[int] = None,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
    ) -> RunRecord:
        raise NotImplementedError(
            "Durable SQLite run store will land with issue #15 schema work"
        )

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunEventRecord:
        raise NotImplementedError(
            "Durable SQLite run store will land with issue #15 schema work"
        )

    def list_events(
        self, *, run_id: str, after: Optional[str], limit: int
    ) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        raise NotImplementedError(
            "Durable SQLite run store will land with issue #15 schema work"
        )


class DbRunStore(RunStore):
    """Database-backed run store using durable persistence."""

    def __init__(self):
        from backend.database.operations import db_ops

        self._db_ops = db_ops

    def create_run(
        self, *, conversation_id: str, message: str, selected_documents: Sequence[str]
    ) -> RunRecord:
        db_record = self._db_ops.create_run(conversation_id=conversation_id)
        return RunRecord(
            run_id=str(db_record["id"]),
            conversation_id=db_record["conversation_id"],
            status=db_record["status"],
            message=message,
            selected_documents=tuple(selected_documents),
            attempt_count=db_record["attempt_count"],
            created_at=self._parse_iso(db_record["created_at"]),
            updated_at=self._parse_iso(db_record["updated_at"]),
            started_at=self._parse_iso(db_record["started_at"]),
            completed_at=self._parse_iso(db_record["completed_at"]),
            error=db_record["error"],
            result=db_record["result"],
        )

    def get_run(self, run_id: str) -> RunRecord:
        if not run_id or not isinstance(run_id, str):
            raise RunNotFoundError(f"Invalid run_id: {run_id!r}")
        db_record = self._db_ops.get_run(run_id)
        if db_record is None:
            raise RunNotFoundError(f"Run '{run_id}' was not found")
        return RunRecord(
            run_id=str(db_record["id"]),
            conversation_id=db_record["conversation_id"],
            status=db_record["status"],
            # TODO: Store message and selected_documents in DB (requires schema change).
            # Currently only available at creation time via create_run return value.
            message="",
            selected_documents=tuple(),
            attempt_count=db_record["attempt_count"],
            created_at=self._parse_iso(db_record["created_at"]),
            updated_at=self._parse_iso(db_record["updated_at"]),
            started_at=self._parse_iso(db_record["started_at"]),
            completed_at=self._parse_iso(db_record["completed_at"]),
            error=db_record["error"],
            result=db_record["result"],
        )

    def update_run(
        self,
        *,
        run_id: str,
        status: str,
        error: Optional[str] = _UNSET,
        result: Optional[str] = _UNSET,
        attempt_count: Optional[int] = None,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
    ) -> RunRecord:
        # Build kwargs for db_ops, only including explicitly-set fields
        update_kwargs = {"run_id": run_id, "status": status}
        if error is not _UNSET:
            update_kwargs["error"] = error
        if result is not _UNSET:
            update_kwargs["result"] = result
        if attempt_count is not None:
            update_kwargs["attempt_count"] = attempt_count
        if started_at is not _UNSET:
            update_kwargs["started_at"] = started_at
        if completed_at is not _UNSET:
            update_kwargs["completed_at"] = completed_at

        db_record = self._db_ops.update_run(**update_kwargs)
        if db_record is None:
            raise RunNotFoundError(f"Run '{run_id}' was not found")
        return RunRecord(
            run_id=str(db_record["id"]),
            conversation_id=db_record["conversation_id"],
            status=db_record["status"],
            message="",
            selected_documents=tuple(),
            attempt_count=db_record["attempt_count"],
            created_at=self._parse_iso(db_record["created_at"]),
            updated_at=self._parse_iso(db_record["updated_at"]),
            started_at=self._parse_iso(db_record["started_at"]),
            completed_at=self._parse_iso(db_record["completed_at"]),
            error=db_record["error"],
            result=db_record["result"],
        )

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunEventRecord:
        # Verify run exists before appending event
        if not self._db_ops.get_run(run_id):
            raise RunNotFoundError(f"Run '{run_id}' was not found")

        db_event = self._db_ops.append_run_event(
            run_id=run_id,
            event_type=event_type,
            status=status,
            message=message,
            tool=tool,
            metadata=metadata,
        )
        return RunEventRecord(
            event_id=str(db_event["id"]),
            run_id=db_event["run_id"],
            type=db_event["type"],
            status=db_event["status"],
            message=db_event["message"],
            created_at=self._parse_iso(db_event["created_at"]),
            tool=db_event.get("tool"),
            metadata=db_event.get("metadata"),
        )

    def list_events(
        self,
        *,
        run_id: str,
        after: Optional[str],
        limit: int,
    ) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        # Verify run exists before listing events
        if not self._db_ops.get_run(run_id):
            raise RunNotFoundError(f"Run '{run_id}' was not found")

        after_event_id = None
        if after is not None:
            try:
                after_event_id = int(after)
            except ValueError as exc:
                raise InvalidEventsCursorError("Invalid events cursor") from exc

        # Fetch one extra to determine if there are more events
        db_events = self._db_ops.list_run_events(
            run_id=run_id, after_event_id=after_event_id, limit=limit + 1
        )

        # Determine if there are more events beyond the requested limit
        has_more = len(db_events) > limit

        # Trim to requested limit
        db_events = db_events[:limit]

        events = [
            RunEventRecord(
                event_id=str(event["id"]),
                run_id=event["run_id"],
                type=event["type"],
                status=event["status"],
                message=event["message"],
                created_at=self._parse_iso(event["created_at"]),
                tool=event.get("tool"),
                metadata=event.get("metadata"),
            )
            for event in db_events
        ]

        next_after = events[-1].event_id if events else after
        return events, next_after, has_more

    @staticmethod
    def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
        if iso_str is None:
            return None
        # Parse ISO format string, handling both Z and +00:00 suffixes
        try:
            if iso_str.endswith("Z"):
                iso_str = iso_str[:-1] + "+00:00"
            return datetime.fromisoformat(iso_str)
        except ValueError as exc:
            raise ValueError(f"Failed to parse ISO datetime: {iso_str!r}") from exc


class PostgresRunStorePlaceholder(RunStore):
    # TODO(postgres-migration): Implement Postgres-backed RunStore using DATABASE_URL and migration tables.
    def create_run(
        self, *, conversation_id: str, message: str, selected_documents: Sequence[str]
    ) -> RunRecord:
        raise NotImplementedError(
            "Postgres run store will be wired in the migration PR"
        )

    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError(
            "Postgres run store will be wired in the migration PR"
        )

    def update_run(
        self,
        *,
        run_id: str,
        status: str,
        error: Any = _UNSET,
        result: Any = _UNSET,
        attempt_count: Optional[int] = None,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
    ) -> RunRecord:
        raise NotImplementedError(
            "Postgres run store will be wired in the migration PR"
        )

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunEventRecord:
        raise NotImplementedError(
            "Postgres run store will be wired in the migration PR"
        )

    def list_events(
        self, *, run_id: str, after: Optional[str], limit: int
    ) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        raise NotImplementedError(
            "Postgres run store will be wired in the migration PR"
        )
