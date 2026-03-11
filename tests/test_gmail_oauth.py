"""Tests for Gmail OAuth helper logic."""

import unittest
from unittest.mock import patch

from backend.integrations.gmail_oauth import (
    InvalidRedirectTargetError,
    sanitize_return_to,
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
