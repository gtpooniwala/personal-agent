"""Tests for Gmail OAuth helper logic."""

import unittest
from unittest.mock import patch

GMAIL_OAUTH_TESTS_AVAILABLE = True
GMAIL_OAUTH_IMPORT_ERROR = ""

try:
    from backend.integrations.gmail_oauth import (
        InvalidRedirectTargetError,
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


if __name__ == "__main__":
    unittest.main()
