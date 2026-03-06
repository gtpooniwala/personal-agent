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
    from backend.api import routes
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

    @patch("backend.api.routes.orchestrator.process_request", new_callable=AsyncMock)
    def test_chat_endpoint(self, mock_process_request):
        mock_process_request.return_value = {
            "response": "hello",
            "conversation_id": "conv-1",
            "orchestration_actions": [{"tool": "calculator", "input": "2+2", "output": "4"}],
            "token_usage": 42,
            "cost": 0.001,
        }
        response = self.client.post(
            "/api/v1/chat",
            json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["response"], "hello")
        self.assertEqual(payload["conversation_id"], "conv-1")
        self.assertEqual(payload["token_usage"], 42)

    @patch("backend.api.routes.orchestrator.get_conversations")
    @patch("backend.api.routes.check_conversation_maintenance")
    def test_get_conversations_endpoint(self, mock_maintenance, mock_get_conversations):
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
        mock_maintenance.assert_called_once()

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
