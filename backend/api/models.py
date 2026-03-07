from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (creates new if not provided)")
    selected_documents: Optional[List[str]] = Field(default_factory=list, description="List of selected document IDs for RAG search")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Agent response")
    conversation_id: str = Field(..., description="Conversation ID")
    agent_actions: Optional[List[Dict[str, Any]]] = Field(None, description="Agent reasoning steps")
    token_usage: Optional[int] = Field(None, description="Tokens used")
    cost: Optional[float] = Field(None, description="API cost")
    error: Optional[bool] = Field(False, description="Whether an error occurred")


class RunSubmitResponse(BaseModel):
    """Response model for asynchronous run submission."""
    run_id: str = Field(..., description="Run ID")
    status: str = Field(..., description="Initial run status")
    conversation_id: str = Field(..., description="Conversation ID")


class RunStatusResponse(BaseModel):
    """Response model for asynchronous run status."""
    run_id: str = Field(..., description="Run ID")
    status: str = Field(..., description="Current run status")
    conversation_id: str = Field(..., description="Conversation ID")
    created_at: str = Field(..., description="Run creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    error: Optional[str] = Field(None, description="Failure details if present")
    result: Optional[str] = Field(None, description="Final assistant response if completed")


class RunEventResponse(BaseModel):
    """Single run event model."""
    event_id: str = Field(..., description="Monotonic event cursor ID")
    type: str = Field(..., description="Event type")
    status: str = Field(..., description="Run status at event time")
    message: str = Field(..., description="Human-readable event message")
    created_at: str = Field(..., description="Event creation timestamp")
    tool: Optional[str] = Field(None, description="Associated tool name if applicable")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")


class RunEventsResponse(BaseModel):
    """Paginated run events response."""
    run_id: str = Field(..., description="Run ID")
    events: List[RunEventResponse] = Field(default_factory=list, description="Ordered run events")
    next_after: Optional[str] = Field(None, description="Cursor for the next page")
    has_more: bool = Field(False, description="Whether more events are available")


class ConversationCreate(BaseModel):
    """Request model for creating a new conversation."""
    title: Optional[str] = Field(None, description="Conversation title")


class ConversationResponse(BaseModel):
    """Response model for conversation info."""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    message_count: Optional[int] = Field(None, description="Number of messages")


class MessageResponse(BaseModel):
    """Response model for individual messages."""
    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")
    agent_actions: Optional[List[Dict[str, Any]]] = Field(None, description="Agent actions for this message")
    token_usage: Optional[int] = Field(None, description="Tokens used for this message")


class ToolInfo(BaseModel):
    """Information about available tools."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Health check timestamp")
    version: str = Field("1.0.0", description="API version")


# Document-related models
class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")


class DocumentInfo(BaseModel):
    """Information about a document."""
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    uploaded_at: str = Field(..., description="Upload timestamp")
    processed: str = Field(..., description="Processing status")
    total_chunks: int = Field(..., description="Number of text chunks")
    summary: str = Field(..., description="AI-generated summary of the document")


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    documents: List[DocumentInfo] = Field(..., description="List of documents")
    total_count: int = Field(..., description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response model for document deletion."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Status message")


class TitleGenerationResponse(BaseModel):
    """Response model for conversation title generation."""
    conversation_id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Generated title")
    generated_at: str = Field(..., description="Title generation timestamp")


class ScheduledTaskCreate(BaseModel):
    """Request model for creating a scheduled task."""
    name: str = Field(..., description="Unique human-readable label")
    conversation_id: str = Field(..., description="Target conversation ID")
    message: str = Field(..., description="Prompt injected as user message")
    cron_expr: str = Field(..., description="Standard cron expression, e.g. '0 * * * *' (every hour at minute 0)")


class ScheduledTaskUpdate(BaseModel):
    """Request model for patching a scheduled task."""
    name: Optional[str] = Field(None, description="New label")
    message: Optional[str] = Field(None, description="New prompt")
    cron_expr: Optional[str] = Field(None, description="New cron expression")
    enabled: Optional[bool] = Field(None, description="Enable or pause the task")


class ScheduledTaskResponse(BaseModel):
    """Response model for a scheduled task."""
    id: str = Field(..., description="Task ID")
    name: str = Field(..., description="Task label")
    conversation_id: str = Field(..., description="Target conversation ID")
    message: str = Field(..., description="Prompt message")
    cron_expr: str = Field(..., description="Cron expression")
    enabled: bool = Field(..., description="Whether the task is active")
    next_run_at: str = Field(..., description="Next scheduled fire time (ISO 8601)")
    last_run_at: Optional[str] = Field(None, description="Last fire time")
    last_run_id: Optional[str] = Field(None, description="Run ID from last dispatch")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
