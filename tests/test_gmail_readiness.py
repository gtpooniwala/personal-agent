"""Tests for Gmail integration readiness gating."""

import unittest
from unittest.mock import patch

from backend.orchestrator.tools.gmail import get_gmail_readiness


class TestGmailReadiness(unittest.TestCase):
    def test_not_ready_when_feature_flag_disabled(self):
        with patch("backend.orchestrator.tools.gmail.gmail_tool_ready") as tool_ready:
            ready, reasons = get_gmail_readiness(enable_gmail_integration=False)
        self.assertFalse(ready)
        self.assertEqual(reasons, ["feature_flag_disabled"])
        tool_ready.assert_not_called()

    def test_uses_user_scoped_runtime_readiness(self):
        with patch(
            "backend.orchestrator.tools.gmail.gmail_tool_ready",
            return_value=(False, ["account_not_connected"]),
        ) as tool_ready:
            ready, reasons = get_gmail_readiness(enable_gmail_integration=True, user_id="alice")
        self.assertFalse(ready)
        self.assertEqual(reasons, ["account_not_connected"])
        tool_ready.assert_called_once_with("alice")

    def test_ready_when_runtime_check_passes(self):
        with patch(
            "backend.orchestrator.tools.gmail.gmail_tool_ready",
            return_value=(True, []),
        ):
            ready, reasons = get_gmail_readiness(enable_gmail_integration=True, user_id="default")
        self.assertTrue(ready)
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
