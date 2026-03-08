# API Documentation

## Scope And Status (As Of March 8, 2026)
This document reflects the current split route model:
- Bare runtime endpoints for async run submission, polling, and run streaming.
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
      "type": "tool_result",
      "status": "running",
      "tool": "calculator",
      "message": "Tool action completed",
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

#### GET `/runs/{run_id}/stream`
Streams run progress over Server-Sent Events (SSE) using the same `runs` and `run_events` store as the polling endpoints.

Behavior:
- replays already-persisted events first, in order
- polls the existing event store for new events and emits them as `run_event`
- sends `heartbeat` events roughly every 15 seconds while the run is still active
- sends one final `run_complete` event and closes once the stored run status reaches `succeeded`, `failed`, or `cancelled`

Response headers:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`

SSE event shapes:

`run_event`
```text
event: run_event
data: {"run_id":"run-uuid","event_id":"2","event_type":"tool_result","status":"running","timestamp":"2026-03-08T10:00:02Z","payload":{"message":"Tool action completed","tool":"calculator","metadata":null}}
```

`run_complete`
```text
event: run_complete
data: {"run_id":"run-uuid","conversation_id":"conv-uuid","status":"succeeded","timestamp":"2026-03-08T10:00:03Z","result":"4","error":null}
```

`heartbeat`
```text
event: heartbeat
data: {}
```

Reconnect guidance:
- the stream does not maintain a separate in-memory event buffer
- reconnecting clients should open a fresh SSE connection and rely on backlog replay from the durable run/event store
- polling via `/runs/{run_id}/status` and `/runs/{run_id}/events` remains supported as the fallback contract

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

Lifecycle vocabulary is frozen in code at `backend/runtime/lifecycle.py` and must stay consistent across API, worker, and schema layers.

Run statuses:
- `queued`
- `running`
- `retrying`
- `succeeded`
- `failed`
- `cancelling`
- `cancelled`

Run event types:
- `queued`
- `started`
- `tool_call`
- `tool_result`
- `retrying`
- `failed`
- `succeeded`
- `cancelling`
- `cancelled`

#### Run
API-facing run record. The `run_id` field is the identifier (mapped to the `runs.id` column in the database).
```json
{
  "run_id": "string (unique identifier, maps to runs.id)",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "conversation_id": "string",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime",
  "error": "string|null",
  "result": "string|null"
}
```

#### RunEvent
API-facing run event record. Subset of the full database record; includes essential fields for progress tracking.
```json
{
  "event_id": "string (cursor for pagination, maps to run_events.id)",
  "run_id": "string (foreign key, maps to runs.id)",
  "type": "queued|started|tool_call|tool_result|retrying|failed|succeeded|cancelling|cancelled",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "message": "string",
  "tool": "string|null",
  "error": "string|null (optional, set on error events)",
  "payload": "string|null (optional, for structured event metadata)",
  "created_at": "ISO-8601 datetime"
}
```

#### Lease
```json
{
  "lease_key": "string",
  "owner_id": "string",
  "fencing_token": "number",
  "acquired_at": "ISO-8601 datetime",
  "expires_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime"
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

### Streaming Run Events (SSE)
```javascript
const source = new EventSource(`/runs/${runId}/stream`);

source.addEventListener('run_event', (event) => {
  const payload = JSON.parse(event.data);
  console.log('run event', payload.event_type, payload.payload);
});

source.addEventListener('run_complete', (event) => {
  const payload = JSON.parse(event.data);
  console.log('run finished', payload.status, payload.result, payload.error);
  source.close();
});

source.addEventListener('heartbeat', () => {
  // Optional: update connection liveness metrics.
});

source.onerror = () => {
  source.close();
  // Fall back to the polling contract if SSE is unavailable.
};
```

## Realtime Notes
Implemented now:
- polling via `/runs/{id}/status` and `/runs/{id}/events`
- SSE streaming via `/runs/{id}/stream`

Recommended client behavior:
- prefer SSE for active runs when available
- keep polling as a fallback path and reconnect-safe recovery mechanism
