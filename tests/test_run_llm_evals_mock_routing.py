"""Regression tests for mock tool-routing logic in run_llm_evals."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_load_suite_files_filters_core_and_extended_sets(self):
        cases_dir = Path(__file__).resolve().parents[1] / "tests" / "llm_evals" / "cases"

        core_suites = self.harness._load_suite_files(cases_dir, [], "core")
        extended_suites = self.harness._load_suite_files(cases_dir, [], "extended")

        core_case_ids = {case["id"] for suite in core_suites for case in suite.get("cases", [])}
        extended_case_ids = {case["id"] for suite in extended_suites for case in suite.get("cases", [])}

        self.assertIn("calculator_basic", core_case_ids)
        self.assertNotIn("calculator_exponentiation", core_case_ids)
        self.assertIn("calculator_exponentiation", extended_case_ids)
        self.assertIn("gmail_read_latest", extended_case_ids)

    def test_live_eval_env_requires_dedicated_postgres_test_database(self):
        with patch.dict(os.environ, {}, clear=True):
            _, error = self.harness._resolve_live_eval_database_url()
        self.assertIn("EVAL_DATABASE_URL or TEST_DATABASE_URL", error)

        with patch.dict(os.environ, {"EVAL_DATABASE_URL": "sqlite:////tmp/evals.db"}, clear=True):
            _, error = self.harness._resolve_live_eval_database_url()
        self.assertEqual(error, "Live eval database must use PostgreSQL.")

        with patch.dict(
            os.environ,
            {"EVAL_DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent"},
            clear=True,
        ):
            _, error = self.harness._resolve_live_eval_database_url()
        self.assertEqual(error, "Live eval database must target a dedicated PostgreSQL *_test database.")

    def test_live_eval_env_sets_database_url_from_eval_db(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test"
        with patch.dict(os.environ, {"EVAL_DATABASE_URL": test_url}, clear=True):
            error = self.harness._configure_live_eval_environment()
            self.assertIsNone(error)
            self.assertEqual(os.environ["DATABASE_URL"], test_url)

    def test_live_eval_env_reads_eval_db_from_dotenv(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test"
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text(f"EVAL_DATABASE_URL={test_url}\n", encoding="utf-8")
            with patch.object(self.harness, "DOTENV_PATH", dotenv_path):
                with patch.dict(os.environ, {}, clear=True):
                    error = self.harness._configure_live_eval_environment()
                    self.assertIsNone(error)
                    self.assertEqual(os.environ["DATABASE_URL"], test_url)


if __name__ == "__main__":
    unittest.main()
