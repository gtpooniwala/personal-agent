"""Tests for Gmail integration readiness gating."""
import unittest
from unittest.mock import patch

from backend.orchestrator.tools.gmail import get_gmail_readiness


class TestGmailReadiness(unittest.TestCase):
    def test_not_ready_when_feature_flag_disabled(self):
        with patch("backend.orchestrator.tools.gmail._gmail_dependencies_installed", return_value=True), \
             patch("backend.orchestrator.tools.gmail._get_credentials_path", return_value="/tmp/creds.json"), \
             patch("backend.orchestrator.tools.gmail.os.path.exists", return_value=True):
            ready, reasons = get_gmail_readiness(enable_gmail_integration=False)
        self.assertFalse(ready)
        self.assertIn("feature_flag_disabled", reasons)

    def test_not_ready_when_dependencies_missing(self):
        with patch("backend.orchestrator.tools.gmail._gmail_dependencies_installed", return_value=False), \
             patch("backend.orchestrator.tools.gmail._get_credentials_path", return_value="/tmp/creds.json"), \
             patch("backend.orchestrator.tools.gmail.os.path.exists", return_value=True):
            ready, reasons = get_gmail_readiness(enable_gmail_integration=True)
        self.assertFalse(ready)
        self.assertIn("dependencies_missing", reasons)

    def test_not_ready_when_credentials_missing(self):
        with patch("backend.orchestrator.tools.gmail._gmail_dependencies_installed", return_value=True), \
             patch("backend.orchestrator.tools.gmail._get_credentials_path", return_value="/tmp/creds.json"), \
             patch("backend.orchestrator.tools.gmail.os.path.exists", return_value=False):
            ready, reasons = get_gmail_readiness(enable_gmail_integration=True)
        self.assertFalse(ready)
        self.assertIn("credentials_missing", reasons)

    def test_ready_when_flag_dependencies_and_credentials_present(self):
        with patch("backend.orchestrator.tools.gmail._gmail_dependencies_installed", return_value=True), \
             patch("backend.orchestrator.tools.gmail._get_credentials_path", return_value="/tmp/creds.json"), \
             patch("backend.orchestrator.tools.gmail.os.path.exists", return_value=True):
            ready, reasons = get_gmail_readiness(enable_gmail_integration=True)
        self.assertTrue(ready)
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
