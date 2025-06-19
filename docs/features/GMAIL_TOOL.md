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
- Google Cloud project with Gmail API enabled
- OAuth client credentials JSON in `backend/data/gmail/`
- Token file generated on first use (user login)

## Limitations
- Only read/search is implemented (no send/compose yet)
- Requires user to complete OAuth flow on first use
- Only works if credentials and token are present

## References
- See `README.md` and `AGENT.md` for user and technical documentation
- See `backend/orchestrator/tools/gmail.py` for implementation details
