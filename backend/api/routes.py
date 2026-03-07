from fastapi import APIRouter, HTTPException, UploadFile, File
from backend.api.models import (
    ConversationCreate, ConversationResponse,
    MessageResponse, ToolInfo, HealthResponse, DocumentUploadResponse,
    DocumentListResponse, DocumentDeleteResponse, DocumentInfo,
    ObservabilitySummaryResponse,
    TitleGenerationResponse
)
from backend.services.document_service import doc_processor
from backend.config import settings, agent_config
from typing import List
from datetime import datetime, timedelta
import asyncio
import logging
from backend.api.state import orchestrator
from backend.database.operations import db_ops
from backend.observability import observe_operation, update_observation, increment_counter

logger = logging.getLogger(__name__)

router = APIRouter()

_NAMING_CFG = agent_config.get("conversation_naming", {})
_NAMING_DELAY_MINUTES: int = _NAMING_CFG.get("delay_minutes", 5)
_NAMING_RETRY_DELAY_MINUTES: int = _NAMING_CFG.get("retry_delay_minutes", 2)
_NAMING_MAX_RETRIES: int = _NAMING_CFG.get("max_retries", 3)

# Patterns that identify a conversation with an auto-generated (non-user) title.
# Must stay in sync with DatabaseOperations.is_conversation_untitled.
_UNTITLED_PREFIXES = ("Conversation ", "New Conversation", "Chat ")


def _average(total: int, count: int) -> float | None:
    if count <= 0:
        return None
    return round(total / count, 1)


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 1)

# Async task functions for conversation maintenance
async def async_generate_title(conversation_id: str):
    """Asynchronously generate a title with automatic retry on empty result or failure."""
    with observe_operation(
        name="maintenance.generate_title",
        counter_prefix="maintenance.generate_title",
        as_type="chain",
        conversation_id=conversation_id,
        metadata={"component": "maintenance"},
    ):
        for attempt in range(1, _NAMING_MAX_RETRIES + 1):
            try:
                logger.info(
                    f"Title generation attempt {attempt}/{_NAMING_MAX_RETRIES} "
                    f"for conversation {conversation_id}"
                )
                title = await orchestrator.generate_conversation_title(conversation_id)
                if title:
                    logger.info(f"Generated title for {conversation_id}: {title}")
                    return
                logger.warning(
                    f"Attempt {attempt}: title generation returned empty for {conversation_id}"
                )
            except Exception as e:
                logger.error(
                    f"Attempt {attempt}: title generation failed for {conversation_id}: {e}"
                )

            if attempt < _NAMING_MAX_RETRIES:
                still_untitled = await asyncio.to_thread(
                    db_ops.is_conversation_untitled, conversation_id
                )
                if not still_untitled:
                    return
                logger.info(
                    f"Retrying title generation in {_NAMING_RETRY_DELAY_MINUTES}m "
                    f"(next attempt {attempt + 1}/{_NAMING_MAX_RETRIES})"
                )
                await asyncio.sleep(_NAMING_RETRY_DELAY_MINUTES * 60)

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
        
        # Check for title generation (≥1 message, inactive ≥ delay, untitled)
        if (message_count >= 1 and
            any(title.startswith(p) for p in _UNTITLED_PREFIXES) and
            (now - updated_at) > timedelta(minutes=_NAMING_DELAY_MINUTES)):
            
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
            raise HTTPException(status_code=500, detail="Failed to retrieve conversations")


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

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create conversation")


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
            raise HTTPException(status_code=500, detail="Failed to retrieve conversation messages")


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
            raise HTTPException(status_code=500, detail="Failed to retrieve available tools")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
async def get_observability_summary():
    """Return a compact metrics snapshot for the frontend observability page."""
    with observe_operation(
        name="api.observability.summary",
        counter_prefix="api.observability.summary",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/api/v1/observability/summary"},
    ) as observation:
        try:
            counters = db_ops.get_runtime_counters()
            database_summary = db_ops.get_observability_summary()

            tool_usage = {
                key.removeprefix("orchestrator.tool_calls.").removesuffix(".total"): value
                for key, value in counters.items()
                if key.startswith("orchestrator.tool_calls.") and key.endswith(".total")
            }

            runtime_submit_requests = counters.get("runtime.submit_run.requests_total", 0)
            runtime_execute_requests = counters.get("runtime.execute_run.requests_total", 0)
            runtime_runs_succeeded = counters.get("runtime.runs.succeeded_total", 0)
            runtime_runs_failed = counters.get("runtime.runs.failed_total", 0)
            runtime_runs_queued = counters.get("runtime.runs.queued_total", 0)

            api_chat_submit_requests = counters.get("api.runtime.chat_submit.requests_total", 0)
            api_documents_upload_requests = counters.get("api.documents.upload.requests_total", 0)
            api_conversation_list_requests = counters.get("api.conversations.list.requests_total", 0)

            response_payload = {
                "generated_at": datetime.now().isoformat(),
                "latest_counter_update": database_summary["latest_counter_update"],
                "langfuse_enabled": bool(settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key),
                "langfuse_base_url": settings.langfuse_base_url,
                "totals": database_summary["totals"],
                "runtime": {
                    "submit_requests_total": runtime_submit_requests,
                    "execute_requests_total": runtime_execute_requests,
                    "queued_total": runtime_runs_queued,
                    "succeeded_total": runtime_runs_succeeded,
                    "failed_total": runtime_runs_failed,
                    "success_rate_pct": _percentage(
                        runtime_runs_succeeded,
                        runtime_runs_succeeded + runtime_runs_failed,
                    ),
                    "average_execution_latency_ms": _average(
                        counters.get("runtime.execute_run.latency_ms_total", 0),
                        counters.get("runtime.execute_run.success_total", 0),
                    ),
                    "average_completed_run_latency_ms": database_summary["average_run_latency_ms"],
                },
                "orchestration": {
                    "tool_calls_total": counters.get("orchestrator.tool_calls_total", 0),
                    "token_usage_total": counters.get("orchestrator.token_usage_total", 0),
                    "fallback_total": counters.get("orchestrator.fallback_total", 0),
                    "average_request_latency_ms": _average(
                        counters.get("orchestrator.process_request.latency_ms_total", 0),
                        counters.get("orchestrator.process_request.success_total", 0),
                    ),
                    "average_langgraph_latency_ms": _average(
                        counters.get("orchestrator.langgraph.invoke.latency_ms_total", 0),
                        counters.get("orchestrator.langgraph.invoke.success_total", 0),
                    ),
                },
                "api": {
                    "chat_submit_requests_total": api_chat_submit_requests,
                    "documents_upload_requests_total": api_documents_upload_requests,
                    "conversations_list_requests_total": api_conversation_list_requests,
                    "average_chat_submit_latency_ms": _average(
                        counters.get("api.runtime.chat_submit.latency_ms_total", 0),
                        counters.get("api.runtime.chat_submit.success_total", 0),
                    ),
                    "average_documents_upload_latency_ms": _average(
                        counters.get("api.documents.upload.latency_ms_total", 0),
                        counters.get("api.documents.upload.success_total", 0),
                    ),
                },
                "tool_usage": dict(sorted(tool_usage.items(), key=lambda item: item[1], reverse=True)),
                "run_status_counts": database_summary["run_status_counts"],
                "recent_runs": database_summary["recent_runs"],
            }

            update_observation(
                observation,
                output={
                    "run_count": response_payload["totals"]["runs"],
                    "tool_count": len(response_payload["tool_usage"]),
                },
            )
            return ObservabilitySummaryResponse(**response_payload)
        except Exception as e:
            logger.error(f"Error getting observability summary: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve observability summary")


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
            raise HTTPException(status_code=500, detail="Failed to upload document")


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
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")


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
            raise HTTPException(status_code=500, detail="Failed to delete document")


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
            raise HTTPException(status_code=500, detail="Failed to generate conversation title")
