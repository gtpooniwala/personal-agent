"""Tests for document search model requirements."""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.llm import MissingProviderKeyError
from backend.services.document_service import DocumentProcessor


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._rows)

    def close(self):
        self.closed = True


class TestDocumentServiceModelRequirements(unittest.TestCase):
    def test_search_documents_async_requires_embeddings_not_chat_model(self):
        embeddings = Mock()
        embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        fake_session = _FakeSession(rows=[])

        with patch(
            "backend.services.document_service.create_embeddings_model",
            return_value=embeddings,
        ), patch(
            "backend.services.document_service.create_chat_model",
            side_effect=MissingProviderKeyError("chat model key missing"),
        ), patch(
            "backend.services.document_service.db_ops.get_session",
            return_value=fake_session,
        ):
            processor = DocumentProcessor()
            results = asyncio.run(processor.search_documents("find contract"))

        self.assertEqual(results, [])
        embeddings.aembed_query.assert_awaited_once_with("find contract")
        self.assertTrue(fake_session.closed)

    def test_search_documents_sync_requires_embeddings_not_chat_model(self):
        embeddings = Mock()
        embeddings.embed_query = Mock(return_value=[0.1, 0.2, 0.3])
        fake_session = _FakeSession(rows=[])

        with patch(
            "backend.services.document_service.create_embeddings_model",
            return_value=embeddings,
        ), patch(
            "backend.services.document_service.create_chat_model",
            side_effect=MissingProviderKeyError("chat model key missing"),
        ), patch(
            "backend.services.document_service.db_ops.get_session",
            return_value=fake_session,
        ):
            processor = DocumentProcessor()
            results = processor.search_documents_sync("find contract")

        self.assertEqual(results, [])
        embeddings.embed_query.assert_called_once_with("find contract")
        self.assertTrue(fake_session.closed)


class TestDocumentServiceUploadFailureHandling(unittest.TestCase):
    def test_process_pdf_upload_failure_before_document_creation_preserves_original_error(self):
        with patch(
            "backend.services.document_service.create_embeddings_model",
            return_value=Mock(),
        ), patch(
            "backend.services.document_service.create_chat_model",
            return_value=Mock(),
        ):
            processor = DocumentProcessor()

        with patch.object(
            processor,
            "_require_processing_models",
            side_effect=RuntimeError("models unavailable"),
        ), patch(
            "backend.services.document_service.db_ops.get_session",
        ) as mock_get_session:
            with self.assertRaisesRegex(RuntimeError, "models unavailable"):
                asyncio.run(
                    processor.process_pdf_upload(
                        file_content=b"%PDF-1.4 mock",
                        filename="sample.pdf",
                    )
                )

        mock_get_session.assert_not_called()

    def test_process_pdf_upload_failure_after_document_creation_marks_document_failed(self):
        with patch(
            "backend.services.document_service.create_embeddings_model",
            return_value=Mock(),
        ), patch(
            "backend.services.document_service.create_chat_model",
            return_value=Mock(),
        ):
            processor = DocumentProcessor()

        with tempfile.TemporaryDirectory() as tmpdir:
            processor.upload_dir = Path(tmpdir)

            create_session = Mock()

            def _assign_document_id(document):
                document.id = "doc-123"

            create_session.add.side_effect = _assign_document_id

            failed_document = Mock()
            update_session = Mock()
            update_session.query.return_value.filter.return_value.first.return_value = failed_document

            with patch.object(
                processor,
                "_require_processing_models",
                return_value=None,
            ), patch.object(
                processor,
                "_process_document_content",
                new=AsyncMock(side_effect=RuntimeError("content failure")),
            ), patch(
                "backend.services.document_service.db_ops.get_session",
                side_effect=[create_session, update_session],
            ):
                with self.assertRaisesRegex(RuntimeError, "content failure"):
                    asyncio.run(
                        processor.process_pdf_upload(
                            file_content=b"%PDF-1.4 mock",
                            filename="sample.pdf",
                        )
                    )

        create_session.add.assert_called_once()
        create_session.commit.assert_called_once()
        create_session.close.assert_called_once()
        update_session.query.assert_called_once()
        self.assertEqual(failed_document.processed, "failed")
        update_session.commit.assert_called_once()
        update_session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
