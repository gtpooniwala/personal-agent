# API Documentation

## Base URL
- **Development host**: `http://127.0.0.1:8000`
- **Interactive Docs**: `http://127.0.0.1:8000/docs`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`
- **Primary route notation in this doc**: bare paths (`/chat`, `/runs`, ...)
- **Legacy route notation**: `/api/v1/...` (older deployments)
- **Current implementation note**: on current mainline backend, prepend `/api/v1` to endpoint paths.
- **Migration note**: bare-route notation documents the soon-to-land async runtime surface.

## Authentication
Currently, the MVP uses a default user system. No authentication is required for API calls.

## Core Endpoints

### Runtime APIs

Current implementation (today):
- `POST /api/v1/chat` (legacy synchronous behavior).

Target runtime behavior (rolling out soon):
- `POST /chat` and `POST /runs` submit asynchronous work and return a run handle.
- `GET /runs/{run_id}/status` and `GET /runs/{run_id}/events` provide polling visibility.

#### POST `/runs`
Submit work to the orchestrator asynchronously.

**Request Body:**
```json
{
  "message": "What's 2 + 2?",
  "conversation_id": "optional-uuid",
  "selected_documents": ["doc-id-1", "doc-id-2"]
}
```

**Response:**
```json
{
  "run_id": "run-uuid",
  "status": "queued",
  "conversation_id": "generated-or-provided-uuid"
}
```

#### GET `/runs/{run_id}/status`
Get current run lifecycle status.

**Response:**
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
Get ordered run progress messages for polling UIs and logging.

Contract note: cursor/pagination parameters for this endpoint are intentionally left flexible in this phase.
Before finalizing the implementation contract, the AI coding agent must confirm details with the user.

**Response:**
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
      "tool": "Calculator",
      "message": "Tool selected and executing",
      "created_at": "2026-03-06T10:00:02Z"
    }
  ]
}
```

#### POST `/chat`
Asynchronous conversational submission endpoint.

Target behavior: `POST /chat` and `POST /runs` both submit asynchronous work and return a run handle.
Legacy `POST /api/v1/chat` synchronous behavior is deprecated and should be removed after migration completion.

#### GET `/conversations`
Get all conversations for the user.

**Response:**
```json
[
  {
    "id": "conv-uuid",
    "title": "Mathematical Calculations",
    "created_at": "2025-06-08T10:00:00Z",
    "updated_at": "2025-06-08T10:30:00Z",
    "message_count": 4
  }
]
```

#### POST `/conversations`
Create a new conversation.

**Request Body:**
```json
{
  "title": "New Conversation"
}
```

#### GET `/conversations/{conversation_id}/messages`
Get messages for a specific conversation.

**Response:**
```json
[
  {
    "role": "user",
    "content": "Hello!",
    "timestamp": "2025-06-08T10:00:00Z",
    "token_usage": null,
    "agent_actions": null
  },
  {
    "role": "assistant", 
    "content": "Hello! How can I help you today?",
    "timestamp": "2025-06-08T10:00:01Z",
    "token_usage": 45,
    "agent_actions": []
  }
]
```

#### POST `/conversations/{conversation_id}/generate-title`
Manually generate a title for a conversation.

**Response:**
```json
{
  "conversation_id": "conv-uuid",
  "title": "Generated Title",
  "generated_at": "2025-06-08T10:00:00Z"
}
```

### Tools

#### GET `/tools`
Get list of available tools.

**Response:**
```json
[
  {
    "name": "Calculator",
    "description": "Perform mathematical calculations"
  },
  {
    "name": "CurrentTime", 
    "description": "Get current date and time"
  }
]
```

### Documents

#### POST `/documents/upload`
Upload a PDF document for processing.

**Request:**
- Content-Type: `multipart/form-data`
- File field: `file` (PDF, max 50MB)

**Response:**
```json
{
  "document_id": "doc-uuid",
  "filename": "document.pdf",
  "file_size": 1024000,
  "status": "processing",
  "message": "Document uploaded successfully and is being processed"
}
```

#### GET `/documents`
Get list of uploaded documents.

**Response:**
```json
{
  "documents": [
    {
      "id": "doc-uuid",
      "filename": "document.pdf", 
      "file_size": 1024000,
      "uploaded_at": "2025-06-08T10:00:00Z",
      "processed": true,
      "total_chunks": 25
    }
  ],
  "total_count": 1
}
```

#### DELETE `/documents/{document_id}`
Delete a document and its associated data.

**Response:**
```json
{
  "success": true,
  "message": "Document deleted successfully"
}
```

### System

#### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-06-08T10:00:00Z",
  "version": "1.0.0"
}
```

## Data Models

### Run Model
```json
{
  "run_id": "run-uuid",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "conversation_id": "conv-uuid",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime",
  "error": "string|null",
  "result": "string|null"
}
```

### Run Event
```json
{
  "type": "started|tool_call|tool_result|retrying|failed|succeeded|cancelled",
  "status": "queued|running|retrying|succeeded|failed|cancelling|cancelled",
  "message": "string",
  "tool": "optional string",
  "created_at": "ISO-8601 datetime"
}
```

### Message Model
```json
{
  "role": "user|assistant",
  "content": "string",
  "timestamp": "ISO-8601 datetime",
  "token_usage": "number|null",
  "agent_actions": "array|null"
}
```

### Agent Action Model
```json
{
  "tool": "string",
  "input": "string", 
  "output": "string"
}
```

### Conversation Model
```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime", 
  "message_count": "number"
}
```

### Document Model
```json
{
  "id": "uuid",
  "filename": "string",
  "file_size": "number",
  "uploaded_at": "ISO-8601 datetime",
  "processed": "boolean",
  "total_chunks": "number"
}
```

## Error Handling

### Standard Error Response
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes
- `200` - Success
- `400` - Bad Request (validation error, invalid input)
- `404` - Not Found (conversation, document, etc.)
- `409` - Conflict (invalid state transition)
- `500` - Internal Server Error

### Specific Error Cases

#### Document Upload Errors
- `400` - Invalid file type (only PDF supported)
- `400` - File too large (max 50MB)
- `500` - Processing failure

#### Conversation Errors
- `404` - Conversation not found
- `400` - Unable to generate title (too few messages)

#### Run Errors
- `404` - Run not found
- `409` - Invalid state transition (for example, canceling terminal run)
- `422` - Invalid run payload

## Rate Limiting
Currently no rate limiting is implemented. For production deployment, consider implementing rate limiting based on:
- Requests per minute per IP
- Token usage limits
- Document upload limits

## Usage Examples

### Basic Chat Flow
```javascript
// Start a new conversation
const runSubmit = await fetch('/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's the current time?",
    conversation_id: null,
    selected_documents: []
  })
});

const runData = await runSubmit.json();

let status = await (await fetch(`/runs/${runData.run_id}/status`)).json();
while (status.status === 'queued' || status.status === 'running' || status.status === 'retrying') {
  await new Promise(resolve => setTimeout(resolve, 500));
  status = await (await fetch(`/runs/${runData.run_id}/status`)).json();
}

if (status.status === 'succeeded') {
  const events = await (await fetch(`/runs/${runData.run_id}/events`)).json();
  console.log('Run succeeded', status, events);
} else {
  console.error('Run failed', status.error);
}
```

### Document Q&A Flow
```javascript
// Upload document
const formData = new FormData();
formData.append('file', pdfFile);

const uploadResponse = await fetch('/documents/upload', {
  method: 'POST',
  body: formData
});

const uploadResult = await uploadResponse.json();

// Query the document
const queryResponse = await fetch('/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Summarize the uploaded document",
    conversation_id: "existing-conv-id",
    selected_documents: [uploadResult.document_id]
  })
});

const queryRunData = await queryResponse.json();
let queryStatus = await (await fetch(`/runs/${queryRunData.run_id}/status`)).json();
while (queryStatus.status === 'queued' || queryStatus.status === 'running' || queryStatus.status === 'retrying') {
  await new Promise(resolve => setTimeout(resolve, 500));
  queryStatus = await (await fetch(`/runs/${queryRunData.run_id}/status`)).json();
}
```

### Conversation Management
```javascript
// Get all conversations
const conversations = await fetch('/conversations').then(r => r.json());

// Get specific conversation messages
const messages = await fetch(`/conversations/${convId}/messages`)
  .then(r => r.json());

// Generate title for conversation
const titleResponse = await fetch(`/conversations/${convId}/generate-title`, {
  method: 'POST'
});
```

## WebSocket Support
The current implementation uses HTTP polling for run status/events. For future real-time migration, consider SSE/WebSocket endpoints for:
- Streamed run status transitions
- Mid-run cancellation and control events
- Lightweight presence updates

---

For interactive API exploration, visit the auto-generated docs at `/docs` when running the server.
