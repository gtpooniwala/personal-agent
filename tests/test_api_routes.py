"""API route tests against the FastAPI app with mocked dependencies."""
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

API_TESTS_AVAILABLE = True
API_IMPORT_ERROR = ""

try:
    from fastapi.testclient import TestClient
    from backend.api import routes, runtime_routes
    from backend.main import app
except Exception as exc:
    API_TESTS_AVAILABLE = False
    API_IMPORT_ERROR = str(exc)


@unittest.skipUnless(API_TESTS_AVAILABLE, f"API test dependencies unavailable: {API_IMPORT_ERROR}")
class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["version"], "1.0.0")
        self.assertIn("timestamp", payload)

    @patch("backend.api.runtime_routes.runtime_service.submit_run", new_callable=AsyncMock)
    def test_runtime_chat_submit_endpoint(self, mock_submit_run):
        mock_submit_run.return_value = {
            "run_id": "run-1",
            "status": "queued",
            "conversation_id": "conv-1",
        }
        response = self.client.post(
            "/chat",
            json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["conversation_id"], "conv-1")

    def test_versioned_chat_endpoint_removed(self):
        response = self.client.post(
            "/api/v1/chat",
            json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
        )
        self.assertEqual(response.status_code, 404)

    @patch("backend.api.runtime_routes.runtime_service.get_run_status", new_callable=AsyncMock)
    def test_runtime_run_status_endpoint(self, mock_get_status):
        mock_get_status.return_value = {
            "run_id": "run-1",
            "status": "running",
            "conversation_id": "conv-1",
            "created_at": "2026-03-06T10:00:00Z",
            "updated_at": "2026-03-06T10:00:01Z",
            "error": None,
            "result": None,
        }
        response = self.client.get("/runs/run-1/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "running")

    @patch("backend.api.runtime_routes.runtime_service.get_run_events", new_callable=AsyncMock)
    def test_runtime_run_events_endpoint(self, mock_get_events):
        mock_get_events.return_value = {
            "run_id": "run-1",
            "events": [
                {
                    "event_id": "1",
                    "type": "started",
                    "status": "running",
                    "message": "Run started",
                    "created_at": "2026-03-06T10:00:01Z",
                    "tool": None,
                    "metadata": None,
                }
            ],
            "next_after": "1",
            "has_more": False,
        }
        response = self.client.get("/runs/run-1/events?limit=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["next_after"], "1")
        self.assertEqual(len(payload["events"]), 1)

    @patch("backend.api.routes.db_ops.delete_conversation")
    @patch("backend.api.routes.orchestrator.generate_conversation_title", new_callable=AsyncMock)
    @patch("backend.api.routes.orchestrator.get_conversations")
    def test_get_conversations_endpoint_is_read_only(
        self,
        mock_get_conversations,
        mock_generate_conversation_title,
        mock_delete_conversation,
    ):
        mock_get_conversations.return_value = [
            {
                "id": "conv-1",
                "title": "Test",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "message_count": 2,
            }
        ]
        response = self.client.get("/api/v1/conversations")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], "conv-1")
        mock_get_conversations.assert_called_once_with()
        mock_generate_conversation_title.assert_not_called()
        mock_delete_conversation.assert_not_called()

    def test_upload_document_rejects_non_pdf(self):
        response = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only PDF files are supported", response.text)

    @patch("backend.api.routes.doc_processor.process_pdf_upload", new_callable=AsyncMock)
    def test_upload_document_success(self, mock_process_pdf_upload):
        mock_process_pdf_upload.return_value = "doc-123"
        response = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.pdf", b"%PDF-1.4 mock", "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document_id"], "doc-123")
        self.assertEqual(payload["filename"], "sample.pdf")
        self.assertEqual(payload["status"], "processing")

    @patch("backend.api.routes.doc_processor.process_pdf_upload", new_callable=AsyncMock)
    def test_upload_document_processing_failure_returns_deterministic_500(self, mock_process_pdf_upload):
        mock_process_pdf_upload.side_effect = RuntimeError("boom upload")
        response = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.pdf", b"%PDF-1.4 mock", "application/pdf")},
        )
        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertIn("Failed to upload document", payload["detail"])
        self.assertNotIn("unbound", payload["detail"].lower())
        self.assertNotIn("local variable", payload["detail"].lower())

    @patch("backend.api.routes.doc_processor.delete_document")
    def test_delete_document_not_found(self, mock_delete_document):
        mock_delete_document.return_value = False
        response = self.client.delete("/api/v1/documents/missing-doc")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
