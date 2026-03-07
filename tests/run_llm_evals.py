#!/usr/bin/env python3
"""LLM/workflow eval harness with deterministic scoring and JSON reporting."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVAL_ROOT = ROOT / "tests" / "llm_evals"
CASES_DIR = EVAL_ROOT / "cases"
RESULTS_DIR = EVAL_ROOT / "results"
MAX_SAFE_EXPONENT = 64
DOTENV_PATH = ROOT / ".env"


@dataclass
class TurnExecution:
    message: str
    response: str
    tools_used: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LLM/workflow eval suites.")
    parser.add_argument(
        "--mode",
        choices=("mock", "live"),
        default="mock",
        help="mock = deterministic local simulation, live = run real orchestrator.",
    )
    parser.add_argument(
        "--suite",
        action="append",
        default=[],
        help="Run only selected suite(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--set",
        dest="eval_set",
        choices=("core", "extended", "all"),
        default="all",
        help="Run only the core cases, only the extended cases, or all cases.",
    )
    parser.add_argument(
        "--cases-dir",
        default=str(CASES_DIR),
        help="Directory containing eval suite JSON files.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional exact output path for JSON report.",
    )
    return parser.parse_args()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_env_file_value(name: str) -> Optional[str]:
    """Read a variable from the repository .env without importing backend settings."""
    if not DOTENV_PATH.exists():
        return None

    for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return value.strip().strip('"').strip("'")
    return None


def _env_or_file(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    file_value = _read_env_file_value(name)
    if file_value is not None and file_value.strip():
        return file_value.strip()
    return None


def _resolve_live_eval_database_url() -> Tuple[Optional[str], Optional[str]]:
    """Return an isolated Postgres URL for live evals or a blocking message."""
    eval_database_url = (_env_or_file("EVAL_DATABASE_URL") or "").strip()
    test_database_url = (_env_or_file("TEST_DATABASE_URL") or "").strip()
    database_url = eval_database_url or test_database_url
    if not database_url:
        return None, (
            "Live evals require EVAL_DATABASE_URL or TEST_DATABASE_URL to point to a dedicated "
            "PostgreSQL *_eval or *_test database."
        )
    if not database_url.startswith("postgresql"):
        return None, "Live eval database must use PostgreSQL."
    database_name = database_url.rsplit("/", 1)[-1]
    if eval_database_url:
        if not (database_name.endswith("_eval") or database_name.endswith("_test")):
            return None, "EVAL_DATABASE_URL must target a dedicated PostgreSQL *_eval or *_test database."
    elif not database_name.endswith("_test"):
        return None, "TEST_DATABASE_URL must target a dedicated PostgreSQL *_test database when used for live evals."
    return database_url, None


def _configure_live_eval_environment() -> Optional[str]:
    """Pin live evals to an isolated database before importing backend modules."""
    database_url, error = _resolve_live_eval_database_url()
    if error:
        return error
    os.environ["DATABASE_URL"] = str(database_url)
    return None


def _check_live_eval_database_connectivity() -> Optional[str]:
    """Return a blocking message if the configured live eval database is unreachable."""
    database_url, error = _resolve_live_eval_database_url()
    if error:
        return error
    try:
        engine = create_engine(str(database_url), pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except Exception as exc:
        return f"Live eval database is not reachable: {exc}"
    return None


def _case_matches_eval_set(case: Dict[str, Any], eval_set: str) -> bool:
    case_set = str(case.get("set", "core")).strip().lower() or "core"
    if case_set not in {"core", "extended"}:
        raise ValueError(
            f"Case '{case.get('id', 'unknown')}' has invalid set '{case_set}'. "
            "Expected 'core' or 'extended'."
        )
    return eval_set == "all" or case_set == eval_set


def _load_suite_files(cases_dir: Path, suite_filter: Sequence[str], eval_set: str) -> List[Dict[str, Any]]:
    if not cases_dir.exists():
        raise ValueError(f"Cases directory does not exist: {cases_dir}")
    if not cases_dir.is_dir():
        raise ValueError(f"Cases path is not a directory: {cases_dir}")

    suites: List[Dict[str, Any]] = []
    selected = {s.strip() for s in suite_filter if s.strip()}

    for path in sorted(cases_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        suite_name = str(payload.get("suite", "")).strip()
        if selected and suite_name not in selected:
            continue
        filtered_cases = [
            case for case in payload.get("cases", [])
            if isinstance(case, dict) and _case_matches_eval_set(case, eval_set)
        ]
        if not filtered_cases:
            continue
        payload["cases"] = filtered_cases
        try:
            payload["_source_file"] = str(path.relative_to(ROOT))
        except ValueError:
            payload["_source_file"] = str(path)
        suites.append(payload)

    if selected:
        present = {suite.get("suite") for suite in suites}
        missing = sorted(selected - present)
        if missing:
            raise ValueError(f"Unknown suite name(s): {', '.join(missing)}")
    elif not suites:
        raise ValueError(
            f"No eval suite files found in {cases_dir}. "
            "Expected at least one *.json suite definition."
        )

    return suites


def _contains_math_expression(message: str) -> Optional[str]:
    candidates = re.findall(r"[-+*/().\d\s]{3,}", message)
    for candidate in candidates:
        stripped = candidate.strip()
        if not stripped:
            continue
        if not re.search(r"\d", stripped):
            continue
        if not re.search(r"[+\-*/]", stripped):
            continue
        return stripped
    return None


def _safe_eval_math(expression: str) -> Optional[float]:
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.Load,
    )

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("Unsupported constant")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_SAFE_EXPONENT:
                    raise ValueError(f"Exponent magnitude exceeds safe limit ({MAX_SAFE_EXPONENT})")
                return left**right
            raise ValueError("Unsupported binary operator")
        raise ValueError("Unsupported expression")

    parsed = ast.parse(expression, mode="eval")
    for node in ast.walk(parsed):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Unsupported node in expression: {type(node).__name__}")

    result = _eval(parsed)
    if math.isnan(result) or math.isinf(result):
        raise ValueError("Non-finite math result")
    return result


def _mock_execute_turn(message: str, selected_documents: Optional[List[str]]) -> TurnExecution:
    lower = message.lower()
    tools_used: List[str] = []
    response_parts: List[str] = []

    doc_query = any(token in lower for token in ("document", "uploaded", "file", "contract", "pdf"))
    internet_query = (
        any(token in lower for token in ("internet", "online", "news", "headline", "headlines"))
        or any(
            phrase in lower
            for phrase in ("search the internet", "internet search", "search the web", "web search")
        )
    )
    time_query = "time" in lower
    greeting_query = any(token in lower for token in ("hello", "hi", "hey"))
    math_expression = _contains_math_expression(message)

    if math_expression:
        tools_used.append("calculator")
        try:
            result = _safe_eval_math(math_expression)
            integer_result = int(result)
            rendered = str(integer_result) if integer_result == result else str(result)
            response_parts.append(f"The result is {rendered}.")
        except Exception:
            response_parts.append("I could not evaluate that expression safely.")

    if time_query:
        tools_used.append("current_time")
        response_parts.append("The current time is 12:00 UTC.")

    if doc_query:
        if selected_documents:
            tools_used.append("search_documents")
            response_parts.append("I searched your selected documents for relevant information.")
        else:
            response_parts.append("No documents are currently selected. Please select one or more documents.")

    if internet_query:
        tools_used.append("internet_search")
        response_parts.append("I ran an internet search and found current results.")

    if greeting_query and not tools_used:
        response_parts.append("Hello! How can I help today?")

    if not response_parts:
        response_parts.append("I can help with tools, document search, and general assistant tasks.")

    # Keep output deterministic and deduplicated
    deduped_tools = list(dict.fromkeys(tools_used))
    return TurnExecution(message=message, response=" ".join(response_parts), tools_used=deduped_tools)


async def _live_execute_case(turns: Sequence[Dict[str, Any]]) -> List[TurnExecution]:
    env_error = _configure_live_eval_environment()
    if env_error:
        raise RuntimeError(env_error)

    # Imported lazily so mock mode can run with minimal dependencies.
    from backend.orchestrator.core import CoreOrchestrator
    from backend.database.operations import db_ops

    orchestrator = CoreOrchestrator(user_id="llm-eval-runner")
    conversation_id = orchestrator.create_conversation("LLM Eval Harness Run")
    executions: List[TurnExecution] = []

    try:
        for turn in turns:
            message = str(turn.get("message", ""))
            selected_documents = turn.get("selected_documents")
            result = await orchestrator.process_request(
                user_request=message,
                conversation_id=conversation_id,
                selected_documents=selected_documents,
            )
            actions = result.get("orchestration_actions") or []
            tools = []
            for action in actions:
                if isinstance(action, dict) and action.get("tool"):
                    tools.append(str(action["tool"]).lower())
            tools = list(dict.fromkeys(tools))
            executions.append(
                TurnExecution(
                    message=message,
                    response=str(result.get("response", "")),
                    tools_used=tools,
                )
            )
    finally:
        db_ops.delete_conversation(conversation_id)

    return executions


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).lower() for v in value]
    return [str(value).lower()]


def _check_turn_expectation(index: int, expectation: Dict[str, Any], actual: TurnExecution) -> List[str]:
    failures: List[str] = []
    tools = [tool.lower() for tool in actual.tools_used]
    response_lower = actual.response.lower()

    for required in _ensure_list(expectation.get("must_call")):
        if required not in tools:
            failures.append(f"turn {index}: expected tool '{required}' was not called (tools={tools})")

    for forbidden in _ensure_list(expectation.get("must_not_call")):
        if forbidden in tools:
            failures.append(f"turn {index}: forbidden tool '{forbidden}' was called (tools={tools})")

    for needle in _ensure_list(expectation.get("response_contains")):
        if needle not in response_lower:
            failures.append(f"turn {index}: response missing expected text '{needle}'")

    contains_any = _ensure_list(expectation.get("response_contains_any"))
    if contains_any and not any(needle in response_lower for needle in contains_any):
        failures.append(
            f"turn {index}: response missing any expected text from {contains_any}"
        )

    for needle in _ensure_list(expectation.get("response_not_contains")):
        if needle in response_lower:
            failures.append(f"turn {index}: response unexpectedly contains '{needle}'")

    return failures


def _resolve_expected(case: Dict[str, Any], mode: str) -> Dict[str, Any]:
    case_id = str(case.get("id", "unknown"))
    expected = case.get("expected")
    if expected is None:
        raise ValueError(f"Case '{case_id}' is missing required 'expected' object")
    if not isinstance(expected, dict):
        raise ValueError(f"Case '{case_id}' has invalid 'expected': must be an object")

    resolved = {k: v for k, v in expected.items() if k != "by_mode"}
    by_mode = expected.get("by_mode")
    if by_mode is not None and not isinstance(by_mode, dict):
        raise ValueError(f"Case '{case_id}' has invalid 'expected.by_mode': must be an object")
    if isinstance(by_mode, dict):
        mode_override = by_mode.get(mode)
        if mode_override is not None and not isinstance(mode_override, dict):
            raise ValueError(
                f"Case '{case_id}' has invalid 'expected.by_mode.{mode}': must be an object"
            )
        if isinstance(mode_override, dict):
            resolved.update(mode_override)

    if "per_turn" in resolved and not isinstance(resolved["per_turn"], list):
        raise ValueError(f"Case '{case_id}' has invalid 'expected.per_turn': must be a list")

    return resolved


def _evaluate_case(
    case: Dict[str, Any], executions: Sequence[TurnExecution], mode: str
) -> Tuple[bool, List[str]]:
    expected = _resolve_expected(case, mode)
    failures: List[str] = []

    per_turn_expectations = expected.get("per_turn", [])
    for index, actual in enumerate(executions):
        if index < len(per_turn_expectations):
            failures.extend(_check_turn_expectation(index + 1, per_turn_expectations[index], actual))

    all_tools = [tool for execution in executions for tool in execution.tools_used]
    all_tools = [tool.lower() for tool in all_tools]
    all_response_text = " ".join(execution.response for execution in executions).lower()

    for required in _ensure_list(expected.get("overall_must_call")):
        if required not in all_tools:
            failures.append(f"overall: expected tool '{required}' was not called")

    for forbidden in _ensure_list(expected.get("overall_must_not_call")):
        if forbidden in all_tools:
            failures.append(f"overall: forbidden tool '{forbidden}' was called")

    for needle in _ensure_list(expected.get("overall_response_contains")):
        if needle not in all_response_text:
            failures.append(f"overall: response missing expected text '{needle}'")

    return len(failures) == 0, failures


async def run_evals(args: argparse.Namespace) -> Dict[str, Any]:
    cases_dir = Path(args.cases_dir).resolve()
    suites = _load_suite_files(cases_dir, args.suite, args.eval_set)
    generated_at = _utc_now_iso()
    results: List[Dict[str, Any]] = []

    for suite in suites:
        suite_name = str(suite.get("suite", "unknown"))
        for case in suite.get("cases", []):
            case_id = str(case.get("id", "unknown"))
            turns = case.get("turns", [])
            started = time.monotonic()

            execution_error: Optional[str] = None
            if args.mode == "live":
                try:
                    executions = await _live_execute_case(turns)
                except Exception as exc:
                    execution_error = f"live execution failed: {exc}"
                    executions = [
                        TurnExecution(
                            message=str(turn.get("message", "")),
                            response=execution_error,
                            tools_used=[],
                        )
                        for turn in turns
                    ]
            else:
                executions = []
                selected_documents: Optional[List[str]] = None
                for turn in turns:
                    if "selected_documents" in turn:
                        selected_documents = turn.get("selected_documents")
                    execution = _mock_execute_turn(str(turn.get("message", "")), selected_documents)
                    executions.append(execution)

            passed, failures = _evaluate_case(case, executions, args.mode)
            if execution_error:
                passed = False
                failures.insert(0, execution_error)
            duration_ms = int((time.monotonic() - started) * 1000)

            results.append(
                {
                    "suite": suite_name,
                    "case_id": case_id,
                    "set": str(case.get("set", "core")),
                    "description": case.get("description", ""),
                    "passed": passed,
                    "failures": failures,
                    "duration_ms": duration_ms,
                    "turns": [
                        {
                            "index": i + 1,
                            "message": turn.message,
                            "tools_used": turn.tools_used,
                            "response": turn.response,
                        }
                        for i, turn in enumerate(executions)
                    ],
                }
            )

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
    }
    if summary["total"] == 0:
        raise ValueError(
            "No eval cases were executed. Check suite definitions and filters."
        )
    summary["pass_rate"] = (summary["passed"] / summary["total"] * 100.0) if summary["total"] else 0.0

    suite_summaries: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for result in results:
        suite_summary = suite_summaries[result["suite"]]
        suite_summary["total"] += 1
        if result["passed"]:
            suite_summary["passed"] += 1
        else:
            suite_summary["failed"] += 1

    return {
        "generated_at": generated_at,
        "mode": args.mode,
        "eval_set": args.eval_set,
        "summary": summary,
        "suite_summaries": dict(suite_summaries),
        "results": results,
    }


def write_report(payload: Dict[str, Any], output_arg: Optional[str]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if output_arg:
        output_path = Path(output_arg).resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        output_path = RESULTS_DIR / f"report-{payload['mode']}-{payload.get('eval_set', 'all')}-{timestamp}.json"

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path = RESULTS_DIR / "latest.json"
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def check_live_prerequisites() -> Optional[str]:
    """Return blocking message if live mode cannot run in current environment."""
    env_error = _configure_live_eval_environment()
    if env_error:
        return env_error
    db_error = _check_live_eval_database_connectivity()
    if db_error:
        return db_error

    try:
        from backend.llm import create_chat_model, MissingProviderKeyError, MissingModelDependencyError
    except ModuleNotFoundError as exc:
        return (
            "Live eval prerequisites are missing. Install backend dependencies first "
            f"(missing module: {exc})."
        )

    try:
        # Probe model construction so missing API key is surfaced once with a clear message.
        _ = create_chat_model("orchestrator", temperature=0.0, max_tokens=32)
    except MissingProviderKeyError as exc:
        return str(exc)
    except MissingModelDependencyError as exc:
        return str(exc)
    except Exception:
        # Non-key runtime issues are handled per case in run_evals.
        return None

    return None


def print_summary(payload: Dict[str, Any], output_path: Path) -> None:
    summary = payload["summary"]
    try:
        report_path = output_path.relative_to(ROOT)
    except ValueError:
        report_path = output_path
    print("LLM Eval Harness")
    print("=" * 60)
    print(f"Mode: {payload['mode']}")
    print(f"Set: {payload.get('eval_set', 'all')}")
    print(f"Generated at: {payload['generated_at']}")
    print(f"Passed: {summary['passed']}/{summary['total']}")
    print(f"Failed: {summary['failed']}/{summary['total']}")
    print(f"Pass rate: {summary['pass_rate']:.1f}%")
    print(f"Report: {report_path}")
    print("=" * 60)

    for result in payload["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['suite']}::{result['case_id']}")
        if result["failures"]:
            for failure in result["failures"]:
                print(f"  - {failure}")


def main() -> int:
    args = parse_args()
    if args.mode == "live":
        preflight_error = check_live_prerequisites()
        if preflight_error:
            print("LLM Eval Harness")
            print("=" * 60)
            print("Mode: live")
            print("Status: blocked")
            print(preflight_error)
            print("=" * 60)
            return 2
    try:
        payload = asyncio.run(run_evals(args))
    except ValueError as exc:
        print("LLM Eval Harness")
        print("=" * 60)
        print(f"Mode: {args.mode}")
        print("Status: blocked")
        print(str(exc))
        print("=" * 60)
        return 2
    output_path = write_report(payload, args.output)
    print_summary(payload, output_path)
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
