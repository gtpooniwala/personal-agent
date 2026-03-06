#!/usr/bin/env python3
"""Deterministic repository checks runner (no third-party dependencies required)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "repo_checks" / "cases.json"
RESULTS_PATH = ROOT / "tests" / "repo_checks" / "results.json"


@dataclass
class CheckResult:
    case_id: str
    passed: bool
    description: str
    detail: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_case(case: Dict[str, Any]) -> CheckResult:
    case_id = case["id"]
    case_type = case["type"]
    description = case.get("description", case_id)
    rel_path = case.get("path", "")
    target = ROOT / rel_path if rel_path else None

    if case_type == "path_absent":
        exists = target.exists() if target else False
        return CheckResult(
            case_id=case_id,
            passed=not exists,
            description=description,
            detail=f"path {'exists' if exists else 'does not exist'}: {rel_path}",
        )

    if case_type == "contains":
        if not target or not target.exists():
            return CheckResult(case_id, False, description, f"missing file: {rel_path}")
        pattern = case["pattern"]
        content = _read_text(target)
        passed = pattern in content
        return CheckResult(case_id, passed, description, f"pattern {'found' if passed else 'not found'}")

    if case_type == "not_contains":
        if not target or not target.exists():
            return CheckResult(case_id, False, description, f"missing file: {rel_path}")
        pattern = case["pattern"]
        content = _read_text(target)
        passed = pattern not in content
        return CheckResult(case_id, passed, description, f"pattern {'absent' if passed else 'present'}")

    return CheckResult(case_id, False, description, f"unsupported case type: {case_type}")


def load_cases() -> List[Dict[str, Any]]:
    return json.loads(_read_text(CASES_PATH))


def main() -> int:
    cases = load_cases()
    results = [run_case(case) for case in cases]

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    failed = total - passed

    print("Repository Checks")
    print("=" * 60)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.case_id}: {result.description}")
        print(f"       {result.detail}")

    print("=" * 60)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {failed}/{total}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "results": [
            {
                "id": r.case_id,
                "passed": r.passed,
                "description": r.description,
                "detail": r.detail,
            }
            for r in results
        ],
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Report written to {RESULTS_PATH.relative_to(ROOT)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
