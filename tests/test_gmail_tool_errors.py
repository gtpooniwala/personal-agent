import sys
import unittest
from unittest.mock import MagicMock, patch

from backend.orchestrator.tools.gmail import GmailReadTool


class TestGmailToolErrors(unittest.TestCase):
    def setUp(self):
        self.tool = GmailReadTool(user_id="test-user")

    def test_run_returns_error_when_dependencies_missing(self):
        with patch(
            "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
            return_value=False,
        ):
            result = self.tool._run(query="test")
        self.assertIn("Gmail integration dependencies are missing", result)

    def test_run_returns_connect_message_when_account_not_connected(self):
        with (
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.get_connection_status",
                return_value={"ready": True, "connected": False, "reasons": ["account_not_connected"]},
            ),
            patch("backend.orchestrator.tools.gmail.load_user_credentials", return_value=None),
        ):
            result = self.tool._run(query="test")
        self.assertIn("/api/v1/gmail/connect", result)

    def test_run_handles_refresh_error(self):
        class MockRefreshError(Exception):
            pass

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh-token"
        mock_creds.refresh.side_effect = MockRefreshError("Token revoked")

        modules = {
            "google.auth.transport.requests": MagicMock(Request=MagicMock()),
            "google.auth.exceptions": MagicMock(RefreshError=MockRefreshError),
            "googleapiclient.discovery": MagicMock(build=MagicMock()),
            "googleapiclient.errors": MagicMock(HttpError=Exception),
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.get_connection_status",
                return_value={"ready": True, "connected": True, "account_label": "user@example.com"},
            ),
            patch("backend.orchestrator.tools.gmail.load_user_credentials", return_value=mock_creds),
            patch("backend.orchestrator.tools.gmail.save_user_credentials"),
        ):
            result = self.tool._run(query="test")
        self.assertIn("refresh failed", result.lower())
        self.assertIn("Token revoked", result)

    def test_run_handles_api_http_error(self):
        class MockHttpError(Exception):
            pass

        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = MockHttpError("boom")

        modules = {
            "google.auth.transport.requests": MagicMock(Request=MagicMock()),
            "google.auth.exceptions": MagicMock(RefreshError=Exception),
            "googleapiclient.discovery": MagicMock(build=MagicMock(return_value=mock_service)),
            "googleapiclient.errors": MagicMock(HttpError=MockHttpError),
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.get_connection_status",
                return_value={"ready": True, "connected": True, "account_label": "user@example.com"},
            ),
            patch("backend.orchestrator.tools.gmail.load_user_credentials", return_value=mock_creds),
        ):
            result = self.tool._run(query="test")
        self.assertIn("Gmail API error during message search", result)

    def test_run_keeps_explicit_empty_label_filter(self):
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {"messages": []}
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value = mock_messages

        modules = {
            "google.auth.transport.requests": MagicMock(Request=MagicMock()),
            "google.auth.exceptions": MagicMock(RefreshError=Exception),
            "googleapiclient.discovery": MagicMock(build=MagicMock(return_value=mock_service)),
            "googleapiclient.errors": MagicMock(HttpError=Exception),
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.get_connection_status",
                return_value={"ready": True, "connected": True, "account_label": "user@example.com"},
            ),
            patch("backend.orchestrator.tools.gmail.load_user_credentials", return_value=mock_creds),
        ):
            self.tool._run(query="test", label_ids=[])

        mock_messages.list.assert_called_once_with(
            userId="me",
            maxResults=5,
            labelIds=[],
            q="test",
        )

    def test_run_logs_safe_query_metadata_only(self):
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_message = {
            "payload": {"headers": []},
            "snippet": "snippet",
        }
        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {"messages": [{"id": "abc"}]}
        mock_messages.get.return_value.execute.return_value = mock_message
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value = mock_messages

        modules = {
            "google.auth.transport.requests": MagicMock(Request=MagicMock()),
            "google.auth.exceptions": MagicMock(RefreshError=Exception),
            "googleapiclient.discovery": MagicMock(build=MagicMock(return_value=mock_service)),
            "googleapiclient.errors": MagicMock(HttpError=Exception),
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.get_connection_status",
                return_value={"ready": True, "connected": True, "account_label": "user@example.com"},
            ),
            patch("backend.orchestrator.tools.gmail.load_user_credentials", return_value=mock_creds),
            patch("backend.orchestrator.tools.gmail.logger.info") as mock_logger_info,
        ):
            self.tool._run(query="subject:payroll", label_ids=["INBOX", "UNREAD"])

        _, kwargs = mock_logger_info.call_args
        self.assertEqual(kwargs["extra"]["query_present"], True)
        self.assertEqual(kwargs["extra"]["query_length"], len("subject:payroll"))
        self.assertEqual(kwargs["extra"]["label_ids_count"], 2)
        self.assertNotIn("query", kwargs["extra"])
        self.assertNotIn("label_ids", kwargs["extra"])


if __name__ == "__main__":
    unittest.main()
