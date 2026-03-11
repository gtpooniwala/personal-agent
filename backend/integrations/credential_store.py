from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from backend.config import settings
from backend.database.operations import db_ops


class CredentialStoreError(RuntimeError):
    """Base error for integration credential storage."""


class MissingCredentialEncryptionKeyError(CredentialStoreError):
    """Raised when encrypted credential storage is not configured."""


class MissingCredentialDependencyError(CredentialStoreError):
    """Raised when the crypto dependency is unavailable."""


class UnreadableCredentialError(CredentialStoreError):
    """Raised when stored credential ciphertext can no longer be decrypted."""


def _load_fernet() -> Any:
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - exercised via runtime guard
        raise MissingCredentialDependencyError(
            "Encrypted credential storage requires the `cryptography` package."
        ) from exc

    key = (settings.credentials_master_key or "").strip()
    if not key:
        raise MissingCredentialEncryptionKeyError(
            "CREDENTIALS_MASTER_KEY must be configured to store integration credentials."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive validation
        raise MissingCredentialEncryptionKeyError(
            "CREDENTIALS_MASTER_KEY is invalid. Generate one with `python3 -c "
            "\"import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\"`."
        ) from exc


class IntegrationCredentialStore:
    """Small encrypted store backed by PostgreSQL rows."""

    def ensure_configured(self) -> None:
        _load_fernet()

    def _encrypt(self, payload: Dict[str, Any]) -> str:
        fernet = _load_fernet()
        plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return fernet.encrypt(plaintext).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> Dict[str, Any]:
        fernet = _load_fernet()
        plaintext = fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        return json.loads(plaintext)

    def save_json(
        self,
        *,
        user_id: str,
        provider: str,
        credential_kind: str,
        payload: Dict[str, Any],
        account_label: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        status: str = "connected",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        ciphertext = self._encrypt(payload)
        return db_ops.upsert_integration_credential(
            user_id=user_id,
            provider=provider,
            credential_kind=credential_kind,
            ciphertext=ciphertext,
            account_label=account_label,
            scopes=scopes,
            status=status,
            expires_at=expires_at,
        )

    def load_json(
        self,
        *,
        user_id: str,
        provider: str,
        credential_kind: str,
    ) -> Optional[Dict[str, Any]]:
        record = db_ops.get_integration_credential(
            user_id=user_id,
            provider=provider,
            credential_kind=credential_kind,
        )
        if record is None:
            return None
        try:
            payload = self._decrypt(record["ciphertext"])
        except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError):
            raise
        except Exception as exc:
            if exc.__class__.__name__ != "InvalidToken" and not isinstance(exc, json.JSONDecodeError):
                raise
            db_ops.upsert_integration_credential(
                user_id=user_id,
                provider=provider,
                credential_kind=credential_kind,
                ciphertext=record["ciphertext"],
                account_label=record.get("account_label"),
                scopes=record.get("scopes") or [],
                status="error",
                expires_at=record.get("expires_at"),
                key_version=record.get("key_version") or "v1",
            )
            raise UnreadableCredentialError(
                "Stored integration credentials can no longer be decrypted. Please reconnect the integration."
            ) from exc
        payload["_metadata"] = {
            "account_label": record.get("account_label"),
            "status": record.get("status"),
            "expires_at": record.get("expires_at"),
            "scopes": record.get("scopes") or [],
        }
        return payload

    def get_status(
        self,
        *,
        user_id: str,
        provider: str,
        credential_kind: str,
    ) -> Optional[Dict[str, Any]]:
        record = db_ops.get_integration_credential(
            user_id=user_id,
            provider=provider,
            credential_kind=credential_kind,
        )
        if record is None:
            return None
        return {
            "account_label": record.get("account_label"),
            "status": record.get("status"),
            "expires_at": record.get("expires_at"),
            "scopes": record.get("scopes") or [],
        }

    def delete(
        self,
        *,
        user_id: str,
        provider: str,
        credential_kind: str,
    ) -> bool:
        return db_ops.delete_integration_credential(
            user_id=user_id,
            provider=provider,
            credential_kind=credential_kind,
        )


credential_store = IntegrationCredentialStore()
