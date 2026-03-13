from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import RedirectResponse
from backend.api.models import (
    ConversationCreate, ConversationResponse,
    MessageResponse, ToolInfo, ToolInfoWithStatus, HealthResponse, DocumentUploadResponse,
    DocumentListResponse, DocumentDeleteResponse, DocumentInfo,
    ObservabilitySummaryResponse,
    TitleGenerationResponse,
    GmailConnectionStatusResponse,
)
from backend.services.document_service import doc_processor
from backend.config import settings
from typing import List
from datetime import datetime
import logging
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from backend.api.state import orchestrator
from backend.database.operations import db_ops
from backend.observability import observe_operation, update_observation
from backend.runtime.blocking import (
    BlockingCall,
    offload_blocking_call,
    offload_blocking_calls,
)
from backend.integrations.credential_store import (
    MissingCredentialDependencyError,
    MissingCredentialEncryptionKeyError,
    credential_store,
)
from backend.integrations.gmail_oauth import (
    GMAIL_CREDENTIAL_KIND,
    GMAIL_PROVIDER,
    GmailOAuthConfigurationError,
    InvalidGmailOAuthStateError,
    InvalidRedirectTargetError,
    create_connect_url,
    exchange_callback,
    get_connection_status,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _current_user_id() -> str:
    # The broader auth/user model still defaults to a single local user. The
    # credential store is keyed by user_id so a future auth layer can plug into
    # this without changing provider storage contracts.
    return "default"


def _average(total: int, count: int) -> float | None:
    if count <= 0:
        return None
    return round(total / count, 1)


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _resolve_frontend_redirect_target(return_to: str | None) -> str:
    target = (return_to or "").strip()
    frontend_url = (settings.frontend_url or "").strip()

    if not target:
        return frontend_url or "/"

    parsed = urlsplit(target)
    if parsed.scheme and parsed.netloc:
        return target

    if target.startswith("/") and frontend_url:
        return urljoin(f"{frontend_url.rstrip('/')}/", target.lstrip("/"))

    return target


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append((key, value))
    path = parsed.path or "/"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, urlencode(query), parsed.fragment)
    )

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations():
    """Get all conversations for the user without triggering maintenance work."""
    with observe_operation(
        name="api.conversations.list",
        counter_prefix="api.conversations.list",
        as_type="span",
        metadata={"component": "api", "endpoint": "/api/v1/conversations"},
    ) as observation:
        try:
            conversations = await offload_blocking_call(orchestrator.get_conversations)
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
            conversation_id = await offload_blocking_call(
                orchestrator.create_conversation,
                request.title or "New Conversation",
            )

            # Get the created conversation details
            conversations = await offload_blocking_call(orchestrator.get_conversations)
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
            messages = await offload_blocking_call(
                orchestrator.get_conversation_history,
                conversation_id,
            )
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
            tools = await offload_blocking_call(orchestrator.get_available_tools)
            update_observation(observation, output={"tools_count": len(tools)})
            return [ToolInfo(**tool) for tool in tools]
        except Exception as e:
            logger.error(f"Error getting tools: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve available tools")


@router.get("/tools/info", response_model=List[ToolInfoWithStatus])
async def get_all_tools_info():
    """Get all tools with active/inactive status.

    Note: active status is evaluated against the shared orchestrator's user_id
    (single-user deployment). Consistent with the existing GET /tools endpoint.
    """
    with observe_operation(
        name="api.tools.info",
        counter_prefix="api.tools.info",
        as_type="span",
        metadata={"component": "api", "endpoint": "/api/v1/tools/info"},
    ) as observation:
        try:
            tools = await offload_blocking_call(orchestrator.tool_registry.get_tool_info)
            update_observation(observation, output={"tool_count": len(tools)})
            return tools
        except Exception as e:
            logger.error(f"Error getting tools info: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve tools info")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@router.get("/gmail/status", response_model=GmailConnectionStatusResponse)
async def gmail_connection_status():
    """Return the current Gmail integration status for the active user."""
    user_id = _current_user_id()
    with observe_operation(
        name="api.gmail.status",
        counter_prefix="api.gmail.status",
        as_type="retriever",
        metadata={"component": "api", "endpoint": "/api/v1/gmail/status"},
    ) as observation:
        try:
            status = get_connection_status(user_id)
            orchestrator.tool_registry.refresh_runtime_capabilities(force=True)
            update_observation(
                observation,
                output={"connected": status.get("connected", False)},
            )
            return GmailConnectionStatusResponse(**status)
        except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Error getting Gmail status: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve Gmail status") from exc


@router.get("/gmail/connect")
async def gmail_connect(return_to: str | None = Query(default=None)):
    """Start the Gmail OAuth web flow for the active user."""
    user_id = _current_user_id()
    with observe_operation(
        name="api.gmail.connect",
        counter_prefix="api.gmail.connect",
        as_type="span",
        input_data={"has_return_to": bool(return_to)},
        metadata={"component": "api", "endpoint": "/api/v1/gmail/connect"},
    ) as observation:
        try:
            authorization_url = create_connect_url(user_id=user_id, return_to=return_to)
            update_observation(observation, output={"redirect": True})
            return RedirectResponse(url=authorization_url, status_code=307)
        except (
            MissingCredentialDependencyError,
            MissingCredentialEncryptionKeyError,
            GmailOAuthConfigurationError,
            InvalidRedirectTargetError,
        ) as exc:
            status = 400 if isinstance(exc, InvalidRedirectTargetError) else 503
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Error starting Gmail connect flow: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to start Gmail connect flow") from exc


@router.get("/gmail/callback")
async def gmail_callback(
    state: str,
    code: str | None = None,
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """Handle the Google OAuth callback for Gmail."""
    with observe_operation(
        name="api.gmail.callback",
        counter_prefix="api.gmail.callback",
        as_type="span",
        metadata={"component": "api", "endpoint": "/api/v1/gmail/callback"},
    ) as observation:
        try:
            if error:
                description = f": {error_description}" if error_description else ""
                raise HTTPException(
                    status_code=400,
                    detail=f"Gmail OAuth failed with error `{error}`{description}",
                )
            if not code:
                raise HTTPException(status_code=400, detail="Missing Gmail OAuth authorization code.")
            result = exchange_callback(state=state, code=code)
            orchestrator.tool_registry.refresh_runtime_capabilities(force=True)
            update_observation(
                observation,
                output={"connected": True, "account_label": result.get("account_label")},
            )
            base_redirect = _resolve_frontend_redirect_target(result.get("return_to"))
            return RedirectResponse(
                url=_append_query_param(base_redirect, "gmail", "connected"),
                status_code=307,
            )
        except HTTPException:
            raise
        except (InvalidGmailOAuthStateError, InvalidRedirectTargetError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Error completing Gmail callback: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to complete Gmail OAuth callback") from exc


@router.delete("/gmail/connection", response_model=GmailConnectionStatusResponse)
async def gmail_disconnect():
    """Delete the saved Gmail connection for the active user."""
    user_id = _current_user_id()
    with observe_operation(
        name="api.gmail.disconnect",
        counter_prefix="api.gmail.disconnect",
        as_type="span",
        metadata={"component": "api", "endpoint": "/api/v1/gmail/connection"},
    ) as observation:
        try:
            credential_store.delete(
                user_id=user_id,
                provider=GMAIL_PROVIDER,
                credential_kind=GMAIL_CREDENTIAL_KIND,
            )
            orchestrator.tool_registry.refresh_runtime_capabilities(force=True)
            status = get_connection_status(user_id)
            update_observation(observation, output={"connected": False})
            return GmailConnectionStatusResponse(**status)
        except (MissingCredentialDependencyError, MissingCredentialEncryptionKeyError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Error disconnecting Gmail: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to disconnect Gmail") from exc


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
            counters, database_summary = await offload_blocking_calls(
                BlockingCall(db_ops.get_runtime_counters),
                BlockingCall(db_ops.get_observability_summary),
            )

            tool_usage = {
                key.removeprefix("orchestrator.tool_calls.").removesuffix(".total"): value
                for key, value in counters.items()
                if key.startswith("orchestrator.tool_calls.")
                and key.endswith(".total")
                and not key.endswith(".latency_ms_total")
            }
            tool_latency_ms = {}
            for key, value in counters.items():
                if not key.startswith("orchestrator.tool_calls."):
                    continue
                if not key.endswith(".latency_ms_total"):
                    continue
                if key == "orchestrator.tool_calls.latency_ms_total":
                    continue
                tool_name = key.removeprefix("orchestrator.tool_calls.").removesuffix(
                    ".latency_ms_total"
                )
                tool_latency_ms[tool_name] = _average(
                    value,
                    counters.get(f"orchestrator.tool_calls.{tool_name}.total", 0),
                )
            phase_latency_ms = {
                phase: _average(
                    counters.get(f"runtime.phase.{phase}.latency_ms_total", 0),
                    counters.get(f"runtime.phase.{phase}.count_total", 0),
                )
                for phase in ("queue_wait", "fetching_data", "llm_execution", "final_response")
            }
            route_latency_ms = {
                "conversation_list": _average(
                    counters.get("api.conversations.list.latency_ms_total", 0),
                    counters.get("api.conversations.list.success_total", 0),
                ),
                "conversation_messages": _average(
                    counters.get("api.conversations.messages.latency_ms_total", 0),
                    counters.get("api.conversations.messages.success_total", 0),
                ),
                "document_list": _average(
                    counters.get("api.documents.list.latency_ms_total", 0),
                    counters.get("api.documents.list.success_total", 0),
                ),
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
                    "phase_latency_ms": phase_latency_ms,
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
                    "average_final_response_latency_ms": _average(
                        counters.get("orchestrator.final_response.latency_ms_total", 0),
                        counters.get("orchestrator.final_response.count_total", 0),
                    ),
                    "average_tool_call_latency_ms": _average(
                        counters.get("orchestrator.tool_calls.latency_ms_total", 0),
                        counters.get("orchestrator.tool_calls_total", 0),
                    ),
                    "tool_latency_ms": tool_latency_ms,
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
                    "route_latency_ms": route_latency_ms,
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
            documents = await offload_blocking_call(
                doc_processor.get_documents,
                user_id="default",
            )

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
            success = await offload_blocking_call(
                doc_processor.delete_document,
                document_id,
                user_id="default",
            )

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
