"""API route tests against the FastAPI app with mocked dependencies."""
from contextlib import ExitStack
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
    import backend.main as main_module
    from backend.main import app, settings as app_settings
    from backend.integrations.gmail_oauth import (
        GmailOAuthConfigurationError,
        InvalidGmailOAuthStateError,
    )
except Exception as exc:
    API_TESTS_AVAILABLE = False
    API_IMPORT_ERROR = str(exc)


@unittest.skipUnless(API_TESTS_AVAILABLE, f"API test dependencies unavailable: {API_IMPORT_ERROR}")
class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        self._default_settings = self._override_settings(
            environment="local",
            agent_api_key=None,
        )
        self._default_settings.__enter__()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self._default_settings.__exit__(None, None, None)

    def _override_settings(self, **overrides):
        stack = ExitStack()
        for name, value in overrides.items():
            stack.enter_context(patch.object(app_settings, name, value))
        return stack

    @staticmethod
    def _auth_headers(token="test-agent-key"):
        return {"Authorization": f"Bearer {token}"}

    def test_health_endpoint_stays_open_locally_without_agent_api_key(self):
        with self._override_settings(environment="local", agent_api_key=None):
            response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["version"], "1.0.0")
        self.assertIn("timestamp", payload)

    def test_lifespan_requires_agent_api_key_outside_local_environment(self):
        with self._override_settings(
            environment="production",
            agent_api_key=None,
            openai_api_key="test-openai-key",
            gemini_api_key=None,
        ):
            with self.assertRaisesRegex(RuntimeError, "AGENT_API_KEY"):
                with TestClient(app):
                    pass

    def test_health_endpoint_requires_bearer_token_when_agent_api_key_is_configured(self):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Unauthorized"})
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.assertIn("X-Request-ID", response.headers)

    def test_health_endpoint_unauthorized_response_includes_cors_headers(self):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.get(
                "/api/v1/health",
                headers={"Origin": "http://localhost:3000"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        self.assertEqual(response.headers["Access-Control-Allow-Credentials"], "true")

    def test_health_endpoint_unauthorized_response_handles_mixed_wildcard_origins(self):
        with patch.object(main_module, "allow_origins", ["*", "http://localhost:3000"]), patch.object(
            main_module,
            "allow_credentials",
            True,
        ), self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.get(
                "/api/v1/health",
                headers={"Origin": "http://example.com"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://example.com")
        self.assertEqual(response.headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(response.headers["Vary"], "Origin")

    def test_health_endpoint_accepts_bearer_token_when_configured(self):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.get(
                "/api/v1/health",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")

    @patch("backend.api.routes.orchestrator.tool_registry.refresh_runtime_capabilities")
    @patch("backend.api.routes.get_connection_status")
    def test_gmail_status_endpoint_returns_connection_status(
        self,
        mock_get_status,
        mock_refresh_capabilities,
    ):
        mock_get_status.return_value = {
            "provider": "gmail",
            "connected": False,
            "ready": True,
            "reasons": ["account_not_connected"],
            "account_label": None,
            "expires_at": None,
            "scopes": [],
        }
        response = self.client.get("/api/v1/gmail/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "gmail")
        mock_refresh_capabilities.assert_called_once_with(force=True)

    @patch("backend.api.routes.create_connect_url")
    def test_gmail_connect_endpoint_redirects_to_google(self, mock_create_connect_url):
        mock_create_connect_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test"
        response = self.client.get(
            "/api/v1/gmail/connect?return_to=http://localhost:3000/settings",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 307)
        self.assertEqual(
            response.headers["location"],
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=test",
        )

    @patch(
        "backend.api.routes.create_connect_url",
        side_effect=GmailOAuthConfigurationError("oauth not configured"),
    )
    def test_gmail_connect_endpoint_surfaces_configuration_gaps_as_service_unavailable(self, _mock_create_connect_url):
        response = self.client.get("/api/v1/gmail/connect", follow_redirects=False)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "oauth not configured"})

    @patch("backend.api.routes.orchestrator.tool_registry.refresh_runtime_capabilities")
    @patch("backend.api.routes.exchange_callback")
    def test_gmail_callback_redirects_back_to_frontend(
        self,
        mock_exchange_callback,
        mock_refresh_capabilities,
    ):
        mock_exchange_callback.return_value = {
            "user_id": "default",
            "return_to": "http://localhost:3000/settings",
            "account_label": "user@example.com",
        }
        response = self.client.get(
            "/api/v1/gmail/callback?state=test-state&code=test-code",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "http://localhost:3000/settings?gmail=connected")
        mock_refresh_capabilities.assert_called_once_with(force=True)

    @patch(
        "backend.api.routes.exchange_callback",
        side_effect=InvalidGmailOAuthStateError("Invalid or expired Gmail OAuth state."),
    )
    def test_gmail_callback_returns_bad_request_for_invalid_state(self, _mock_exchange_callback):
        response = self.client.get(
            "/api/v1/gmail/callback?state=expired-state&code=test-code",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid or expired Gmail OAuth state."})

    @patch("backend.api.runtime_routes.runtime_service.submit_run", new_callable=AsyncMock)
    def test_runtime_chat_submit_endpoint_requires_bearer_token(self, mock_submit_run):
        mock_submit_run.return_value = {
            "run_id": "run-1",
            "status": "queued",
            "conversation_id": "conv-1",
        }
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            missing_response = self.client.post(
                "/chat",
                json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
            )
            wrong_token_response = self.client.post(
                "/chat",
                json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
                headers=self._auth_headers("wrong-token"),
            )
            response = self.client.post(
                "/chat",
                json={"message": "hi", "conversation_id": "conv-1", "selected_documents": []},
                headers=self._auth_headers(),
            )
        self.assertEqual(missing_response.status_code, 401)
        self.assertEqual(wrong_token_response.status_code, 401)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["conversation_id"], "conv-1")
        mock_submit_run.assert_awaited_once()

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
            "attempt_count": 1,
            "created_at": "2026-03-06T10:00:00Z",
            "updated_at": "2026-03-06T10:00:01Z",
            "started_at": "2026-03-06T10:00:00Z",
            "completed_at": None,
            "error": None,
            "result": None,
        }
        response = self.client.get("/runs/run-1/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["attempt_count"], 1)

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

    @patch("backend.api.scheduler_routes.db_ops.list_scheduled_tasks")
    def test_scheduler_routes_reject_missing_bearer_token_before_route_logic_runs(self, mock_list_tasks):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.get("/scheduler/tasks")
        self.assertEqual(response.status_code, 401)
        mock_list_tasks.assert_not_called()

    def test_docs_and_openapi_require_bearer_token_when_enabled(self):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            docs_response = self.client.get("/docs")
            openapi_response = self.client.get("/openapi.json")
        self.assertEqual(docs_response.status_code, 401)
        self.assertEqual(openapi_response.status_code, 401)

    def test_options_preflight_bypasses_bearer_auth(self):
        with self._override_settings(environment="local", agent_api_key="test-agent-key"):
            response = self.client.options(
                "/chat",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access-control-allow-origin", response.headers)

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
