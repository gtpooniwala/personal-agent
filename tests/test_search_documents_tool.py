"""Focused regression tests for the search_documents tool."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

SEARCH_DOCUMENTS_TOOL_AVAILABLE = True
SEARCH_DOCUMENTS_TOOL_IMPORT_ERROR = ""
search_documents_module = None

try:
    import backend.orchestrator.tools.search_documents as search_documents_module
    from backend.orchestrator.tools.search_documents import SearchDocumentsTool
except ImportError as exc:
    SEARCH_DOCUMENTS_TOOL_AVAILABLE = False
    SEARCH_DOCUMENTS_TOOL_IMPORT_ERROR = str(exc)


def _build_doc_processor(async_results=None, sync_results=None, documents=None):
    processor = Mock()
    processor.initialization_error = None
    processor.search_documents = AsyncMock(return_value=async_results or [])
    processor.search_documents_sync = Mock(return_value=sync_results or [])
    processor.get_documents = Mock(
        return_value=documents
        if documents is not None
        else [{"filename": "Plan.pdf", "summary": "Quarterly plan summary."}]
    )
    return processor


@unittest.skipUnless(
    SEARCH_DOCUMENTS_TOOL_AVAILABLE,
    f"SearchDocumentsTool unavailable: {SEARCH_DOCUMENTS_TOOL_IMPORT_ERROR}",
)
class TestSearchDocumentsToolSync(unittest.TestCase):
    @patch("backend.services.document_service.doc_processor")
    def test_run_passes_selected_documents_and_clamped_limit(self, mock_doc_processor):
        mock_doc_processor.search_documents_sync.return_value = []
        mock_doc_processor.get_documents.return_value = []
        mock_doc_processor.initialization_error = None

        tool = SearchDocumentsTool(
            user_id="user-1",
            selected_documents=["doc-1", "doc-2"],
        )

        tool._run("pricing", max_results=4)

        mock_doc_processor.search_documents_sync.assert_called_once_with(
            "pricing",
            "user-1",
            limit=4,
            selected_documents=["doc-1", "doc-2"],
        )


@unittest.skipUnless(
    SEARCH_DOCUMENTS_TOOL_AVAILABLE,
    f"SearchDocumentsTool unavailable: {SEARCH_DOCUMENTS_TOOL_IMPORT_ERROR}",
)
class TestSearchDocumentsToolAsync(unittest.IsolatedAsyncioTestCase):
    async def test_arun_honors_requested_max_results(self):
        cases = (
            (1, 1),
            (5, 5),
            (0, 1),
            (99, 5),
        )

        for requested, expected in cases:
            with self.subTest(requested=requested, expected=expected):
                tool = SearchDocumentsTool(
                    user_id="user-1",
                    selected_documents=["doc-1", "doc-2"],
                )
                mock_doc_processor = _build_doc_processor(async_results=[])

                with patch(
                    "backend.services.document_service.doc_processor",
                    mock_doc_processor,
                ), self.assertLogs("backend.orchestrator.tools.search_documents", level="INFO") as logs:
                    await tool._arun("pricing", max_results=requested)

                mock_doc_processor.search_documents.assert_awaited_once_with(
                    "pricing",
                    "user-1",
                    limit=expected,
                    selected_documents=["doc-1", "doc-2"],
                )
                self.assertTrue(
                    any(f"(max_results: {expected})" in entry for entry in logs.output)
                )

    async def test_run_and_arun_forward_selected_documents_with_same_limit(self):
        tool = SearchDocumentsTool(
            user_id="user-1",
            selected_documents=["doc-1", "doc-2"],
        )
        mock_doc_processor = _build_doc_processor(async_results=[], sync_results=[], documents=[])

        with patch("backend.services.document_service.doc_processor", mock_doc_processor):
            sync_result = tool._run("pricing", max_results=5)
            async_result = await tool._arun("pricing", max_results=5)

        mock_doc_processor.search_documents_sync.assert_called_once_with(
            "pricing",
            "user-1",
            limit=5,
            selected_documents=["doc-1", "doc-2"],
        )
        mock_doc_processor.search_documents.assert_awaited_once_with(
            "pricing",
            "user-1",
            limit=5,
            selected_documents=["doc-1", "doc-2"],
        )
        self.assertIn("No documents are available.", sync_result)
        self.assertIn("No documents are available.", async_result)
        self.assertIn("2 selected document(s)", sync_result)
        self.assertIn("2 selected document(s)", async_result)

    async def test_arun_matches_run_when_no_selected_documents(self):
        tool = SearchDocumentsTool(user_id="user-1", selected_documents=[])
        mock_doc_processor = _build_doc_processor()

        with patch("backend.services.document_service.doc_processor", mock_doc_processor):
            sync_result = tool._run("pricing", max_results=5)
            async_result = await tool._arun("pricing", max_results=5)

        expected = (
            "No documents are currently selected. Please select one or more "
            "documents to enable document search."
        )
        self.assertEqual(sync_result, expected)
        self.assertEqual(async_result, expected)
        mock_doc_processor.search_documents_sync.assert_not_called()
        mock_doc_processor.search_documents.assert_not_called()
