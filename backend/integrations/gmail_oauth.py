from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from backend.config import settings
from backend.database.operations import db_ops
from backend.integrations.credential_store import (
    MissingCredentialDependencyError,
    MissingCredentialEncryptionKeyError,
    credential_store,
)

GMAIL_PROVIDER = "gmail"
GMAIL_CREDENTIAL_KIND = "oauth_token"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailOAuthConfigurationError(RuntimeError):
    """Raised when app-level Gmail OAuth configuration is incomplete."""


class InvalidGmailOAuthStateError(ValueError):
    """Raised when the OAuth callback state is missing, invalid, or expired."""


class InvalidRedirectTargetError(ValueError):
    """Raised when a post-auth redirect target is unsafe."""


def _gmail_dependencies_installed() -> bool:
    required_modules = (
        "google.auth.transport.requests",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
        "googleapiclient.discovery",
    )
    for module_name in required_modules:
        try:
            if find_spec(module_name) is None:
                return False
        except ModuleNotFoundError:
            return False
    return True


def gmail_oauth_ready() -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not settings.enable_gmail_integration:
        reasons.append("feature_flag_disabled")
    if not _gmail_dependencies_installed():
        reasons.append("dependencies_missing")
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret):
        reasons.append("oauth_client_missing")
    if not settings.google_oauth_redirect_uri:
        reasons.append("redirect_uri_missing")
    try:
        credential_store.ensure_configured()
    except MissingCredentialDependencyError:
        if "dependencies_missing" not in reasons:
            reasons.append("dependencies_missing")
    except MissingCredentialEncryptionKeyError:
        reasons.append("credential_store_unconfigured")
    return len(reasons) == 0, reasons


def gmail_connected(user_id: str) -> bool:
    try:
        record = credential_store.get_status(
            user_id=user_id,
            provider=GMAIL_PROVIDER,
            credential_kind=GMAIL_CREDENTIAL_KIND,
        )
    except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError):
        return False
    return record is not None and record.get("status") == "connected"


def gmail_tool_ready(user_id: str) -> Tuple[bool, List[str]]:
    ready, reasons = gmail_oauth_ready()
    if not ready:
        return False, reasons
    if not gmail_connected(user_id):
        return False, ["account_not_connected"]
    return True, []


def _oauth_client_config() -> Dict[str, Dict[str, Any]]:
    return {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }


def _build_flow(*, state: Optional[str] = None):
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _oauth_client_config(),
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.google_oauth_redirect_uri
    return flow


def _allowed_return_to_origins() -> List[str]:
    origins: List[str] = []
    for candidate in [settings.frontend_url, *(settings.allowed_origins or "").split(",")]:
        if not candidate:
            continue
        parsed = urlsplit(candidate.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            origins.append(f"{parsed.scheme}://{parsed.netloc}")
    return list(dict.fromkeys(origins))


def sanitize_return_to(return_to: Optional[str]) -> Optional[str]:
    if return_to is None:
        return None

    value = return_to.strip()
    if not value:
        return None

    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        if not value.startswith("/"):
            raise InvalidRedirectTargetError("return_to must be a relative path or an allowed frontend URL.")
        return urlunsplit(("", "", parsed.path or "/", parsed.query, parsed.fragment))

    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    if parsed.scheme not in {"http", "https"} or origin not in _allowed_return_to_origins():
        raise InvalidRedirectTargetError("return_to must target the configured frontend origin.")

    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, parsed.fragment))


def create_connect_url(*, user_id: str, return_to: Optional[str]) -> str:
    ready, reasons = gmail_oauth_ready()
    if not ready:
        raise GmailOAuthConfigurationError(
            f"Gmail OAuth is not configured for this app yet ({', '.join(reasons)})."
        )

    sanitized_return_to = sanitize_return_to(return_to)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    state = db_ops.create_integration_oauth_state(
        user_id=user_id,
        provider=GMAIL_PROVIDER,
        return_to=sanitized_return_to,
        expires_at=expires_at,
    )
    flow = _build_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return authorization_url


def _serialize_google_credentials(creds: Any) -> Dict[str, Any]:
    expiry = getattr(creds, "expiry", None)
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "scopes": list(creds.scopes or GMAIL_SCOPES),
        "expiry": expiry.isoformat() if expiry else None,
    }


def _deserialize_google_credentials(payload: Dict[str, Any]) -> Any:
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=payload.get("token"),
        refresh_token=payload.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=payload.get("scopes") or GMAIL_SCOPES,
    )
    expiry = payload.get("expiry")
    if expiry:
        normalized = expiry.replace("Z", "+00:00")
        creds.expiry = datetime.fromisoformat(normalized)
    return creds


def exchange_callback(*, state: str, code: str) -> Dict[str, Any]:
    state_payload = db_ops.consume_integration_oauth_state(
        state=state,
        provider=GMAIL_PROVIDER,
    )
    if state_payload is None:
        raise InvalidGmailOAuthStateError("Invalid or expired Gmail OAuth state.")

    flow = _build_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials

    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    account_label = profile.get("emailAddress")

    credential_store.save_json(
        user_id=state_payload["user_id"],
        provider=GMAIL_PROVIDER,
        credential_kind=GMAIL_CREDENTIAL_KIND,
        payload=_serialize_google_credentials(creds),
        account_label=account_label,
        scopes=list(creds.scopes or GMAIL_SCOPES),
        expires_at=getattr(creds, "expiry", None),
    )

    return {
        "user_id": state_payload["user_id"],
        "return_to": sanitize_return_to(state_payload.get("return_to")),
        "account_label": account_label,
    }


def load_user_credentials(user_id: str) -> Any:
    payload = credential_store.load_json(
        user_id=user_id,
        provider=GMAIL_PROVIDER,
        credential_kind=GMAIL_CREDENTIAL_KIND,
    )
    if payload is None:
        return None
    return _deserialize_google_credentials(payload)


def save_user_credentials(user_id: str, creds: Any, *, account_label: Optional[str] = None) -> None:
    scopes = list(getattr(creds, "scopes", None) or GMAIL_SCOPES)
    metadata = credential_store.get_status(
        user_id=user_id,
        provider=GMAIL_PROVIDER,
        credential_kind=GMAIL_CREDENTIAL_KIND,
    )
    credential_store.save_json(
        user_id=user_id,
        provider=GMAIL_PROVIDER,
        credential_kind=GMAIL_CREDENTIAL_KIND,
        payload=_serialize_google_credentials(creds),
        account_label=account_label or (metadata or {}).get("account_label"),
        scopes=scopes,
        expires_at=getattr(creds, "expiry", None),
    )


def get_connection_status(user_id: str) -> Dict[str, Any]:
    ready, reasons = gmail_oauth_ready()
    if not ready:
        return {
            "provider": GMAIL_PROVIDER,
            "connected": False,
            "ready": False,
            "reasons": reasons,
            "account_label": None,
        }
    record = credential_store.get_status(
        user_id=user_id,
        provider=GMAIL_PROVIDER,
        credential_kind=GMAIL_CREDENTIAL_KIND,
    )
    if record is None:
        return {
            "provider": GMAIL_PROVIDER,
            "connected": False,
            "ready": True,
            "reasons": ["account_not_connected"],
            "account_label": None,
        }
    status = record.get("status") or "unknown"
    return {
        "provider": GMAIL_PROVIDER,
        "connected": status == "connected",
        "ready": True,
        "reasons": [] if status == "connected" else [f"credential_{status}"],
        "account_label": record.get("account_label"),
        "expires_at": record.get("expires_at"),
        "scopes": record.get("scopes") or [],
    }
