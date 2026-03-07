# API Documentation

## Scope And Status (As Of March 6, 2026)
This document reflects the current split route model:
- Bare runtime endpoints for async run submission and polling.
- `/api/v1` endpoints for conversations, tools, documents, and health.

## Base URLs
- Development host: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Routing conventions:
- Runtime endpoints: bare routes (`/chat`, `/runs`, ...).
- Non-runtime endpoints: mounted under `/api/v1`.

## Authentication
Implemented now: no auth; single default-user behavior.
All endpoints execute with full privileges for the single default user.

Security constraint: do not bind this API to non-loopback interfaces or expose it behind a reverse proxy without adding authentication/authorization (for example, FastAPI auth dependencies, an authenticating reverse proxy, or VPN-restricted access).

Production/shared deployment requirement: before exposing this service beyond strictly local trusted use on `127.0.0.1`, add authentication/authorization and restrict access appropriately.

## Endpoint Matrix

### Implemented Now (Current Mainline)

#### POST `/chat`
Asynchronous conversational submit endpoint.

#### POST `/runs`
Asynchronous generic submit endpoint.

Request body:
```json
{
  "message": "What's 2 + 2?",
  "conversation_id": "optional-uuid",
  "selected_documents": ["doc-id-1", "doc-id-2"]
}
```

Response body:
```json
{
  "run_id": "run-uuid",
  "status": "queued",
  "conversation_id": "generated-or-provided-uuid"
}
```

#### GET `/runs/{run_id}/status`
Returns lifecycle state for polling clients.

Response body:
```json
{
  "run_id": "run-uuid",
  "status": "running",
  "conversation_id": "conv-uuid",
  "created_at": "2026-03-06T10:00:00Z",
  "updated_at": "2026-03-06T10:00:02Z",
  "error": null,
  "result": null
}
```

#### GET `/runs/{run_id}/events`
Returns ordered progress events for polling UIs.

Response body:
```json
{
  "run_id": "run-uuid",
  "events": [
    {
      "type": "started",
      "status": "running",
      "message": "Run created and queued",
      "created_at": "2026-03-06T10:00:01Z"
    },
    {
      "type": "tool_call",
      "status": "running",
      "tool": "calculator",
      "message": "Tool selected and executing",
      "created_at": "2026-03-06T10:00:02Z"
    }
  ],
  "next_after": "2",
  "has_more": false
}
```

Cursor contract:
- `after`: fetch events strictly after this event cursor.
- `limit`: page size (`1..200`, default `50`).

#### GET `/api/v1/conversations`
Get all conversations.

#### POST `/api/v1/conversations`
Create conversation.

Request body:
```json
{
  "title": "New Conversation"
}
```

#### GET `/api/v1/conversations/{conversation_id}/messages`
Get messages for one conversation.

#### POST `/api/v1/conversations/{conversation_id}/generate-title`
Generate a title for an existing conversation.

#### GET `/api/v1/tools`
List available tools.

#### POST `/api/v1/documents/upload`
Upload PDF (`multipart/form-data`, `file`, max 50MB).

#### GET `/api/v1/documents`
List uploaded documents.

#### DELETE `/api/v1/documents/{document_id}`
Delete a document.

#### GET `/api/v1/health`
Service health endpoint.

Response body:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-06T10:00:00",
  "version": "1.0.0"
}
```

## Data Models

### Implemented Models

#### ChatResponse
```json
{
  "response": "string",
  "conversation_id": "string",
  "agent_actions": "array|null",
  "token_usage": "number|null",
  "cost": "number|null",
  "error": "boolean"
}
```

#### Message
```json
{
  "id": "string",
  "role": "user|assistant",
  "content": "string",
  "timestamp": "ISO-8601 datetime",
  "agent_actions": "array|null",
  "token_usage": "number|null"
}
```

#### Conversation
```json
{
  "id": "string",
  "title": "string",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime",
  "message_count": "number|null"
}
```

#### Document
```json
{
  "id": "string",
  "filename": "string",
  "file_size": "number",
  "uploaded_at": "ISO-8601 datetime",
  "processed": "boolean",
  "total_chunks": "number",
  "summary": "string"
}
```

### Runtime Models

#### Run
```json
{
  "run_id": "string",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "conversation_id": "string",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime",
  "error": "string|null",
  "result": "string|null"
}
```

#### RunEvent
```json
{
  "event_id": "string cursor",
  "type": "started|tool_call|tool_result|retrying|failed|succeeded|cancelled",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "message": "string",
  "tool": "string|null",
  "created_at": "ISO-8601 datetime"
}
```

## Error Handling

Standard error payload:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Common status codes:
- `200` success
- `400` invalid input
- `404` resource missing
- `409` invalid state transition (target run lifecycle)
- `422` invalid payload shape
- `500` internal server error

## Usage Examples

### Implemented Now: Async Run Polling
```javascript
const submit = await fetch('/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Summarize the uploaded document",
    conversation_id: "existing-conv-id",
    selected_documents: []
  })
});

const { run_id } = await submit.json();
let status = await (await fetch(`/runs/${run_id}/status`)).json();
while (['queued', 'running', 'retrying'].includes(status.status)) {
  await new Promise((resolve) => setTimeout(resolve, 500));
  status = await (await fetch(`/runs/${run_id}/status`)).json();
}
```

## Realtime Notes
Implemented now: polling style interactions.
Planned target: SSE/WebSocket can be considered after async run lifecycle is stable.
