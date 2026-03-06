"""Regression checks for issue #22 LangChain/LangGraph migration."""

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CORE_IMPORT_AVAILABLE = True
CORE_IMPORT_ERROR = ""
DOC_IMPORT_AVAILABLE = True
DOC_IMPORT_ERROR = ""

try:
    from backend.orchestrator.core import CoreOrchestrator
except Exception as exc:  # pragma: no cover - gated by skipUnless
    CORE_IMPORT_AVAILABLE = False
    CORE_IMPORT_ERROR = str(exc)

try:
    from backend.services.document_service import DocumentProcessor
except Exception as exc:  # pragma: no cover - gated by skipUnless
    DOC_IMPORT_AVAILABLE = False
    DOC_IMPORT_ERROR = str(exc)


class TestLangchainMigrationSource(unittest.TestCase):
    """Static checks to prevent regressions to pre-1.x import paths/APIs."""

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
        }
        for package, version in expected_versions.items():
            self.assertIn(
                f"{package}=={version}",
                requirements,
                f"Missing or incorrect version pin for {package}",
            )


@unittest.skipUnless(
    CORE_IMPORT_AVAILABLE,
    f"Core orchestrator dependencies unavailable: {CORE_IMPORT_ERROR}",
)
class TestCoreAinvokeCompatibility(unittest.TestCase):
    def test_ainvoke_text_returns_content(self):
        with patch("backend.orchestrator.core.ToolRegistry"), patch.object(
            CoreOrchestrator, "_setup_llm"
        ) as setup_llm:
            fake_llm = AsyncMock()
            fake_llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content="pong"))
            setup_llm.return_value = fake_llm
            orchestrator = CoreOrchestrator()

            result = asyncio.run(orchestrator._ainvoke_text("ping"))
            self.assertEqual(result, "pong")


@unittest.skipUnless(
    DOC_IMPORT_AVAILABLE,
    f"Document processor dependencies unavailable: {DOC_IMPORT_ERROR}",
)
class TestDocumentAinvokeCompatibility(unittest.TestCase):
    def test_ainvoke_text_returns_content(self):
        with patch.object(DocumentProcessor, "__init__", return_value=None):
            processor = DocumentProcessor()
        processor.llm = AsyncMock()
        processor.llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content="summary"))

        result = asyncio.run(processor._ainvoke_text("summarize"))
        self.assertEqual(result, "summary")


if __name__ == "__main__":
    unittest.main()
