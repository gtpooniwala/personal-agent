"""Tests for document search model requirements."""

import asyncio
import os
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
