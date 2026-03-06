# API Documentation

## Scope And Status (As Of March 6, 2026)
This document intentionally separates:
- `Implemented now` behavior available on `main`.
- `Planned target` behavior for the async runtime migration.

Do not treat planned endpoints as currently available unless issues [#15](https://github.com/gtpooniwala/personal-agent/issues/15) and [#17](https://github.com/gtpooniwala/personal-agent/issues/17) are merged.

## Base URLs
- Development host: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Routing conventions:
- Implemented now: all API routes are mounted under `/api/v1`.
- Planned target: runtime endpoints also exposed as bare routes (`/chat`, `/runs`, ...).

## Authentication
Implemented now: no auth; single default-user behavior.
All endpoints execute with full privileges for the single default user.

Security constraint: do not bind this API to non-loopback interfaces or expose it behind a reverse proxy without adding authentication/authorization (for example, FastAPI auth dependencies, an authenticating reverse proxy, or VPN-restricted access).

Production/shared deployment requirement: before exposing this service beyond strictly local trusted use on `127.0.0.1`, add authentication/authorization and restrict access appropriately.

## Endpoint Matrix

### Implemented Now (Current Mainline)

#### POST `/api/v1/chat`
Current behavior: synchronous chat request/response.

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
  "response": "2 + 2 = 4",
  "conversation_id": "conv-uuid",
  "agent_actions": [
    {
      "tool": "calculator",
      "input": "2+2",
      "output": "4"
    }
  ],
  "token_usage": 123,
  "cost": 0.00012,
  "error": false
}
```

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

### Planned Target (Not Yet Implemented On Main)

These endpoints document migration intent and are not guaranteed to exist yet:

#### POST `/chat`
Target behavior: asynchronous submit endpoint returning `run_id`.

#### POST `/runs`
Target behavior: asynchronous submit endpoint returning `run_id`.

Planned request body:
```json
{
  "message": "What's 2 + 2?",
  "conversation_id": "optional-uuid",
  "selected_documents": ["doc-id-1", "doc-id-2"]
}
```

Planned response body:
```json
{
  "run_id": "run-uuid",
  "status": "queued",
  "conversation_id": "generated-or-provided-uuid"
}
```

#### GET `/runs/{run_id}/status`
Target behavior: return lifecycle state for polling clients.

Planned response body:
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
Target behavior: ordered progress events for polling UIs.

Planned response body:
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
  ]
}
```

Contract note: pagination/cursor shape for events remains intentionally flexible until `#17` is finalized.

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

### Planned Runtime Models (Migration Target)

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

### Implemented Now: Synchronous Chat
```javascript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's the current time?",
    conversation_id: null,
    selected_documents: []
  })
});

const data = await response.json();
console.log(data.response, data.conversation_id);
```

### Planned Target: Async Run Polling
```javascript
const submit = await fetch('/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Summarize the uploaded document',
    conversation_id: 'existing-conv-id',
    selected_documents: ['doc-id']
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
