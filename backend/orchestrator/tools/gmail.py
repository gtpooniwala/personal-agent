import os
import pickle
from typing import Optional
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import BaseTool

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
# Use the correct path for credentials and token
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "backend/data/gmail/client_secret_978811794429-sjaaqdpeg0psga3k6afpm4gvl64tqlal.apps.googleusercontent.com.json")
TOKEN_PATH = os.path.join(BASE_DIR, "backend/data/gmail/token.pickle")

class GmailReadTool(BaseTool):
    """
    Tool: gmail_read
    Description: Use this tool to fetch the most recent email from the user's Gmail inbox. Returns sender, subject, snippet, and date. Use for queries like 'show my latest email', 'read my newest message', or 'what is my last received email?'.
    """
    name: str = "gmail_read"
    description: str = (
        "Fetches the most recent email from the user's Gmail inbox. "
        "Returns sender, subject, snippet, and date. "
        "Use for queries like 'show my latest email', 'read my newest message', or 'what is my last received email?'."
    )

    def _run(self, **kwargs):
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
        # Get the latest message
        results = service.users().messages().list(userId="me", maxResults=1, labelIds=["INBOX"]).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No emails found in your inbox."
        msg_id = messages[0]["id"]
        msg = service.users().messages().get(userId="me", id=msg_id, format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        snippet = msg.get("snippet", "")
        return (
            f"From: {headers.get('From', 'Unknown')}\n"
            f"Subject: {headers.get('Subject', 'No Subject')}\n"
            f"Date: {headers.get('Date', 'Unknown')}\n"
            f"Snippet: {snippet}"
        )

    async def _arun(self, **kwargs):
        return self._run(**kwargs)
