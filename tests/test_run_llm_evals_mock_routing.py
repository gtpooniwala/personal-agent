"""Regression tests for mock tool-routing logic in run_llm_evals."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


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
        with patch.object(self.harness, "_dotenv_candidates", return_value=[Path("/tmp/nonexistent-live-eval.env")]):
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
            self.assertEqual(error, "EVAL_DATABASE_URL must target a dedicated PostgreSQL *_eval or *_test database.")

            with patch.dict(
                os.environ,
                {"TEST_DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent"},
                clear=True,
            ):
                _, error = self.harness._resolve_live_eval_database_url()
            self.assertEqual(error, "TEST_DATABASE_URL must target a dedicated PostgreSQL *_test database when used for live evals.")

    def test_live_eval_env_sets_database_url_from_eval_db(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test"
        with patch.dict(os.environ, {"EVAL_DATABASE_URL": test_url}, clear=True):
            error = self.harness._configure_live_eval_environment()
            self.assertIsNone(error)
            self.assertEqual(os.environ["DATABASE_URL"], test_url)

    def test_live_eval_env_accepts_eval_suffix(self):
        eval_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_eval"
        with patch.dict(os.environ, {"EVAL_DATABASE_URL": eval_url}, clear=True):
            error = self.harness._configure_live_eval_environment()
            self.assertIsNone(error)
            self.assertEqual(os.environ["DATABASE_URL"], eval_url)

    def test_live_eval_env_accepts_query_string_on_dedicated_database(self):
        eval_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test?sslmode=require"
        with patch.dict(os.environ, {"EVAL_DATABASE_URL": eval_url}, clear=True):
            error = self.harness._configure_live_eval_environment()
            self.assertIsNone(error)
            self.assertEqual(os.environ["DATABASE_URL"], eval_url)

    def test_live_eval_env_reads_eval_db_from_dotenv(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test"
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text(f"EVAL_DATABASE_URL={test_url}\n", encoding="utf-8")
            with patch.object(self.harness, "_dotenv_candidates", return_value=[dotenv_path]):
                with patch.dict(os.environ, {}, clear=True):
                    error = self.harness._configure_live_eval_environment()
                    self.assertIsNone(error)
                    self.assertEqual(os.environ["DATABASE_URL"], test_url)

    def test_live_eval_database_connectivity_returns_blocking_message(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_eval"
        with patch.dict(os.environ, {"EVAL_DATABASE_URL": test_url}, clear=True):
            with patch.object(self.harness, "_dotenv_candidates", return_value=[Path("/tmp/nonexistent-live-eval.env")]):
                with patch.object(self.harness, "_create_live_eval_engine", side_effect=RuntimeError("db down")):
                    with patch.object(self.harness, "_ensure_live_eval_database_exists"):
                        error = self.harness._check_live_eval_database_connectivity()
        self.assertEqual(error, "Live eval database is not reachable: db down")

    def test_live_eval_env_hydrates_provider_keys_from_dotenv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text(
                "GEMINI_API_KEY=test-key\nEVAL_DATABASE_URL=postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_test\n",
                encoding="utf-8",
            )
            with patch.object(self.harness, "_dotenv_candidates", return_value=[dotenv_path]):
                with patch.dict(os.environ, {}, clear=True):
                    error = self.harness._configure_live_eval_environment()
                    hydrated_key = os.environ.get("GEMINI_API_KEY")
        self.assertIsNone(error)
        self.assertEqual(hydrated_key, "test-key")

    def test_live_eval_database_connectivity_includes_docker_port_hint(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_eval"
        with patch.dict(
            os.environ,
            {"EVAL_DATABASE_URL": test_url, "DOCKER_POSTGRES_PORT": "5433"},
            clear=True,
        ):
            with patch.object(self.harness, "_create_live_eval_engine", side_effect=RuntimeError("db down")):
                with patch.object(self.harness, "_ensure_live_eval_database_exists"):
                    error = self.harness._check_live_eval_database_connectivity()
        self.assertIn("Live eval database is not reachable: db down", error)
        self.assertIn("Docker Compose exposes Postgres on host port 5433", error)

    def test_live_mode_requested_parses_flag_and_assignment_forms(self):
        self.assertTrue(self.harness._live_mode_requested(["run_llm_evals.py", "--mode", "live"]))
        self.assertTrue(self.harness._live_mode_requested(["run_llm_evals.py", "--mode=live"]))
        self.assertFalse(self.harness._live_mode_requested(["run_llm_evals.py"]))
        self.assertFalse(self.harness._live_mode_requested(["run_llm_evals.py", "--mode", "mock"]))

    def test_missing_live_eval_dependencies_reports_absent_modules(self):
        def fake_find_spec(name: str):
            return None if name in {"sqlalchemy", "langgraph"} else object()

        with patch.object(self.harness.importlib.util, "find_spec", side_effect=fake_find_spec):
            missing = self.harness._missing_live_eval_dependencies()
        self.assertEqual(missing, ["sqlalchemy", "langgraph"])

    def test_repo_venv_python_candidates_include_git_common_dir_parent(self):
        common_dir = Path("/tmp/personal-agent/.git")
        completed = Mock(stdout=str(common_dir))
        with patch.object(self.harness.subprocess, "run", return_value=completed):
            candidates = self.harness._repo_venv_python_candidates()
        self.assertIn(self.harness.ROOT / ".venv" / "bin" / "python", candidates)
        self.assertIn(common_dir.parent / ".venv" / "bin" / "python", candidates)

    def test_dotenv_candidates_include_git_common_dir_parent(self):
        common_dir = Path("/tmp/personal-agent/.git")
        completed = Mock(stdout=str(common_dir))
        with patch.object(self.harness.subprocess, "run", return_value=completed):
            candidates = self.harness._dotenv_candidates()
        self.assertIn(self.harness.DOTENV_PATH, candidates)
        self.assertIn(common_dir.parent / ".env", candidates)

    def test_live_eval_database_connectivity_ensures_database_exists_first(self):
        test_url = "postgresql+psycopg://user:pass@127.0.0.1:5432/personal_agent_eval"
        engine = Mock()
        sql_text = object()
        connection = unittest.mock.MagicMock()
        engine_cm = unittest.mock.MagicMock()
        engine_cm.__enter__.return_value = connection
        engine.connect = unittest.mock.MagicMock(return_value=engine_cm)
        engine.dispose = unittest.mock.MagicMock()

        with patch.dict(os.environ, {"EVAL_DATABASE_URL": test_url}, clear=True):
            with patch.object(self.harness, "_ensure_live_eval_database_exists") as ensure_db:
                with patch.object(self.harness, "_create_live_eval_engine", return_value=(engine, lambda _: sql_text)):
                    error = self.harness._check_live_eval_database_connectivity()
        self.assertIsNone(error)
        ensure_db.assert_called_once_with(test_url)
        connection.execute.assert_called_once_with(sql_text)


if __name__ == "__main__":
    unittest.main()
