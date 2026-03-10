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
    attempt_count: int = Field(..., description="Number of execution attempts")
    created_at: str = Field(..., description="Run creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    started_at: Optional[str] = Field(None, description="Run start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
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


class ExternalTriggerCreate(BaseModel):
    """Request model for registering an external trigger."""

    type: str = Field(..., description="Trigger type: telegram, email, webhook, or generic")
    name: str = Field(..., description="Unique human-readable label")
    conversation_id: str = Field(..., description="Target conversation ID")
    config: Optional[Dict[str, Any]] = Field(None, description="Trigger-specific configuration (JSON)")
    enabled: bool = Field(True, description="Whether the trigger is active")


class ExternalTriggerUpdate(BaseModel):
    """Request model for patching an external trigger."""

    name: Optional[str] = Field(None, description="New label")
    type: Optional[str] = Field(None, description="New trigger type")
    conversation_id: Optional[str] = Field(None, description="New target conversation ID")
    config: Optional[Dict[str, Any]] = Field(None, description="New trigger configuration")
    enabled: Optional[bool] = Field(None, description="Enable or disable the trigger")


class ExternalTriggerResponse(BaseModel):
    """Response model for an external trigger."""

    id: str = Field(..., description="Trigger ID")
    type: str = Field(..., description="Trigger type")
    name: str = Field(..., description="Trigger label")
    conversation_id: str = Field(..., description="Target conversation ID")
    config: Optional[Dict[str, Any]] = Field(None, description="Trigger configuration")
    enabled: bool = Field(..., description="Whether the trigger is active")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class TriggerEventResponse(BaseModel):
    """Response model for a single trigger event audit log entry."""

    id: str = Field(..., description="Event ID")
    trigger_id: str = Field(..., description="Parent trigger ID")
    external_event_id: str = Field(..., description="ID from the external system (dedup key)")
    run_id: Optional[str] = Field(None, description="Run ID created for this event")
    received_at: str = Field(..., description="When the event was received")
    dispatched: bool = Field(..., description="Whether the event was dispatched to a run")


class ObservabilityRunSummary(BaseModel):
    """Compact run summary for observability dashboards."""

    id: str = Field(..., description="Run ID")
    conversation_id: str = Field(..., description="Conversation ID")
    status: str = Field(..., description="Run status")
    attempt_count: int = Field(..., description="Number of execution attempts")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    started_at: Optional[str] = Field(None, description="Run start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    error: Optional[str] = Field(None, description="Failure details if present")


class ObservabilitySummaryResponse(BaseModel):
    """Summary payload for the frontend metrics page."""

    generated_at: str = Field(..., description="Response generation timestamp")
    latest_counter_update: Optional[str] = Field(
        None,
        description="Latest runtime counter update timestamp",
    )
    langfuse_enabled: bool = Field(..., description="Whether Langfuse export is active")
    langfuse_base_url: str = Field(..., description="Configured Langfuse base URL")
    totals: Dict[str, int] = Field(..., description="High-level record counts")
    runtime: Dict[str, Optional[float]] = Field(..., description="Runtime metrics snapshot")
    orchestration: Dict[str, Optional[float]] = Field(..., description="Orchestration metrics snapshot")
    api: Dict[str, Optional[float]] = Field(..., description="API request metrics snapshot")
    tool_usage: Dict[str, int] = Field(default_factory=dict, description="Tool call counts by tool")
    run_status_counts: Dict[str, int] = Field(default_factory=dict, description="Run counts grouped by status")
    recent_runs: List[ObservabilityRunSummary] = Field(
        default_factory=list,
        description="Most recently updated runs",
    )
