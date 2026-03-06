import os
import pickle
from langchain_core.tools import BaseTool

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
CREDENTIALS_PATH = os.environ.get(
    "GMAIL_CREDENTIALS_PATH",
    os.path.join(BASE_DIR, "backend/data/gmail/client_secret.json")
)
TOKEN_PATH = os.environ.get(
    "GMAIL_TOKEN_PATH",
    os.path.join(BASE_DIR, "backend/data/gmail/token.pickle")
)

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
        try:
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            return (
                "Gmail integration dependencies are not installed. "
                "Install `google-auth`, `google-auth-oauthlib`, and `google-api-python-client` to use this tool."
            )

        if not os.path.exists(CREDENTIALS_PATH):
            return (
                "Gmail credentials file not found. "
                "Set GMAIL_CREDENTIALS_PATH or place a client secret file at backend/data/gmail/client_secret.json."
            )

        creds = None
        # Load token if it exists
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)
        # If no valid creds, do OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for next run
            with open(TOKEN_PATH, "wb") as token:
                pickle.dump(creds, token)
        # Build Gmail API service
        service = build("gmail", "v1", credentials=creds)

        # Support search query, max_results, and label_ids
        query = kwargs.get("query", None)  # Gmail search string
        max_results = int(kwargs.get("max_results", 5))  # Default to 5 emails
        label_ids = kwargs.get("label_ids", ["INBOX"])  # Default to INBOX

        results = service.users().messages().list(
            userId="me",
            maxResults=max_results,
            labelIds=label_ids,
            q=query
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No emails found matching your search."
        emails = []
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            msg = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            snippet = msg.get("snippet", "")
            emails.append({
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "No Subject"),
                "date": headers.get("Date", "Unknown"),
                "snippet": snippet
            })
        # Format output for readability
        output = []
        for i, email in enumerate(emails, 1):
            output.append(
                f"Email {i}:\nFrom: {email['from']}\nSubject: {email['subject']}\nDate: {email['date']}\nSnippet: {email['snippet']}\n"
            )
        return "\n".join(output)

    async def _arun(self, **kwargs):
        return self._run(**kwargs)
