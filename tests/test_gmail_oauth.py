"""Tests for Gmail OAuth helper logic."""

import unittest
from unittest.mock import patch

GMAIL_OAUTH_TESTS_AVAILABLE = True
GMAIL_OAUTH_IMPORT_ERROR = ""

try:
    from backend.integrations.gmail_oauth import (
        InvalidRedirectTargetError,
        get_connection_status,
        sanitize_return_to,
    )
except (ImportError, ModuleNotFoundError) as exc:
    GMAIL_OAUTH_TESTS_AVAILABLE = False
    GMAIL_OAUTH_IMPORT_ERROR = str(exc)


@unittest.skipUnless(
    GMAIL_OAUTH_TESTS_AVAILABLE,
    f"Gmail OAuth test dependencies unavailable: {GMAIL_OAUTH_IMPORT_ERROR}",
)
class TestSanitizeReturnTo(unittest.TestCase):
    @patch("backend.integrations.gmail_oauth.settings.frontend_url", "http://localhost:3001")
    @patch("backend.integrations.gmail_oauth.settings.allowed_origins", "http://localhost:3001,http://127.0.0.1:3001")
    def test_allows_relative_paths(self):
        self.assertEqual(
            sanitize_return_to("/settings?tab=gmail"),
            "/settings?tab=gmail",
        )

    @patch("backend.integrations.gmail_oauth.settings.frontend_url", "http://localhost:3001")
    @patch("backend.integrations.gmail_oauth.settings.allowed_origins", "http://localhost:3001,http://127.0.0.1:3001")
    def test_allows_configured_frontend_origin(self):
        self.assertEqual(
            sanitize_return_to("http://localhost:3001/settings?tab=gmail"),
            "http://localhost:3001/settings?tab=gmail",
        )

    @patch("backend.integrations.gmail_oauth.settings.frontend_url", "http://localhost:3001")
    @patch("backend.integrations.gmail_oauth.settings.allowed_origins", "http://localhost:3001,http://127.0.0.1:3001")
    def test_rejects_external_origins(self):
        with self.assertRaises(InvalidRedirectTargetError):
            sanitize_return_to("https://evil.example.com/callback")


@unittest.skipUnless(
    GMAIL_OAUTH_TESTS_AVAILABLE,
    f"Gmail OAuth test dependencies unavailable: {GMAIL_OAUTH_IMPORT_ERROR}",
)
class TestGmailConnectionStatus(unittest.TestCase):
    @patch("backend.integrations.gmail_oauth.gmail_oauth_ready", return_value=(True, []))
    @patch("backend.integrations.gmail_oauth.credential_store.get_status")
    def test_non_connected_credential_status_is_exposed_as_reason(
        self,
        mock_get_status,
        _mock_gmail_ready,
    ):
        mock_get_status.return_value = {
            "account_label": "user@example.com",
            "status": "expired",
            "expires_at": None,
            "scopes": [],
        }

        status = get_connection_status("default")

        self.assertEqual(status["connected"], False)
        self.assertEqual(status["reasons"], ["credential_expired"])
        self.assertEqual(status["account_label"], "user@example.com")


if __name__ == "__main__":
    unittest.main()
