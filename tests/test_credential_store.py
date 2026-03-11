"""Unit tests for encrypted integration credential storage."""

import unittest
from unittest.mock import patch

from backend.integrations.credential_store import (
    IntegrationCredentialStore,
    UnreadableCredentialError,
)


class TestCredentialStore(unittest.TestCase):
    def setUp(self):
        self.store = IntegrationCredentialStore()

    @patch("backend.integrations.credential_store.db_ops.upsert_integration_credential")
    @patch("backend.integrations.credential_store.db_ops.get_integration_credential")
    def test_load_json_marks_unreadable_credentials_as_error(
        self,
        mock_get_integration_credential,
        mock_upsert_integration_credential,
    ):
        invalid_token_type = type("InvalidToken", (Exception,), {})
        mock_get_integration_credential.return_value = {
            "ciphertext": "encrypted-payload",
            "account_label": "user@example.com",
            "scopes": ["scope-a"],
            "status": "connected",
            "expires_at": None,
            "key_version": "v1",
        }

        with patch.object(
            IntegrationCredentialStore,
            "_decrypt",
            side_effect=invalid_token_type("bad token"),
        ):
            with self.assertRaises(UnreadableCredentialError):
                self.store.load_json(
                    user_id="default",
                    provider="gmail",
                    credential_kind="oauth_token",
                )

        mock_upsert_integration_credential.assert_called_once_with(
            user_id="default",
            provider="gmail",
            credential_kind="oauth_token",
            ciphertext="encrypted-payload",
            account_label="user@example.com",
            scopes=["scope-a"],
            status="error",
            expires_at=None,
            key_version="v1",
        )

    @patch("backend.integrations.credential_store.db_ops.upsert_integration_credential")
    @patch("backend.integrations.credential_store.db_ops.get_integration_credential")
    def test_load_json_preserves_unexpected_decrypt_errors(
        self,
        mock_get_integration_credential,
        mock_upsert_integration_credential,
    ):
        mock_get_integration_credential.return_value = {
            "ciphertext": "encrypted-payload",
            "account_label": "user@example.com",
            "scopes": [],
            "status": "connected",
            "expires_at": None,
            "key_version": "v1",
        }

        with patch.object(
            IntegrationCredentialStore,
            "_decrypt",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                self.store.load_json(
                    user_id="default",
                    provider="gmail",
                    credential_kind="oauth_token",
                )

        mock_upsert_integration_credential.assert_not_called()
