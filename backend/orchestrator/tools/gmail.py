import os
import pickle
from importlib.util import find_spec
from typing import List, Tuple

from langchain_core.tools import BaseTool

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))


def _get_credentials_path() -> str:
    return os.environ.get(
        "GMAIL_CREDENTIALS_PATH",
        os.path.join(BASE_DIR, "backend/data/gmail/client_secret.json"),
    )


def _get_token_path() -> str:
    return os.environ.get(
        "GMAIL_TOKEN_PATH", os.path.join(BASE_DIR, "backend/data/gmail/token.pickle")
    )


def _gmail_dependencies_installed() -> bool:
    required_modules = (
        "google.auth.transport.requests",
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


def get_gmail_readiness(enable_gmail_integration: bool) -> Tuple[bool, List[str]]:
    """
    Determine whether Gmail integration should be exposed to the orchestrator.
    """
    if not enable_gmail_integration:
        return False, ["feature_flag_disabled"]

    reasons = []
    if not _gmail_dependencies_installed():
        reasons.append("dependencies_missing")
    if not os.path.exists(_get_credentials_path()):
        reasons.append("credentials_missing")

    return len(reasons) == 0, reasons


class GmailReadTool(BaseTool):
    """
    Tool: gmail_read
    Description: Use this tool to search, filter, and read emails from the user's Gmail inbox.

    Features:
    - OAuth authentication (secure, user-granted access)
    - Full Gmail search syntax support (by sender, subject, date, label, etc.)
    - Fetches multiple emails per query (not just the latest)
    - Returns sender, subject, date, and snippet for each email
    - Supports label-based filtering (e.g., INBOX, UNREAD)
    - Handles both simple and advanced user queries

    Usage:
    - "Show emails from Alice last week"
    - "Find unread messages with 'invoice' in the subject"
    - "Read my latest email"
    - "Search for emails about project X from Bob"
    """

    name: str = "gmail_read"
    description: str = (
        "Fetches the most recent email from the user's Gmail inbox. "
        "Returns sender, subject, snippet, and date. "
        "Use for queries like 'show my latest email', 'read my newest message', or 'what is my last received email?'."
    )

    def _run(self, **kwargs):
        credentials_path = _get_credentials_path()
        token_path = _get_token_path()

        if not _gmail_dependencies_installed():
            return (
                "Gmail integration dependencies are missing. "
                "Please run `pip install -r backend/requirements-gmail.txt` to use this tool."
            )

        if not os.path.exists(credentials_path):
            return (
                "Gmail credentials file not found. "
                "Set GMAIL_CREDENTIALS_PATH or place a client secret file at 'backend/data/gmail/client_secret.json'."
            )

        try:
            from google.auth.transport.requests import Request
            from google.auth.exceptions import RefreshError
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as e:
            return f"Failed to import Gmail dependencies: {str(e)}. Please check your installation."

        creds = None
        # Load token if it exists
        if os.path.exists(token_path):
            try:
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
            except Exception as e:
                return f"Failed to read existing token at '{token_path}': {str(e)}. Please delete it and authenticate again."

        # If no valid creds, do OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    return f"Gmail auth expired and refresh failed: {str(e)}. Please delete '{token_path}' and re-authenticate."
                except Exception as e:
                    return f"Unexpected error refreshing Gmail token: {str(e)}. Please delete '{token_path}' and try again."
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, GMAIL_SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    return f"Failed to run OAuth flow: {str(e)}. Please verify your client_secret.json."

            # Save the credentials for next run
            token_dir = os.path.dirname(token_path)
            if token_dir and not os.path.exists(token_dir):
                try:
                    os.makedirs(token_dir, exist_ok=True)
                except OSError as e:
                    return f"Failed to create directory for Gmail token at '{token_dir}': {str(e)}."
            try:
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            except OSError as e:
                return f"Failed to save Gmail OAuth token to '{token_path}': {str(e)}."

        # Build Gmail API service
        try:
            service = build("gmail", "v1", credentials=creds)
        except Exception as e:
            return f"Failed to build Gmail service: {str(e)}."

        # Support search query, max_results, and label_ids
        query = kwargs.get("query", None)  # Gmail search string
        max_results = int(kwargs.get("max_results", 5))  # Default to 5 emails
        label_ids = kwargs.get("label_ids", ["INBOX"])  # Default to INBOX

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, labelIds=label_ids, q=query)
                .execute()
            )
        except HttpError as e:
            return f"Gmail API error during message search: {str(e)}."
        except Exception as e:
            return f"Unexpected error during message search: {str(e)}."

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
            except HttpError as e:
                return (
                    f"Gmail API error during message retrieval for {msg_id}: {str(e)}."
                )
            except Exception as e:
                return (
                    f"Unexpected error during message retrieval for {msg_id}: {str(e)}."
                )

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
        # Format output for readability
        output = []
        for i, email in enumerate(emails, 1):
            output.append(
                f"Email {i}:\nFrom: {email['from']}\nSubject: {email['subject']}\nDate: {email['date']}\nSnippet: {email['snippet']}\n"
            )
        return "\n".join(output)

    async def _arun(self, **kwargs):
        return self._run(**kwargs)
