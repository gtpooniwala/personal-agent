from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from threading import RLock
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from backend.runtime.contracts import RunEventRecord, RunRecord, RUN_STATUS_QUEUED, utcnow


class RunStoreError(Exception):
    """Base runtime store error."""


class RunNotFoundError(RunStoreError):
    """Raised when a run cannot be found."""


class InvalidEventsCursorError(RunStoreError):
    """Raised when an events cursor is malformed."""


_UNSET = object()


class RunStore(ABC):
    @abstractmethod
    def create_run(self, *, conversation_id: str, message: str, selected_documents: Sequence[str]) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def update_run(self, *, run_id: str, status: str, error: Optional[str] = None, result: Optional[str] = None) -> RunRecord:
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

    def create_run(self, *, conversation_id: str, message: str, selected_documents: Sequence[str]) -> RunRecord:
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
    ) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                raise RunNotFoundError(f"Run '{run_id}' was not found")

            record.status = status
            record.updated_at = utcnow()
            if error is not _UNSET:
                record.error = error
            if result is not _UNSET:
                record.result = result
            return replace(record)

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
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
            )
            self._events[run_id].append(event)
            if len(self._events[run_id]) > self.MAX_EVENTS_PER_RUN:
                self._events[run_id] = self._events[run_id][-self.MAX_EVENTS_PER_RUN :]
            return replace(event)

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
            return [replace(evt) for evt in page], next_after, has_more

    def _prune_runs_locked(self) -> None:
        overflow = len(self._runs) - self.MAX_STORED_RUNS
        if overflow <= 0:
            return

        stale_run_ids = list(self._runs.keys())[:overflow]
        for stale_run_id in stale_run_ids:
            self._runs.pop(stale_run_id, None)
            self._events.pop(stale_run_id, None)


class SqliteRunStorePlaceholder(RunStore):
    # TODO(#15): Replace temporary in-memory run store with durable runs/run_events persistence.
    # TODO(postgres-migration): Implement Postgres-backed RunStore using DATABASE_URL and migration tables.
    def create_run(self, *, conversation_id: str, message: str, selected_documents: Sequence[str]) -> RunRecord:
        raise NotImplementedError("Durable SQLite run store will land with issue #15 schema work")

    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError("Durable SQLite run store will land with issue #15 schema work")

    def update_run(self, *, run_id: str, status: str, error: Optional[str] = None, result: Optional[str] = None) -> RunRecord:
        raise NotImplementedError("Durable SQLite run store will land with issue #15 schema work")

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
    ) -> RunEventRecord:
        raise NotImplementedError("Durable SQLite run store will land with issue #15 schema work")

    def list_events(self, *, run_id: str, after: Optional[str], limit: int) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        raise NotImplementedError("Durable SQLite run store will land with issue #15 schema work")


class PostgresRunStorePlaceholder(RunStore):
    # TODO(postgres-migration): Implement Postgres-backed RunStore using DATABASE_URL and migration tables.
    def create_run(self, *, conversation_id: str, message: str, selected_documents: Sequence[str]) -> RunRecord:
        raise NotImplementedError("Postgres run store will be wired in the migration PR")

    def get_run(self, run_id: str) -> RunRecord:
        raise NotImplementedError("Postgres run store will be wired in the migration PR")

    def update_run(self, *, run_id: str, status: str, error: Optional[str] = None, result: Optional[str] = None) -> RunRecord:
        raise NotImplementedError("Postgres run store will be wired in the migration PR")

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        tool: Optional[str] = None,
    ) -> RunEventRecord:
        raise NotImplementedError("Postgres run store will be wired in the migration PR")

    def list_events(self, *, run_id: str, after: Optional[str], limit: int) -> Tuple[List[RunEventRecord], Optional[str], bool]:
        raise NotImplementedError("Postgres run store will be wired in the migration PR")
