from fastapi import APIRouter, HTTPException, UploadFile, File
from agent import PersonalAgent
from api.models import (
    ChatRequest, ChatResponse, ConversationCreate, ConversationResponse,
    MessageResponse, ToolInfo, HealthResponse, DocumentUploadResponse,
    DocumentListResponse, DocumentDeleteResponse, DocumentInfo
)
from services.document_service import doc_processor
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize personal agent
agent = PersonalAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message through the LangChain agent."""
    try:
        conversation_id = request.conversation_id
        
        # Create new conversation if not provided
        if not conversation_id:
            conversation_id = agent.create_conversation()
        
        # Process message with agent
        result = await agent.process_message(request.message, conversation_id)
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations():
    """Get all conversations for the user."""
    try:
        conversations = agent.get_conversations()
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    try:
        conversation_id = agent.create_conversation(request.title or "New Conversation")
        
        # Get the created conversation details
        conversations = agent.get_conversations()
        conversation = next((c for c in conversations if c["id"] == conversation_id), None)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Failed to create conversation")
        
        return ConversationResponse(**conversation)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(conversation_id: str):
    """Get messages for a specific conversation."""
    try:
        messages = agent.get_conversation_history(conversation_id)
        return [MessageResponse(**msg) for msg in messages]
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools():
    """Get list of available tools."""
    try:
        tools = agent.get_available_tools()
        return [ToolInfo(**tool) for tool in tools]
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


# Document management endpoints
@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF document for processing."""
    try:
        # Validate file type
        if not file.content_type == "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Validate file size (max 50MB)
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 50MB")
        
        # Process document
        document_id = await doc_processor.process_pdf_upload(
            file_content=content,
            filename=file.filename,
            user_id="default"  # For MVP, using default user
        )
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            file_size=len(content),
            status="processing",
            message="Document uploaded successfully and is being processed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents():
    """Get list of uploaded documents."""
    try:
        documents = doc_processor.get_documents(user_id="default")
        
        document_infos = [
            DocumentInfo(
                id=doc["id"],
                filename=doc["filename"],
                file_size=doc["file_size"],
                upload_date=doc["upload_date"],
                processed=doc["processed"],
                total_chunks=doc["total_chunks"]
            )
            for doc in documents
        ]
        
        return DocumentListResponse(
            documents=document_infos,
            total_count=len(document_infos)
        )
        
    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    """Delete a document and its associated data."""
    try:
        success = doc_processor.delete_document(document_id, user_id="default")
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentDeleteResponse(
            success=True,
            message="Document deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
