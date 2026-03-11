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
  1. Sign in with the Google account that should own the app integration, typically your work account.
  2. Create or select the app's Google Cloud project.
  3. Enable the **Gmail API** once for that project.
  4. Configure the OAuth consent screen for an External app.
  5. If the app is still private, keep the consent screen in Testing and add each allowed Gmail user as a test user.
  6. Create OAuth 2.0 **Web application** credentials.
  7. Add your backend callback URI:
     - local Python: `http://localhost:8000/api/v1/gmail/callback`
     - local Docker: `http://localhost:8001/api/v1/gmail/callback`
     - production: `https://<your-backend-host>/api/v1/gmail/callback`
  8. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in the app environment.
  9. Set `CREDENTIALS_MASTER_KEY` so the app can store per-user Gmail tokens encrypted in Postgres.
  10. Restart the backend after updating secrets.
- **Credential Model**:
  - App-level OAuth client secrets stay in env or a secret manager.
  - Per-user Gmail access tokens and refresh tokens are stored encrypted in Postgres.
  - Users do not need their own Google Cloud project or to enable Gmail API themselves.
- **User Connect Flow**:
  - The user visits `/api/v1/gmail/connect`.
  - Google redirects back to `/api/v1/gmail/callback`.
  - The app stores the user's Gmail token encrypted in Postgres.

## Troubleshooting
- **Dependencies Missing**: If you see an error about missing dependencies, run the pip install command above.
- **App OAuth Config Missing**: Ensure `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` are set.
- **Encrypted Store Not Configured**: Ensure `CREDENTIALS_MASTER_KEY` is set and valid.
- **Auth Errors**: If authentication fails or tokens expire unexpectedly, disconnect Gmail and reconnect through `/api/v1/gmail/connect`.

## Limitations
- Only read/search is implemented (no send/compose yet)
- Requires the user to complete the web OAuth flow once
- Tool is hidden from the active tool list unless dependencies, app OAuth config, encrypted storage, and a user connection are all available

## References
- See [`README.md`](../../README.md) and [`AGENTS.md`](../../AGENTS.md) for user and workflow documentation
- See `backend/orchestrator/tools/gmail.py` for implementation details
