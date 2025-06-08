from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


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


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    documents: List[DocumentInfo] = Field(..., description="List of documents")
    total_count: int = Field(..., description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response model for document deletion."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Status message")
