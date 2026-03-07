import unittest
from unittest.mock import patch, MagicMock
import sys

# We need to mock the google modules BEFORE importing the tool if we want to ensure
# we can test the "import success" paths even without the libs installed.
# However, the tool imports them locally inside _run, so we can patch them during the test.

from backend.orchestrator.tools.gmail import GmailReadTool


class TestGmailToolErrors(unittest.TestCase):
    def setUp(self):
        self.tool = GmailReadTool()

    def test_run_returns_error_when_dependencies_missing(self):
        with patch(
            "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
            return_value=False,
        ):
            result = self.tool._run(query="test")
            self.assertIn("Gmail integration dependencies are missing", result)
            self.assertIn("pip install -r backend/requirements-gmail.txt", result)

    def test_run_returns_error_when_credentials_missing(self):
        with (
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail.os.path.exists", return_value=False
            ),
        ):
            result = self.tool._run(query="test")
            self.assertIn("Gmail credentials file not found", result)

    def test_run_handles_import_error_gracefully(self):
        # Simulate dependencies_installed=True but import fails
        with (
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch("backend.orchestrator.tools.gmail.os.path.exists", return_value=True),
        ):
            # We patch builtins.__import__ to raise ImportError when google modules are requested
            original_import = __import__

            def side_effect(name, globals=None, locals=None, fromlist=(), level=0):
                if name.startswith("google"):
                    raise ImportError(f"No module named {name}")
                return original_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=side_effect):
                result = self.tool._run(query="test")
                self.assertIn("Failed to import Gmail dependencies", result)

    def test_run_handles_token_load_error(self):
        # Mock the google modules so the local import succeeds
        mock_google = MagicMock()
        modules = {
            "google.auth.transport.requests": mock_google,
            "google.auth.exceptions": mock_google,
            "google_auth_oauthlib.flow": mock_google,
            "googleapiclient.discovery": mock_google,
            "googleapiclient.errors": mock_google,
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_credentials_path",
                return_value="creds.json",
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_token_path",
                return_value="token.pickle",
            ),
            patch(
                "backend.orchestrator.tools.gmail.os.path.exists",
                side_effect=lambda p: p in ["creds.json", "token.pickle"],
            ),
            patch(
                "backend.orchestrator.tools.gmail.pickle.load",
                side_effect=Exception("Corrupt pickle"),
            ),
            patch("builtins.open", new_callable=MagicMock),
        ):
            result = self.tool._run(query="test")
            self.assertIn("Failed to read existing token", result)
            self.assertIn("Corrupt pickle", result)

    def test_run_handles_refresh_error(self):
        # Create a mock RefreshError class
        class MockRefreshError(Exception):
            pass

        mock_google_auth_exceptions = MagicMock()
        mock_google_auth_exceptions.RefreshError = MockRefreshError

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "some_token"
        mock_creds.refresh.side_effect = MockRefreshError("Token revoked")

        modules = {
            "google.auth.transport.requests": MagicMock(),
            "google.auth.exceptions": mock_google_auth_exceptions,
            "google_auth_oauthlib.flow": MagicMock(),
            "googleapiclient.discovery": MagicMock(),
            "googleapiclient.errors": MagicMock(),
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_credentials_path",
                return_value="creds.json",
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_token_path",
                return_value="token.pickle",
            ),
            patch(
                "backend.orchestrator.tools.gmail.os.path.exists",
                side_effect=lambda p: p in ["creds.json", "token.pickle"],
            ),
            patch(
                "backend.orchestrator.tools.gmail.pickle.load", return_value=mock_creds
            ),
            patch("builtins.open", new_callable=MagicMock),
        ):
            result = self.tool._run(query="test")
            self.assertIn("Gmail auth expired and refresh failed", result)
            self.assertIn("Token revoked", result)

    def test_run_handles_api_http_error(self):
        # Create a mock HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__(str(content))

        mock_google_apiclient_errors = MagicMock()
        mock_google_apiclient_errors.HttpError = MockHttpError

        mock_creds = MagicMock()
        mock_creds.valid = True

        # Mock service and execution
        mock_build = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_resp = MagicMock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = MockHttpError(
            mock_resp, b"Access Not Configured"
        )

        mock_google_apiclient_discovery = MagicMock()
        mock_google_apiclient_discovery.build = mock_build

        modules = {
            "google.auth.transport.requests": MagicMock(),
            "google.auth.exceptions": MagicMock(),
            "google_auth_oauthlib.flow": MagicMock(),
            "googleapiclient.discovery": mock_google_apiclient_discovery,
            "googleapiclient.errors": mock_google_apiclient_errors,
        }

        with (
            patch.dict(sys.modules, modules),
            patch(
                "backend.orchestrator.tools.gmail._gmail_dependencies_installed",
                return_value=True,
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_credentials_path",
                return_value="creds.json",
            ),
            patch(
                "backend.orchestrator.tools.gmail._get_token_path",
                return_value="token.pickle",
            ),
            patch(
                "backend.orchestrator.tools.gmail.os.path.exists",
                side_effect=lambda p: p in ["creds.json", "token.pickle"],
            ),
            patch(
                "backend.orchestrator.tools.gmail.pickle.load", return_value=mock_creds
            ),
            patch("builtins.open", new_callable=MagicMock),
        ):
            result = self.tool._run(query="test")
            self.assertIn("Gmail API error", result)
            self.assertIn("Access Not Configured", result)


if __name__ == "__main__":
    unittest.main()
