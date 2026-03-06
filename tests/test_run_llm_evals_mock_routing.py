"""Regression tests for mock tool-routing logic in run_llm_evals."""

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_eval_harness_module():
    project_root = Path(__file__).resolve().parents[1]
    harness_path = project_root / "tests" / "run_llm_evals.py"
    spec = importlib.util.spec_from_file_location("run_llm_evals_module", harness_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestRunLLMEvalsMockRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = _load_eval_harness_module()

    def test_document_search_phrase_does_not_trigger_internet_search(self):
        turn = self.harness._mock_execute_turn(
            "Search my uploaded contract for termination details",
            selected_documents=["doc-123"],
        )
        self.assertIn("search_documents", turn.tools_used)
        self.assertNotIn("internet_search", turn.tools_used)

    def test_explicit_internet_query_triggers_internet_search(self):
        turn = self.harness._mock_execute_turn(
            "Search the internet for today's AI headlines",
            selected_documents=None,
        )
        self.assertIn("internet_search", turn.tools_used)

    def test_safe_eval_math_rejects_exponentiation(self):
        with self.assertRaises(ValueError):
            self.harness._safe_eval_math("2 ** 512")


if __name__ == "__main__":
    unittest.main()
