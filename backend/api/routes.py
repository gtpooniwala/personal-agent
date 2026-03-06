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
from backend.observability import observe_operation, update_observation, increment_counter, push_context

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize core orchestrator
orchestrator = CoreOrchestrator()

# Async task functions for conversation maintenance
async def async_generate_title(conversation_id: str):
    """Asynchronously generate title for a conversation."""
    with observe_operation(
        name="maintenance.generate_title",
        counter_prefix="maintenance.generate_title",
        as_type="chain",
        conversation_id=conversation_id,
        metadata={"component": "maintenance"},
    ):
        try:
            logger.info(f"Starting async title generation for conversation: {conversation_id}")
            title = await orchestrator.generate_conversation_title(conversation_id)
            if title:
                logger.info(f"Successfully generated title for {conversation_id}: {title}")
            else:
                logger.warning(f"Title generation returned empty result for {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to generate title for conversation {conversation_id}: {str(e)}")
            raise

async def async_delete_empty_conversation(conversation_id: str):
    """Asynchronously delete an empty old conversation."""
    with observe_operation(
        name="maintenance.delete_empty_conversation",
        counter_prefix="maintenance.delete_empty_conversation",
        as_type="span",
        conversation_id=conversation_id,
        metadata={"component": "maintenance"},
    ):
        try:
            logger.info(f"Starting async deletion of empty conversation: {conversation_id}")
            db_ops.delete_conversation(conversation_id)
            logger.info(f"Successfully deleted empty conversation: {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")
            raise

def check_conversation_maintenance(conversations: List[dict]) -> None:
    """Check conversations for maintenance tasks and trigger them asynchronously."""
    increment_counter("maintenance.scan_total")
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
            increment_counter("maintenance.generate_title.scheduled_total")
            asyncio.create_task(async_generate_title(conversation_id))
        
        # Check for deletion (0 messages, >1 day old)
        elif (message_count == 0 and 
              (now - created_at) > timedelta(days=1)):
            
            logger.info(f"Scheduling deletion of empty conversation {conversation_id} "
                       f"(age: {now - created_at})")
            increment_counter("maintenance.delete_empty_conversation.scheduled_total")
            asyncio.create_task(async_delete_empty_conversation(conversation_id))

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message through the LangChain agent."""
    conversation_id = request.conversation_id
    payload_preview = {
        "message_chars": len(request.message or ""),
        "selected_documents_count": len(request.selected_documents or []),
        "has_conversation_id": bool(conversation_id),
    }
    with observe_operation(
        name="api.chat",
        counter_prefix="api.chat",
        as_type="chain",
        conversation_id=conversation_id,
        input_data=payload_preview,
        metadata={"component": "api", "endpoint": "/api/v1/chat"},
    ) as observation:
        try:
            # Create new conversation if not provided
            if not conversation_id:
                conversation_id = orchestrator.create_conversation()

            with push_context(conversation_id=conversation_id):
                # Process message with orchestrator
                result = await orchestrator.process_request(
                    user_request=request.message,
                    conversation_id=conversation_id,
                    selected_documents=request.selected_documents,
                )

            update_observation(
                observation,
                output={
                    "error": bool(result.get("error", False)),
                    "token_usage": result.get("token_usage"),
                    "tool_actions_count": len(result.get("orchestration_actions") or []),
                },
            )

            # Return orchestrator response
            return ChatResponse(
                response=result["response"],
                conversation_id=result["conversation_id"],
                agent_actions=result.get("orchestration_actions"),
                token_usage=result.get("token_usage"),
                cost=result.get("cost"),
                error=result.get("error", False),
            )

        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations():
    """Get all conversations for the user."""
    with observe_operation(
        name="api.conversations.list",
        counter_prefix="api.conversations.list",
        as_type="span",
        metadata={"component": "api", "endpoint": "/api/v1/conversations"},
    ) as observation:
        try:
            conversations = orchestrator.get_conversations()

            # Trigger passive maintenance tasks (title generation and cleanup)
            logger.info(f"Running conversation maintenance check for {len(conversations)} conversations")
            check_conversation_maintenance(conversations)

            update_observation(observation, output={"conversation_count": len(conversations)})
            return [ConversationResponse(**conv) for conv in conversations]
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    with observe_operation(
        name="api.conversations.create",
        counter_prefix="api.conversations.create",
        as_type="span",
        input_data={"has_title": bool(request.title)},
        metadata={"component": "api", "endpoint": "/api/v1/conversations"},
    ) as observation:
        try:
            conversation_id = orchestrator.create_conversation(request.title or "New Conversation")

            # Get the created conversation details
            conversations = orchestrator.get_conversations()
            conversation = next((c for c in conversations if c["id"] == conversation_id), None)

            if not conversation:
                raise HTTPException(status_code=404, detail="Failed to create conversation")

            update_observation(observation, output={"conversation_id": conversation_id})
            return ConversationResponse(**conversation)

        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(conversation_id: str):
    """Get messages for a specific conversation."""
    with observe_operation(
        name="api.conversations.messages",
        counter_prefix="api.conversations.messages",
        as_type="span",
        conversation_id=conversation_id,
        metadata={"component": "api", "endpoint": "/api/v1/conversations/{conversation_id}/messages"},
    ) as observation:
        try:
            messages = orchestrator.get_conversation_history(conversation_id)
            update_observation(observation, output={"messages_count": len(messages)})
            return [MessageResponse(**msg) for msg in messages]
        except Exception as e:
            logger.error(f"Error getting conversation messages: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools():
    """Get list of available tools."""
    with observe_operation(
        name="api.tools.list",
        counter_prefix="api.tools.list",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/api/v1/tools"},
    ) as observation:
        try:
            tools = orchestrator.get_available_tools()
            update_observation(observation, output={"tools_count": len(tools)})
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
    with observe_operation(
        name="api.documents.upload",
        counter_prefix="api.documents.upload",
        as_type="span",
        input_data={"content_type": file.content_type, "filename": file.filename},
        metadata={"component": "api", "endpoint": "/api/v1/documents/upload"},
    ) as observation:
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
                user_id="default",  # For MVP, using default user
            )

            update_observation(
                observation,
                output={"document_id": document_id, "file_size": len(content)},
            )
            return DocumentUploadResponse(
                document_id=document_id,
                filename=file.filename,
                file_size=len(content),
                status="processing",
                message="Document uploaded successfully and is being processed",
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents():
    """Get list of uploaded documents."""
    with observe_operation(
        name="api.documents.list",
        counter_prefix="api.documents.list",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/api/v1/documents"},
    ) as observation:
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
                    summary=doc["summary"],
                )
                for doc in documents
            ]

            update_observation(observation, output={"documents_count": len(document_infos)})
            return DocumentListResponse(
                documents=document_infos,
                total_count=len(document_infos),
            )

        except Exception as e:
            logger.error(f"Error getting documents: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    """Delete a document and its associated data."""
    with observe_operation(
        name="api.documents.delete",
        counter_prefix="api.documents.delete",
        as_type="tool",
        input_data={"document_id": document_id},
        metadata={"component": "api", "endpoint": "/api/v1/documents/{document_id}"},
    ) as observation:
        try:
            success = doc_processor.delete_document(document_id, user_id="default")

            if not success:
                raise HTTPException(status_code=404, detail="Document not found")

            update_observation(observation, output={"deleted": True})
            return DocumentDeleteResponse(
                success=True,
                message="Document deleted successfully",
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/generate-title", response_model=TitleGenerationResponse)
async def generate_conversation_title(conversation_id: str):
    """Generate a title for a conversation using LLM."""
    with observe_operation(
        name="api.conversations.generate_title",
        counter_prefix="api.conversations.generate_title",
        as_type="generation",
        conversation_id=conversation_id,
        input_data={"conversation_id": conversation_id},
        metadata={"component": "api", "endpoint": "/api/v1/conversations/{conversation_id}/generate-title"},
    ) as observation:
        try:
            title = await orchestrator.generate_conversation_title(conversation_id)

            if not title:
                raise HTTPException(status_code=400, detail="Unable to generate title - conversation may be too short or have no messages")

            update_observation(observation, output={"title": title})
            return TitleGenerationResponse(
                conversation_id=conversation_id,
                title=title,
                generated_at=datetime.now().isoformat(),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating conversation title: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
