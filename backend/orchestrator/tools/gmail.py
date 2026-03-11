from __future__ import annotations

from importlib.util import find_spec
import logging
from typing import List, Optional, Tuple, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.integrations.credential_store import (
    MissingCredentialDependencyError,
    MissingCredentialEncryptionKeyError,
)
from backend.integrations.gmail_oauth import (
    GMAIL_SCOPES,
    get_connection_status,
    gmail_tool_ready,
    load_user_credentials,
    save_user_credentials,
)

logger = logging.getLogger(__name__)


def _gmail_dependencies_installed() -> bool:
    required_modules = (
        "google.auth.transport.requests",
        "google.oauth2.credentials",
        "googleapiclient.discovery",
    )
    for module_name in required_modules:
        try:
            if find_spec(module_name) is None:
                return False
        except ModuleNotFoundError:
            return False
    return True


def get_gmail_readiness(enable_gmail_integration: bool, user_id: str = "default") -> Tuple[bool, List[str]]:
    """Determine whether Gmail integration should be exposed to the orchestrator."""
    if not enable_gmail_integration:
        return False, ["feature_flag_disabled"]
    return gmail_tool_ready(user_id)


class GmailReadInput(BaseModel):
    """Structured input contract for Gmail inbox reads."""

    query: Optional[str] = Field(
        default=None,
        description="Optional Gmail search query, such as 'from:alice newer_than:7d' or 'label:unread'. Leave empty for latest inbox messages.",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of matching emails to return.",
    )
    label_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional Gmail label filters such as ['INBOX'] or ['UNREAD']. Defaults to ['INBOX'].",
    )


class GmailReadTool(BaseTool):
    """
    Tool: gmail_read
    Description: Use this tool to search, filter, and read emails from the user's Gmail inbox.
    """

    name: str = "gmail_read"
    description: str = (
        "Reads the user's Gmail inbox and can fetch the latest emails, newest messages, unread mail, "
        "or messages matching a sender/search query. Returns sender, subject, snippet, and date. "
        "Use for queries like 'show my latest emails', 'read my newest message', "
        "'what are my latest emails?', or 'find email from Alice'."
    )
    args_schema: Type[BaseModel] = GmailReadInput

    def __init__(self, user_id: str = "default"):
        super().__init__()
        object.__setattr__(self, "_user_id", user_id)

    def _run(
        self,
        query: Optional[str] = None,
        max_results: int = 5,
        label_ids: Optional[List[str]] = None,
    ) -> str:
        if not _gmail_dependencies_installed():
            return (
                "Gmail integration dependencies are missing. "
                "Please run `pip install -r backend/requirements-gmail.txt` to use this tool."
            )

        try:
            status = get_connection_status(self._user_id)
        except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError) as exc:
            return str(exc)

        if not status.get("ready"):
            reasons = ", ".join(status.get("reasons") or ["unknown"])
            return f"Gmail integration is not configured for this app yet ({reasons})."

        creds = load_user_credentials(self._user_id)
        if creds is None:
            return (
                "Gmail is not connected for this user yet. Visit `/api/v1/gmail/connect` "
                "to authorize access."
            )

        try:
            from google.auth.transport.requests import Request
            from google.auth.exceptions import RefreshError
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as exc:
            return f"Failed to import Gmail dependencies: {exc}. Please check your installation."

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    save_user_credentials(
                        self._user_id,
                        creds,
                        account_label=status.get("account_label"),
                    )
                except RefreshError as exc:
                    return (
                        "Gmail authorization expired and refresh failed. "
                        "Please reconnect your Gmail account. "
                        f"Details: {exc}"
                    )
                except Exception as exc:
                    return f"Unexpected error refreshing Gmail token: {exc}. Please reconnect Gmail."
            else:
                return "Gmail is connected, but the saved credentials are no longer usable. Please reconnect Gmail."

        try:
            service = build("gmail", "v1", credentials=creds)
        except Exception as exc:
            return f"Failed to build Gmail service: {exc}."

        effective_label_ids = label_ids or ["INBOX"]

        try:
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    maxResults=int(max_results),
                    labelIds=effective_label_ids,
                    q=query,
                )
                .execute()
            )
        except HttpError as exc:
            return f"Gmail API error during message search: {exc}."
        except Exception as exc:
            return f"Unexpected error during message search: {exc}."

        messages = results.get("messages", [])
        if not messages:
            return "No emails found matching your search."

        emails = []
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    )
                    .execute()
                )
            except HttpError as exc:
                return f"Gmail API error during message retrieval for {msg_id}: {exc}."
            except Exception as exc:
                return f"Unexpected error during message retrieval for {msg_id}: {exc}."

            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            snippet = msg.get("snippet", "")
            emails.append(
                {
                    "from": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "No Subject"),
                    "date": headers.get("Date", "Unknown"),
                    "snippet": snippet,
                }
            )

        output = []
        for i, email in enumerate(emails, 1):
            output.append(
                f"Email {i}:\nFrom: {email['from']}\nSubject: {email['subject']}\nDate: {email['date']}\nSnippet: {email['snippet']}\n"
            )
        logger.info(
            "Gmail tool executed",
            extra={
                "event": "gmail.tool.executed",
                "user_id": self._user_id,
                "query": query or "",
                "max_results": max_results,
                "label_ids": effective_label_ids,
            },
        )
        return "\n".join(output)

    async def _arun(
        self,
        query: Optional[str] = None,
        max_results: int = 5,
        label_ids: Optional[List[str]] = None,
    ) -> str:
        return self._run(query=query, max_results=max_results, label_ids=label_ids)
