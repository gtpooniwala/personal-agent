from fastapi import APIRouter, HTTPException, UploadFile, File
from backend.orchestrator import CoreOrchestrator
from backend.api.models import (
    ChatRequest, ChatResponse, ConversationCreate, ConversationResponse,
    MessageResponse, ToolInfo, HealthResponse, DocumentUploadResponse,
    DocumentListResponse, DocumentDeleteResponse, DocumentInfo,
    TitleGenerationResponse  # Add new model import
)
from backend.services.document_service import doc_processor
from typing import List
from datetime import datetime, timedelta
import asyncio
import logging
from backend.database.operations import db_ops

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize core orchestrator
orchestrator = CoreOrchestrator()

# Async task functions for conversation maintenance
async def async_generate_title(conversation_id: str):
    """Asynchronously generate title for a conversation."""
    try:
        logger.info(f"Starting async title generation for conversation: {conversation_id}")
        title = await orchestrator.generate_conversation_title(conversation_id)
        if title:
            logger.info(f"Successfully generated title for {conversation_id}: {title}")
        else:
            logger.warning(f"Title generation returned empty result for {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to generate title for conversation {conversation_id}: {str(e)}")

async def async_delete_empty_conversation(conversation_id: str):
    """Asynchronously delete an empty old conversation."""
    try:
        logger.info(f"Starting async deletion of empty conversation: {conversation_id}")
        db_ops.delete_conversation(conversation_id)
        logger.info(f"Successfully deleted empty conversation: {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")

def check_conversation_maintenance(conversations: List[dict]) -> None:
    """Check conversations for maintenance tasks and trigger them asynchronously."""
    now = datetime.now()
    
    for conv in conversations:
        conversation_id = conv["id"]
        title = conv["title"]
        message_count = conv["message_count"]
        updated_at = datetime.fromisoformat(conv["updated_at"].replace("Z", "+00:00"))
        created_at = datetime.fromisoformat(conv["created_at"].replace("Z", "+00:00"))
        
        # Make times timezone-naive for comparison (assuming UTC)
        if updated_at.tzinfo:
            updated_at = updated_at.replace(tzinfo=None)
        if created_at.tzinfo:
            created_at = created_at.replace(tzinfo=None)
        
        # Check for title generation (≥1 message, >5 minutes old, "New Conversation" title)
        if (message_count >= 1 and 
            title == "New Conversation" and 
            (now - updated_at) > timedelta(minutes=5)):
            
            logger.info(f"Scheduling title generation for conversation {conversation_id} "
                       f"(messages: {message_count}, age: {now - updated_at})")
            asyncio.create_task(async_generate_title(conversation_id))
        
        # Check for deletion (0 messages, >1 day old)
        elif (message_count == 0 and 
              (now - created_at) > timedelta(days=1)):
            
            logger.info(f"Scheduling deletion of empty conversation {conversation_id} "
                       f"(age: {now - created_at})")
            asyncio.create_task(async_delete_empty_conversation(conversation_id))

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message through the LangChain agent."""
    try:
        conversation_id = request.conversation_id
        
        # Create new conversation if not provided
        if not conversation_id:
            conversation_id = orchestrator.create_conversation()
        
        # Process message with orchestrator
        result = await orchestrator.process_request(
            user_request=request.message, 
            conversation_id=conversation_id,
            selected_documents=request.selected_documents
        )
        
        # Return orchestrator response
        return ChatResponse(
            response=result["response"],
            conversation_id=result["conversation_id"],
            agent_actions=result.get("orchestration_actions"),
            token_usage=result.get("token_usage"),
            cost=result.get("cost"),
            error=result.get("error", False)
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations():
    """Get all conversations for the user."""
    try:
        conversations = orchestrator.get_conversations()
        
        # Trigger passive maintenance tasks (title generation and cleanup)
        logger.info(f"Running conversation maintenance check for {len(conversations)} conversations")
        check_conversation_maintenance(conversations)
        
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    try:
        conversation_id = orchestrator.create_conversation(request.title or "New Conversation")
        
        # Get the created conversation details
        conversations = orchestrator.get_conversations()
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
        messages = orchestrator.get_conversation_history(conversation_id)
        return [MessageResponse(**msg) for msg in messages]
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools():
    """Get list of available tools."""
    try:
        tools = orchestrator.get_available_tools()
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
                uploaded_at=doc["upload_date"],
                processed=doc["processed"],
                total_chunks=doc["total_chunks"],
                summary=doc["summary"]
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


@router.post("/conversations/{conversation_id}/generate-title", response_model=TitleGenerationResponse)
async def generate_conversation_title(conversation_id: str):
    """Generate a title for a conversation using LLM."""
    try:
        title = await orchestrator.generate_conversation_title(conversation_id)
        
        if not title:
            raise HTTPException(status_code=400, detail="Unable to generate title - conversation may be too short or have no messages")
        
        return TitleGenerationResponse(
            conversation_id=conversation_id,
            title=title,
            generated_at=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating conversation title: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
