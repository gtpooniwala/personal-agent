"""Regression tests for the guarded unittest runner exit semantics."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_runner_module():
    project_root = Path(__file__).resolve().parents[1]
    runner_path = project_root / "tests" / "run_unit_tests.py"
    spec = importlib.util.spec_from_file_location("run_unit_tests_module", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestRunUnitTestsGuardrail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner_module()

    def test_no_tests_discovered_is_non_pass(self):
        code = self.runner.determine_exit_code(discovered=0, executed=0, successful=True)
        self.assertEqual(code, self.runner.EXIT_NO_TESTS)

    def test_skip_only_run_is_non_pass(self):
        code = self.runner.determine_exit_code(discovered=7, executed=0, successful=True)
        self.assertEqual(code, self.runner.EXIT_SKIP_ONLY)

    def test_failure_run_is_non_pass(self):
        code = self.runner.determine_exit_code(discovered=7, executed=5, successful=False)
        self.assertEqual(code, self.runner.EXIT_TEST_FAILURE)

    def test_successful_run_passes(self):
        code = self.runner.determine_exit_code(discovered=7, executed=5, successful=True)
        self.assertEqual(code, self.runner.EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()
