#!/usr/bin/env python3
"""Runtime eval harness for run lifecycle, retries, and session isolation."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import types
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "tests" / "runtime_evals" / "results"

# ---------------------------------------------------------------------------
# Inject a stub for backend.database.operations BEFORE any backend imports.
# This prevents DatabaseOperations() from attempting a DB connection at import
# time (which would fail in environments without a live database).
# ---------------------------------------------------------------------------
_STUB_DB_MODULE_NAME = "backend.database.operations"
if _STUB_DB_MODULE_NAME not in sys.modules:
    _stub_db_module = types.ModuleType(_STUB_DB_MODULE_NAME)

    class _StubDbOps:
        """Minimal no-op stub so module-level imports in tracking.py succeed."""

        def acquire_lease(self, key: str, owner_id: str, ttl_seconds: int) -> Optional[Dict[str, str]]:
            return None

        def release_lease(self, key: str, owner_id: str) -> None:
            pass

        def renew_lease(self, key: str, owner_id: str, ttl_seconds: int) -> None:
            return None

        def increment_runtime_counter(self, key: str, amount: int = 1) -> int:
            return 0

    _stub_db_module.db_ops = _StubDbOps()  # type: ignore[attr-defined]
    _stub_db_module.DatabaseOperations = type("DatabaseOperations", (), {})  # type: ignore[attr-defined]
    sys.modules[_STUB_DB_MODULE_NAME] = _stub_db_module

# ---------------------------------------------------------------------------
# Import runtime dependencies — any failure → exit 2
# ---------------------------------------------------------------------------
_IMPORT_ERROR: Optional[str] = None
RuntimeService = None
InMemoryRunStore = None
SESSION_BUSY_MESSAGE = None
RUN_STATUS_SUCCEEDED = RUN_STATUS_FAILED = None
RUN_TERMINAL_STATUSES = None
RUN_EVENT_QUEUED = RUN_EVENT_STARTED = RUN_EVENT_RETRYING = None
RUN_EVENT_FAILED = RUN_EVENT_SUCCEEDED = None

try:
    from backend.runtime.service import RuntimeService, SESSION_BUSY_MESSAGE  # type: ignore[assignment]
    from backend.runtime.store import InMemoryRunStore  # type: ignore[assignment]
    from backend.runtime.contracts import (
        RUN_STATUS_SUCCEEDED,  # type: ignore[assignment]
        RUN_STATUS_FAILED,  # type: ignore[assignment]
        RUN_TERMINAL_STATUSES,  # type: ignore[assignment]
        RUN_EVENT_QUEUED,  # type: ignore[assignment]
        RUN_EVENT_STARTED,  # type: ignore[assignment]
        RUN_EVENT_RETRYING,  # type: ignore[assignment]
        RUN_EVENT_FAILED,  # type: ignore[assignment]
        RUN_EVENT_SUCCEEDED,  # type: ignore[assignment]
    )
except Exception as exc:
    _IMPORT_ERROR = f"Failed to import runtime dependencies: {exc}"


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockDbOps:
    """In-memory lease management used to replace db_ops during eval cases."""

    def __init__(self) -> None:
        self._leases: Dict[str, str] = {}

    def acquire_lease(self, key: str, owner_id: str, ttl_seconds: int) -> Optional[Dict[str, str]]:
        if key not in self._leases:
            self._leases[key] = owner_id
            return {"key": key, "owner_id": owner_id}
        return None

    def release_lease(self, key: str, owner_id: str) -> None:
        if self._leases.get(key) == owner_id:
            del self._leases[key]

    def renew_lease(self, key: str, owner_id: str, ttl_seconds: int) -> Optional[Dict[str, str]]:
        if self._leases.get(key) == owner_id:
            return {"key": key, "owner_id": owner_id}
        return None

    def increment_runtime_counter(self, key: str, amount: int = 1) -> int:
        return 0


class MockOrchestrator:
    """Configurable orchestrator: each call pops the next response spec."""

    def __init__(self, responses: List[Tuple[str, Any]]) -> None:
        # responses: list of ("success", result_str) | ("error", msg) | ("raise", exc)
        self._responses = list(responses)
        self._index = 0
        self._call_count = 0

    def create_conversation(self) -> str:
        return str(uuid4())

    async def process_request(self, **kwargs: Any) -> Dict[str, Any]:
        self._call_count += 1
        if self._index >= len(self._responses):
            raise RuntimeError("MockOrchestrator exhausted: no more responses configured")
        kind, payload = self._responses[self._index]
        self._index += 1
        if kind == "raise":
            raise payload
        if kind == "error":
            return {"error": True, "response": payload}
        return {"error": False, "response": payload, "orchestration_actions": []}


class RuntimeRequest:
    def __init__(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        selected_documents: Optional[List[str]] = None,
    ) -> None:
        self.message = message
        self.conversation_id = conversation_id
        self.selected_documents = selected_documents or []


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _wait_terminal(
    service: Any,
    run_id: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = await service.get_run_status(run_id)
        if status["status"] in RUN_TERMINAL_STATUSES:
            return status
        await asyncio.sleep(0.02)
    raise TimeoutError(f"Run {run_id} did not reach terminal state within {timeout}s")


async def _get_event_types(service: Any, run_id: str) -> List[str]:
    result = await service.get_run_events(run_id=run_id, after=None, limit=200)
    return [e["type"] for e in result["events"]]


def _check_event_order(
    event_types: List[str],
    required_sequence: List[str],
    failures: List[str],
) -> None:
    """Assert each type in required_sequence is present and in ascending index order."""
    indices = []
    for etype in required_sequence:
        if etype not in event_types:
            failures.append(
                f"missing required event type '{etype}' (events={event_types})"
            )
            return
        indices.append(event_types.index(etype))
    for i in range(1, len(indices)):
        if not (indices[i - 1] < indices[i]):  # require strict ascending order
            failures.append(
                f"events out of order: expected {required_sequence}, got {event_types}"
            )
            return


# ---------------------------------------------------------------------------
# Eval cases
# ---------------------------------------------------------------------------

async def _case_lifecycle_queued_to_succeeded() -> Tuple[bool, List[str]]:
    """State transitions: queued→running→succeeded; events in order; result populated."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()
    orchestrator = MockOrchestrator([("success", "hello response")])
    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=orchestrator, run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub = await service.submit_run(RuntimeRequest("hello", "conv-lc-ok"))
        if sub["status"] != "queued":
            failures.append(f"expected initial status 'queued', got '{sub['status']}'")

        run_id = sub["run_id"]
        status = await _wait_terminal(service, run_id)

        if status["status"] != RUN_STATUS_SUCCEEDED:
            failures.append(
                f"expected terminal status '{RUN_STATUS_SUCCEEDED}', got '{status['status']}'"
            )
        if status.get("result") != "hello response":
            failures.append(
                f"expected result 'hello response', got '{status.get('result')}'"
            )
        if status.get("error") is not None:
            failures.append(f"expected no error, got '{status.get('error')}'")

        event_types = await _get_event_types(service, run_id)
        _check_event_order(
            event_types,
            [RUN_EVENT_QUEUED, RUN_EVENT_STARTED, RUN_EVENT_SUCCEEDED],
            failures,
        )

    return len(failures) == 0, failures


async def _case_lifecycle_queued_to_failed() -> Tuple[bool, List[str]]:
    """Error path: running→failed; error field set; no result."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()
    orchestrator = MockOrchestrator([("error", "something went wrong")])
    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=orchestrator, run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub = await service.submit_run(RuntimeRequest("hello", "conv-lc-fail"))
        run_id = sub["run_id"]
        status = await _wait_terminal(service, run_id)

        if status["status"] != RUN_STATUS_FAILED:
            failures.append(
                f"expected terminal status '{RUN_STATUS_FAILED}', got '{status['status']}'"
            )
        if status.get("error") != "something went wrong":
            failures.append(
                f"expected error 'something went wrong', got '{status.get('error')}'"
            )
        if status.get("result") is not None:
            failures.append(f"expected no result, got '{status.get('result')}'")

        event_types = await _get_event_types(service, run_id)
        _check_event_order(
            event_types,
            [RUN_EVENT_QUEUED, RUN_EVENT_STARTED, RUN_EVENT_FAILED],
            failures,
        )

    return len(failures) == 0, failures


async def _case_retry_transient_then_success() -> Tuple[bool, List[str]]:
    """Orchestrator raises twice, succeeds on 3rd; retrying events emitted; final status succeeded."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()
    orchestrator = MockOrchestrator([
        ("raise", RuntimeError("transient error 1")),
        ("raise", RuntimeError("transient error 2")),
        ("success", "recovered ok"),
    ])
    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=orchestrator, run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub = await service.submit_run(RuntimeRequest("hello", "conv-retry-ok"))
        run_id = sub["run_id"]
        status = await _wait_terminal(service, run_id)

        if status["status"] != RUN_STATUS_SUCCEEDED:
            failures.append(
                f"expected terminal status '{RUN_STATUS_SUCCEEDED}', got '{status['status']}'"
            )
        if status.get("result") != "recovered ok":
            failures.append(
                f"expected result 'recovered ok', got '{status.get('result')}'"
            )

        event_types = await _get_event_types(service, run_id)

        retrying_count = event_types.count(RUN_EVENT_RETRYING)
        if retrying_count < 2:
            failures.append(
                f"expected at least 2 '{RUN_EVENT_RETRYING}' events, got {retrying_count} "
                f"(events={event_types})"
            )

        if not event_types or event_types[-1] != RUN_EVENT_SUCCEEDED:
            failures.append(
                f"expected last event to be '{RUN_EVENT_SUCCEEDED}', got events={event_types}"
            )

    return len(failures) == 0, failures


async def _case_retry_exhaustion() -> Tuple[bool, List[str]]:
    """All 3 attempts raise; final status failed; exactly 2 retrying events before failed."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()
    orchestrator = MockOrchestrator([
        ("raise", RuntimeError("fail 1")),
        ("raise", RuntimeError("fail 2")),
        ("raise", RuntimeError("fail 3")),
    ])
    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=orchestrator, run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub = await service.submit_run(RuntimeRequest("hello", "conv-exhaust"))
        run_id = sub["run_id"]
        status = await _wait_terminal(service, run_id)

        if status["status"] != RUN_STATUS_FAILED:
            failures.append(
                f"expected terminal status '{RUN_STATUS_FAILED}', got '{status['status']}'"
            )

        event_types = await _get_event_types(service, run_id)

        retrying_count = event_types.count(RUN_EVENT_RETRYING)
        if retrying_count != 2:
            failures.append(
                f"expected exactly 2 '{RUN_EVENT_RETRYING}' events, got {retrying_count} "
                f"(events={event_types})"
            )

        if not event_types or event_types[-1] != RUN_EVENT_FAILED:
            failures.append(
                f"expected last event to be '{RUN_EVENT_FAILED}', got events={event_types}"
            )

    return len(failures) == 0, failures


async def _case_session_isolation_different_sessions() -> Tuple[bool, List[str]]:
    """Two concurrent runs in different sessions both reach succeeded."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()
    orchestrator = MockOrchestrator([
        ("success", "result-A"),
        ("success", "result-B"),
    ])
    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=orchestrator, run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub_a = await service.submit_run(RuntimeRequest("hello", "conv-diff-A"))
        sub_b = await service.submit_run(RuntimeRequest("hello", "conv-diff-B"))

        status_a, status_b = await asyncio.gather(
            _wait_terminal(service, sub_a["run_id"]),
            _wait_terminal(service, sub_b["run_id"]),
        )

        for label, status in [("conv-diff-A", status_a), ("conv-diff-B", status_b)]:
            if status["status"] != RUN_STATUS_SUCCEEDED:
                failures.append(
                    f"{label}: expected '{RUN_STATUS_SUCCEEDED}', got '{status['status']}'"
                )

    return len(failures) == 0, failures


async def _case_session_isolation_same_session_blocked() -> Tuple[bool, List[str]]:
    """Second concurrent run in same session fails with SESSION_BUSY error."""
    failures: List[str] = []
    mock_db_ops = MockDbOps()

    # Run 1 blocks until we release it; run 2 must exhaust all lease retries and fail
    proceed_event = asyncio.Event()

    class BlockingOrchestrator:
        def create_conversation(self) -> str:
            return str(uuid4())

        async def process_request(self, **kwargs: Any) -> Dict[str, Any]:
            await proceed_event.wait()
            return {"error": False, "response": "run1 ok", "orchestration_actions": []}

    store = InMemoryRunStore()
    service = RuntimeService(orchestrator=BlockingOrchestrator(), run_store=store)

    with patch("backend.database.operations.db_ops", mock_db_ops):
        sub1 = await service.submit_run(RuntimeRequest("hello 1", "conv-shared"))
        run1_id = sub1["run_id"]

        # Wait until run1 has acquired the lease (status transitions to running)
        # before submitting run2. Without this, asyncio may schedule run2's background
        # task before run1's, letting run2 win the lease and inverting the assertions.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            s = await service.get_run_status(run1_id)
            if s["status"] not in {"queued"}:
                break
            await asyncio.sleep(0.01)

        sub2 = await service.submit_run(RuntimeRequest("hello 2", "conv-shared"))
        run2_id = sub2["run_id"]

        # Wait for run 2 to exhaust its lease acquisition retries and fail
        # (backoff policy in _acquire_lease_with_retry determines how long this takes)
        status2 = await _wait_terminal(service, run2_id, timeout=10.0)

        # Now let run 1 proceed and complete
        proceed_event.set()
        status1 = await _wait_terminal(service, run1_id, timeout=5.0)

        if status1["status"] != RUN_STATUS_SUCCEEDED:
            failures.append(
                f"run1: expected '{RUN_STATUS_SUCCEEDED}', got '{status1['status']}'"
            )

        if status2["status"] != RUN_STATUS_FAILED:
            failures.append(
                f"run2: expected '{RUN_STATUS_FAILED}', got '{status2['status']}'"
            )
        if status2.get("error") != SESSION_BUSY_MESSAGE:
            failures.append(
                f"run2: expected error '{SESSION_BUSY_MESSAGE}', got '{status2.get('error')}'"
            )

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Eval registry
# ---------------------------------------------------------------------------

EvalCase = Tuple[str, str, Callable[[], Coroutine[Any, Any, Tuple[bool, List[str]]]]]

EVAL_CASES: List[EvalCase] = [
    ("runtime", "lifecycle_queued_to_succeeded", _case_lifecycle_queued_to_succeeded),
    ("runtime", "lifecycle_queued_to_failed", _case_lifecycle_queued_to_failed),
    ("runtime", "retry_transient_then_success", _case_retry_transient_then_success),
    ("runtime", "retry_exhaustion", _case_retry_exhaustion),
    ("runtime", "session_isolation_different_sessions", _case_session_isolation_different_sessions),
    ("runtime", "session_isolation_same_session_blocked", _case_session_isolation_same_session_blocked),
]


# ---------------------------------------------------------------------------
# Runner and reporting
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_evals() -> Dict[str, Any]:
    generated_at = _utc_now_iso()
    results: List[Dict[str, Any]] = []

    for suite, case_id, case_fn in EVAL_CASES:
        started = time.monotonic()
        try:
            passed, failures = await case_fn()
        except Exception as exc:
            passed = False
            failures = [f"eval case raised unexpected exception: {exc}"]
        duration_ms = int((time.monotonic() - started) * 1000)
        results.append(
            {
                "suite": suite,
                "case_id": case_id,
                "passed": passed,
                "failures": failures,
                "duration_ms": duration_ms,
            }
        )

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
    }
    summary["pass_rate"] = (
        summary["passed"] / summary["total"] * 100.0 if summary["total"] else 0.0
    )

    suite_summaries: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )
    for result in results:
        s = suite_summaries[result["suite"]]
        s["total"] += 1
        if result["passed"]:
            s["passed"] += 1
        else:
            s["failed"] += 1

    return {
        "generated_at": generated_at,
        "mode": "runtime",
        "summary": summary,
        "suite_summaries": dict(suite_summaries),
        "results": results,
    }


def write_report(payload: Dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RESULTS_DIR / f"report-runtime-{timestamp}.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path = RESULTS_DIR / "latest.json"
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def print_summary(payload: Dict[str, Any], output_path: Path) -> None:
    summary = payload["summary"]
    try:
        report_path = output_path.relative_to(ROOT)
    except ValueError:
        report_path = output_path
    print("Runtime Eval Harness")
    print("=" * 60)
    print(f"Generated at: {payload['generated_at']}")
    print(f"Passed: {summary['passed']}/{summary['total']}")
    print(f"Failed: {summary['failed']}/{summary['total']}")
    print(f"Pass rate: {summary['pass_rate']:.1f}%")
    print(f"Report: {report_path}")
    print("=" * 60)
    for result in payload["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] {result['suite']}::{result['case_id']} ({result['duration_ms']}ms)"
        )
        for failure in result["failures"]:
            print(f"  - {failure}")


def main() -> int:
    if _IMPORT_ERROR:
        print("Runtime Eval Harness")
        print("=" * 60)
        print("Status: blocked")
        print(_IMPORT_ERROR)
        print("=" * 60)
        return 2

    try:
        payload = asyncio.run(run_evals())
    except Exception as exc:
        print("Runtime Eval Harness")
        print("=" * 60)
        print("Status: blocked")
        print(f"Unexpected error running evals: {exc}")
        print("=" * 60)
        return 2

    output_path = write_report(payload)
    print_summary(payload, output_path)
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
