#!/usr/bin/env python3
"""Guarded unittest runner used by local checks and CI."""

from __future__ import annotations

import argparse
import sys
import unittest

EXIT_SUCCESS = 0
EXIT_TEST_FAILURE = 1
EXIT_NO_TESTS = 2
EXIT_SKIP_ONLY = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unittest discovery with guardrails.")
    parser.add_argument("--start-dir", default="tests", help="Discovery start directory.")
    parser.add_argument("--pattern", default="test_*.py", help="Discovery filename pattern.")
    parser.add_argument(
        "--top-level-dir",
        default=None,
        help="Top-level project directory for import resolution.",
    )
    parser.add_argument(
        "--verbosity",
        type=int,
        default=2,
        help="unittest runner verbosity level.",
    )
    return parser.parse_args()


def determine_exit_code(discovered: int, executed: int, successful: bool) -> int:
    if discovered == 0:
        return EXIT_NO_TESTS
    if executed == 0:
        return EXIT_SKIP_ONLY
    if not successful:
        return EXIT_TEST_FAILURE
    return EXIT_SUCCESS


def main() -> int:
    args = parse_args()
    loader = unittest.TestLoader()
    discover_kwargs = {
        "start_dir": args.start_dir,
        "pattern": args.pattern,
    }
    if args.top_level_dir:
        discover_kwargs["top_level_dir"] = args.top_level_dir
    suite = loader.discover(**discover_kwargs)

    runner = unittest.TextTestRunner(verbosity=args.verbosity)
    result = runner.run(suite)

    discovered = result.testsRun
    skipped = len(result.skipped)
    executed = discovered - skipped
    failures = len(result.failures)
    errors = len(result.errors)
    unexpected_successes = len(result.unexpectedSuccesses)

    print("\nUnit Test Guardrail Summary")
    print("=" * 60)
    print(f"Discovered: {discovered}")
    print(f"Skipped: {skipped}")
    print(f"Executed (non-skipped): {executed}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
    print(f"Unexpected successes: {unexpected_successes}")

    exit_code = determine_exit_code(
        discovered=discovered,
        executed=executed,
        successful=result.wasSuccessful(),
    )

    if exit_code == EXIT_NO_TESTS:
        print("Status: NON-PASS (no tests discovered)")
    elif exit_code == EXIT_SKIP_ONLY:
        print("Status: NON-PASS (skip-only test run)")
    elif exit_code == EXIT_TEST_FAILURE:
        print("Status: NON-PASS (test failures/errors)")
    else:
        print("Status: PASS")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
