"""Regression checks for issue #22 LangChain/LangGraph migration."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestLangchainMigrationSource(unittest.TestCase):
    """Static checks to prevent regressions to pre-1.x import paths/APIs."""

    def test_core_orchestrator_imports(self):
        from backend.orchestrator.core import CoreOrchestrator  # noqa: F401

    def test_document_processor_imports(self):
        from backend.services.document_service import DocumentProcessor  # noqa: F401

    def test_no_legacy_import_paths(self):
        targets = [
            ROOT / "backend/orchestrator/core.py",
            ROOT / "backend/services/document_service.py",
            *sorted((ROOT / "backend/orchestrator/tools").glob("*.py")),
        ]
        forbidden = [
            "from langchain.tools import BaseTool",
            "from langchain.prompts import ChatPromptTemplate",
            "from langchain.text_splitter import RecursiveCharacterTextSplitter",
        ]
        for target in targets:
            content = target.read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertNotIn(
                    pattern,
                    content,
                    f"Found legacy import path in {target.relative_to(ROOT)}: {pattern}",
                )

    def test_no_apredict_calls(self):
        for rel_path in (
            "backend/orchestrator/core.py",
            "backend/services/document_service.py",
        ):
            content = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn(
                ".apredict(",
                content,
                f"Deprecated apredict usage found in {rel_path}",
            )

    def test_requirements_match_issue_22_targets(self):
        requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        expected_versions = {
            "langchain": "1.2.10",
            "langgraph": "1.0.10",
            "langchain-openai": "1.1.10",
            "langchain-community": "0.4.1",
            "langchain-text-splitters": "1.1.1",
            "langgraph-checkpoint": "4.0.1",
            "langgraph-prebuilt": "1.0.8",
            "openai": "2.26.0",
            "requests": "2.32.5",
            "pydantic-settings": "2.13.1",
            "numpy": "2.4.2",
            "sqlalchemy": "2.0.48",
            "fastapi": "0.135.1",
            "uvicorn[standard]": "0.41.0",
            "python-dotenv": "1.2.2",
            "aiofiles": "25.1.0",
            "pypdf": "6.7.5",
        }
        for package, version in expected_versions.items():
            self.assertIn(
                f"{package}=={version}",
                requirements,
                f"Missing or incorrect version pin for {package}",
            )


if __name__ == "__main__":
    unittest.main()
