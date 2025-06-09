# API Documentation

## Base URL
- **Development**: `http://127.0.0.1:8000/api/v1`
- **Interactive Docs**: `http://127.0.0.1:8000/docs`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

## Authentication
Currently, the MVP uses a default user system. No authentication is required for API calls.

## Core Endpoints

### Chat & Conversations

#### POST `/chat`
Process a chat message through the LangChain agent.

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
  "response": "2 + 2 equals 4.",
  "conversation_id": "generated-or-provided-uuid",
  "agent_actions": [
    {
      "tool": "Calculator",
      "input": "2 + 2",
      "output": "4"
    }
  ],
  "token_usage": 125
}
```

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
- `500` - Internal Server Error

### Specific Error Cases

#### Document Upload Errors
- `400` - Invalid file type (only PDF supported)
- `400` - File too large (max 50MB)
- `500` - Processing failure

#### Conversation Errors
- `404` - Conversation not found
- `400` - Unable to generate title (too few messages)

## Rate Limiting
Currently no rate limiting is implemented. For production deployment, consider implementing rate limiting based on:
- Requests per minute per IP
- Token usage limits
- Document upload limits

## Usage Examples

### Basic Chat Flow
```javascript
// Start a new conversation
const chatResponse = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's the current time?",
    conversation_id: null,
    selected_documents: []
  })
});

const result = await chatResponse.json();
console.log(result.conversation_id); // Use for subsequent messages
```

### Document Q&A Flow
```javascript
// Upload document
const formData = new FormData();
formData.append('file', pdfFile);

const uploadResponse = await fetch('/api/v1/documents/upload', {
  method: 'POST',
  body: formData
});

const uploadResult = await uploadResponse.json();

// Query the document
const queryResponse = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Summarize the uploaded document",
    conversation_id: "existing-conv-id",
    selected_documents: [uploadResult.document_id]
  })
});
```

### Conversation Management
```javascript
// Get all conversations
const conversations = await fetch('/api/v1/conversations').then(r => r.json());

// Get specific conversation messages
const messages = await fetch(`/api/v1/conversations/${convId}/messages`)
  .then(r => r.json());

// Generate title for conversation
const titleResponse = await fetch(`/api/v1/conversations/${convId}/generate-title`, {
  method: 'POST'
});
```

## WebSocket Support
The current implementation uses HTTP polling. For real-time features, consider implementing WebSocket endpoints for:
- Live typing indicators
- Real-time message streaming
- Document processing status updates

---

For interactive API exploration, visit the auto-generated docs at `/docs` when running the server.
