# Gmail Tool

## Overview
The Gmail Tool provides robust integration with Gmail, enabling the agent to search, filter, and read emails directly from the user's inbox. It supports advanced search queries, multi-email retrieval, and returns structured results including sender, subject, date, and snippet.

## Features
- OAuth authentication (secure, user-granted access)
- Full Gmail search syntax support (by sender, subject, date, label, etc.)
- Fetches multiple emails per query (not just the latest)
- Returns sender, subject, date, and snippet for each email
- Supports label-based filtering (e.g., INBOX, UNREAD)
- Handles both simple and advanced user queries

## Usage Examples
- "Show emails from Alice last week"
- "Find unread messages with 'invoice' in the subject"
- "Read my latest email"
- "Search for emails about project X from Bob"

## Technical Implementation
- Tool: `GmailReadTool` (production, read/search)
- File: `backend/orchestrator/tools/gmail.py`
- Uses Google OAuth 2.0 for authentication
- Uses Google API client to fetch and parse emails
- Returns formatted results for agent and user

## Setup Requirements
- Gmail integration is enabled by default. Set `ENABLE_GMAIL_INTEGRATION=false` in your `.env` file if you want to hide it.
- **Dependencies**: Install Gmail-specific dependencies:
  ```bash
  pip install -r backend/requirements-gmail.txt
  ```
- **Google Cloud Project**:
  1. Create a project in Google Cloud Console.
  2. Enable the **Gmail API**.
  3. Configure OAuth consent screen (add your email as a test user).
  4. Create OAuth 2.0 Desktop App credentials.
  5. Download the JSON file and save it as `backend/data/gmail/client_secret.json` (or set `GMAIL_CREDENTIALS_PATH`).
- **First Run**:
  - The first time the tool is used, it will launch a local browser window to authorize access.
  - A token will be saved to `backend/data/gmail/token.pickle` for future use.

## Troubleshooting
- **Dependencies Missing**: If you see an error about missing dependencies, run the pip install command above.
- **Credentials Not Found**: Ensure `client_secret.json` is in the correct path (`backend/data/gmail/`) or `GMAIL_CREDENTIALS_PATH` is set.
- **Auth Errors**: If authentication fails or tokens expire unexpectedly, delete `backend/data/gmail/token.pickle` and try again to trigger a new OAuth flow.

## Limitations
- Only read/search is implemented (no send/compose yet)
- Requires user to complete OAuth flow on first use
- Tool is hidden from the active tool list unless dependencies, credentials, and token/auth readiness checks pass

## References
- See [`README.md`](../../README.md) and [`AGENT.md`](../../AGENT.md) for user and workflow documentation
- See `backend/orchestrator/tools/gmail.py` for implementation details
