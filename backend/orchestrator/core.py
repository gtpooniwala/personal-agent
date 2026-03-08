import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from backend.llm import create_chat_model, predict_text, MissingProviderKeyError, MissingModelDependencyError
from backend.orchestrator.tool_registry import ToolRegistry
from backend.orchestrator.prompts import (
    build_direct_response_prompt,
    build_orchestrator_system_prompt,
    build_title_prompt,
    format_conversation_history,
)
from ..database.operations import db_ops
from backend.config import agent_config
from backend.observability import observe_operation, update_observation, increment_counter

_NAMING_CFG = agent_config.get("conversation_naming", {})
_TITLE_MAX_LENGTH: int = _NAMING_CFG.get("title_max_length", 50)
_TITLE_CONTEXT_MESSAGES: int = _NAMING_CFG.get("context_messages", 6)

logger = logging.getLogger(__name__)

NO_SELECTED_DOCUMENTS_MESSAGE = (
    "No documents are currently selected. Please select one or more documents "
    "to enable document search."
)
DOCUMENT_INTENT_PATTERN = re.compile(
    r"\b(document|documents|uploaded|file|files|contract|contracts|pdf|pdfs)\b"
)


class CoreOrchestrator:
    """
    Core orchestrator that manages the overall system flow and delegates tasks to specialized tools/agents.
    
    This is the main decision-making component that:
    1. Receives user requests
    2. Analyzes what type of task it is
    3. Delegates to appropriate tools/agents
    4. Coordinates responses back to the user
    
    The orchestrator uses a LangChain ReAct agent as its decision-making brain,
    but all actual work is delegated to specialized tools/agents.
    """
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.llm = None
        # Shared per-user registry for static tools, tool listing, and background summarisation.
        self.tool_registry = ToolRegistry(user_id)
    
    def _setup_llm(self):
        """Setup the language model for the orchestrator."""
        return create_chat_model(
            tool_name="orchestrator",
            temperature=0.3,  # Lower temperature for more focused decision-making
            max_tokens=800   # Optimized for orchestration decisions
        )

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = self._setup_llm()
    
    def _build_orchestrator_agent(self, conversation_id: str, tool_registry: ToolRegistry):
        """
        Build and return a fresh LangGraph ReAct agent for a single run.

        Creating a new agent per run guarantees that concurrent runs for different
        conversations cannot overwrite each other's tool context or agent state.
        """
        available_tools = tool_registry.get_available_tools()
        document_context = self._get_document_context(tool_registry)
        system_prompt = build_orchestrator_system_prompt(self._format_document_status(document_context))
        self._ensure_llm()
        return create_react_agent(
            model=self.llm,
            tools=available_tools,
            prompt=system_prompt,
            checkpointer=MemorySaver(),
        )
    
    def get_condensed_conversation_history(self, conversation_id: str) -> list:
        """
        Returns the most recent summary (if any), the 4 non-summary messages before it (if they exist), and all messages after it.
        If no summary, returns the full conversation history.
        """
        history = db_ops.get_conversation_history(conversation_id)
        summary_idx = None
        for i in reversed(range(len(history))):
            msg = history[i]
            if msg['role'] == 'system' and msg['content'].startswith('[CONVERSATION SUMMARY]'):
                summary_idx = i
                break
        if summary_idx is not None:
            # Find the 4 non-summary messages before the summary
            pre_summary = []
            count = 0
            j = summary_idx - 1
            while j >= 0 and count < 4:
                if not (history[j]['role'] == 'system' and history[j]['content'].startswith('[CONVERSATION SUMMARY]')):
                    pre_summary.append(history[j])
                    count += 1
                j -= 1
            pre_summary = list(reversed(pre_summary))
            return [history[summary_idx]] + pre_summary + history[summary_idx+1:]
        else:
            return history

    def _build_langgraph_messages(self, condensed_history: List[Dict[str, Any]]) -> List:
        """
        Convert stored conversation history to LangChain messages for graph invocation.
        Summary system messages are preserved as a synthetic context HumanMessage because
        some model integrations reject mid-history SystemMessage entries.
        """
        messages = []
        summary_blocks: List[str] = []
        summary_prefix = "[CONVERSATION SUMMARY]"

        for msg in condensed_history:
            role = msg.get("role")
            content = str(msg.get("content", ""))

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                if content.startswith(summary_prefix):
                    summary_text = content[len(summary_prefix):].strip() or content.strip()
                    if summary_text:
                        summary_blocks.append(summary_text)
                # Skip all system messages in rolling history.
                continue

        if summary_blocks:
            summary_context = "\n\n".join(summary_blocks)
            messages.insert(
                0,
                HumanMessage(
                    content=(
                        "Context from earlier conversation summary (for reference only; "
                        "not a new user request):\n"
                        f"{summary_context}"
                    )
                ),
            )

        return messages
    
    async def process_request(
        self, 
        user_request: str, 
        conversation_id: str,
        selected_documents: Optional[List[str]] = None,
        spawn_background_tasks: bool = True,
    ) -> Dict[str, Any]:
        """
        Main orchestrator method that processes user requests.
        
        This is the core orchestration logic:
        1. Setup the orchestrator agent for the conversation
        2. Update available tools based on context (e.g., selected documents)
        3. Let the agent analyze and delegate tasks
        4. Track and return the orchestration results
        """
        with observe_operation(
            name="orchestrator.process_request",
            counter_prefix="orchestrator.process_request",
            as_type="chain",
            conversation_id=conversation_id,
            input_data={
                "request_chars": len(user_request or ""),
                "selected_documents_count": len(selected_documents or []),
            },
            metadata={"component": "orchestrator"},
        ) as operation_observation:
            try:
                self._ensure_llm()
                # Clone static tools and rebuild only document-scoped state per run
                # so concurrent requests do not share mutable document context.
                run_registry = self.tool_registry.clone_with_selected_documents(selected_documents)
                run_agent = self._build_orchestrator_agent(conversation_id, run_registry)

                # Save user message to database
                db_ops.save_message(conversation_id, "user", user_request)

                # Use condensed conversation history for agent context
                condensed_history = self.get_condensed_conversation_history(conversation_id)
                messages = self._build_langgraph_messages(condensed_history)
                token_usage = None
                fallback_used = False
                try:
                    with observe_operation(
                        name="orchestrator.langgraph.invoke",
                        counter_prefix="orchestrator.langgraph.invoke",
                        as_type="generation",
                        conversation_id=conversation_id,
                        input_data={"messages_count": len(messages)},
                        metadata={"component": "orchestrator"},
                    ) as invoke_observation:
                        config = {"configurable": {"thread_id": conversation_id}}
                        result = run_agent.invoke({"messages": messages}, config=config)
                        orchestration_actions = (
                            self._extract_langgraph_actions(result["messages"])
                            if result and "messages" in result
                            else []
                        ) or []
                        tool_results = orchestration_actions
                        response_agent_tool = run_registry.get_tool("response_agent")
                        if response_agent_tool:
                            # Use condensed history for response agent as well
                            conversation_history = self.get_condensed_conversation_history(conversation_id)
                            response = response_agent_tool._run(
                                user_query=user_request,
                                tool_results=tool_results,
                                conversation_history=conversation_history
                            )
                        else:
                            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                            if ai_messages:
                                response = ai_messages[-1].content
                            else:
                                response = "I apologize, but I couldn't process your request properly."

                        if result and "messages" in result:
                            usage = self._extract_usage_metadata(result["messages"])
                            if usage:
                                token_usage = usage.get("total_tokens")
                                update_observation(invoke_observation, usage_details={k: int(v) for k, v in usage.items() if isinstance(v, int)})
                except Exception as e:
                    logger.warning(f"LangGraph agent processing failed: {str(e)}")
                    increment_counter("orchestrator.fallback_total")
                    fallback_used = True
                    # Normal tool selection belongs to the model from the currently
                    # bound tool set. If orchestration fails catastrophically, fall
                    # back to an honest direct response rather than switching to a
                    # second handwritten routing policy. Retry behavior is tracked
                    # separately from this ownership cleanup.
                    response = await self._generate_direct_response(
                        user_request=user_request,
                        conversation_history=condensed_history,
                    )
                    orchestration_actions = []

                for action in orchestration_actions or []:
                    tool_name = action.get("tool", "unknown")
                    increment_counter("orchestrator.tool_calls_total")
                    increment_counter(f"orchestrator.tool_calls.{tool_name}.total")
                if token_usage:
                    increment_counter("orchestrator.token_usage_total", amount=int(token_usage))

                response = self._enforce_capability_boundaries(
                    response=response,
                    user_request=user_request,
                    tool_registry=run_registry,
                    orchestration_actions=orchestration_actions,
                )

                update_observation(
                    operation_observation,
                    output={
                        "tool_actions_count": len(orchestration_actions or []),
                        "token_usage": token_usage,
                        "fallback_used": fallback_used,
                    },
                )

                # Save orchestrator response to database
                db_ops.save_message(
                    conversation_id,
                    "assistant",
                    response,
                    agent_actions=json.dumps(orchestration_actions) if orchestration_actions else None,
                    token_usage=token_usage
                )

                # Worker-thread execution disables background task spawning so the
                # runtime can schedule follow-up work from the main event loop.
                if spawn_background_tasks:
                    async def _summarise_background() -> None:
                        try:
                            await self.maybe_summarise_conversation(conversation_id)
                        except Exception:
                            logger.exception(
                                "Background summarisation failed",
                                extra={
                                    "event": "orchestrator.summarisation_failed",
                                    "conversation_id": conversation_id,
                                },
                            )

                    asyncio.create_task(_summarise_background())

                # Return response immediately
                return {
                    "response": response,
                    "conversation_id": conversation_id,
                    "orchestration_actions": orchestration_actions,
                    "token_usage": token_usage,
                }

            except (MissingProviderKeyError, MissingModelDependencyError) as e:
                logger.warning(f"LLM setup error: {str(e)}")
                response = "I can't process this request right now because the model configuration is unavailable."
                db_ops.save_message(conversation_id, "assistant", response)
                increment_counter("orchestrator.process_request.handled_error_total")
                update_observation(
                    operation_observation,
                    output={"error": True},
                    metadata={"error_type": type(e).__name__},
                    status_message=str(e),
                )
                return {
                    "response": response,
                    "conversation_id": conversation_id,
                    "error": True
                }
            except Exception as e:
                logger.error(f"Error in orchestrator processing: {str(e)}")
                error_response = "I apologize, but I encountered an internal error while processing your request. Please try again."

                # Save error response
                db_ops.save_message(conversation_id, "assistant", error_response)
                increment_counter("orchestrator.process_request.exceptions_total")
                increment_counter("orchestrator.process_request.handled_error_total")
                update_observation(
                    operation_observation,
                    output={"error": True},
                    metadata={"error_type": type(e).__name__},
                    status_message=str(e),
                )

                return {
                    "response": error_response,
                    "conversation_id": conversation_id,
                    "error": True
                }
    
    async def maybe_summarise_conversation(self, conversation_id: str, context_window_tokens: int = 4096, threshold: float = 0.8) -> bool:
        """
        If conversation history exceeds a threshold ratio of the context window, summarise it and save the summary.
        """
        with observe_operation(
            name="orchestrator.maybe_summarise_conversation",
            counter_prefix="orchestrator.summarisation",
            as_type="chain",
            conversation_id=conversation_id,
            metadata={"component": "orchestrator"},
        ):
            conversation_history = db_ops.get_conversation_history(conversation_id)
            # Concatenate all messages for token estimation
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
            # Estimate tokens (very rough: 1 token ≈ 4 chars)
            token_count = len(history_text) // 4
            if token_count > int(context_window_tokens * threshold):
                # Summarise
                summarisation_agent = self.tool_registry.get_tool("summarisation_agent")
                if summarisation_agent:
                    try:
                        summary = await summarisation_agent._arun(history_text)
                        if summary:
                            # Save summary as a special message
                            db_ops.save_message(conversation_id, "system", f"[CONVERSATION SUMMARY]\n{summary}")
                            increment_counter("orchestrator.summarisation.generated_total")
                            return True
                    except Exception as e:
                        increment_counter("orchestrator.summarisation.failures_total")
                        logger.warning(f"Skipping summarisation: {str(e)}")
            return False

    def _extract_usage_metadata(self, messages: List) -> Optional[Dict[str, Any]]:
        """Extract usage metadata when the provider exposes token counters."""
        for message in reversed(messages):
            usage = getattr(message, "usage_metadata", None)
            if isinstance(usage, dict):
                return {
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            response_metadata = getattr(message, "response_metadata", None)
            if isinstance(response_metadata, dict):
                token_usage = response_metadata.get("token_usage")
                if isinstance(token_usage, dict):
                    total = token_usage.get("total_tokens")
                    if total is not None:
                        return {
                            "input_tokens": token_usage.get("prompt_tokens"),
                            "output_tokens": token_usage.get("completion_tokens"),
                            "total_tokens": total,
                        }
        return None

    async def _generate_direct_response(
        self,
        *,
        user_request: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Fallback direct response when the graph cannot complete and no tool route applies."""
        prompt = build_direct_response_prompt(
            user_request=user_request,
            conversation_history=conversation_history,
        )
        return await predict_text(self.llm, prompt)

    def _has_document_intent(self, query: str) -> bool:
        return DOCUMENT_INTENT_PATTERN.search((query or "").lower()) is not None

    def _build_no_selected_documents_response(self, user_request: str) -> str:
        query_lower = (user_request or "").strip().lower()
        if "contract" in query_lower:
            return f"I can't answer what your contract says because {NO_SELECTED_DOCUMENTS_MESSAGE}"
        return (
            "I can't answer questions about your uploaded documents because "
            f"{NO_SELECTED_DOCUMENTS_MESSAGE}"
        )

    def _document_capability_boundary_response(
        self,
        *,
        user_request: str,
        tool_registry: ToolRegistry,
        orchestration_actions: Optional[List[Dict[str, Any]]],
    ) -> Optional[str]:
        if tool_registry.get_tool("search_documents") is not None:
            return None
        if not self._has_document_intent(user_request):
            return None
        if any(action.get("tool") == "search_documents" for action in orchestration_actions or []):
            return None
        return self._build_no_selected_documents_response(user_request)

    def _enforce_capability_boundaries(
        self,
        *,
        response: str,
        user_request: str,
        tool_registry: ToolRegistry,
        orchestration_actions: Optional[List[Dict[str, Any]]],
    ) -> str:
        document_boundary = self._document_capability_boundary_response(
            user_request=user_request,
            tool_registry=tool_registry,
            orchestration_actions=orchestration_actions,
        )
        if document_boundary is None:
            return response

        response_text = (response or "").strip()
        if NO_SELECTED_DOCUMENTS_MESSAGE.lower() in response_text.lower():
            return response

        other_tool_actions = [
            action for action in (orchestration_actions or [])
            if action.get("tool") != "search_documents"
        ]
        if other_tool_actions and response_text:
            return f"{response_text}\n\n{document_boundary}"
        return document_boundary

    def _extract_langgraph_actions(self, messages: List) -> Optional[List[Dict[str, Any]]]:
        """
        Extract LangGraph actions for transparency.
        Skips messages that do not have tool call structure (e.g., system messages like summaries).
        Handles both dict and object tool_call/tool_message formats.
        Never fails on missing tool_call_id.
        """
        if not messages:
            return None
        actions = []
        for i, message in enumerate(messages):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    # Get tool_call id safely
                    if isinstance(tool_call, dict):
                        tool_call_id = tool_call.get('id')
                        tool_name = tool_call.get('name', 'unknown')
                        tool_input = tool_call.get('args', {})
                    else:
                        tool_call_id = getattr(tool_call, 'id', None)
                        tool_name = getattr(tool_call, 'name', 'unknown')
                        tool_input = getattr(tool_call, 'args', {})
                    # Find corresponding tool response
                    tool_response = None
                    for j in range(i + 1, len(messages)):
                        msg_j = messages[j]
                        msg_tool_call_id = getattr(msg_j, 'tool_call_id', None) if hasattr(msg_j, 'tool_call_id') else None
                        if msg_tool_call_id and tool_call_id and msg_tool_call_id == tool_call_id:
                            tool_response = getattr(msg_j, 'content', None)
                            break
                    # Safely convert tool_input to dict if possible
                    try:
                        if not isinstance(tool_input, dict):
                            if hasattr(tool_input, 'model_dump'):
                                tool_input = tool_input.model_dump()
                            elif hasattr(tool_input, 'dict'):
                                tool_input = tool_input.dict()
                    except Exception:
                        pass
                    if isinstance(tool_input, dict):
                        import json
                        tool_input_pretty = json.dumps(tool_input, ensure_ascii=False, indent=2)
                    else:
                        tool_input_pretty = str(tool_input)
                    actions.append({
                        "tool": tool_name,
                        "input": tool_input_pretty,
                        "output": tool_response or "No response captured"
                    })
        return actions if actions else None
    
    def create_conversation(self, title: Optional[str] = None) -> str:
        """Create a new conversation through the orchestrator."""
        return db_ops.create_conversation(title, self.user_id)
    
    def get_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations for the user."""
        return db_ops.get_conversations(self.user_id)
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation message history."""
        return db_ops.get_conversation_history(conversation_id)
    
    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get list of available tools/agents from the registry."""
        tools = self.tool_registry.get_available_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ]
    
    async def generate_conversation_title(self, conversation_id: str) -> Optional[str]:
        """
        Generate a conversation title using the orchestrator's LLM.

        Runs all database I/O in a thread so the event loop is never blocked.
        Returns the generated title string, or None if generation was skipped or failed.
        """
        try:
            self._ensure_llm()

            # Skip if the conversation already has a real title (idempotency guard).
            already_titled = not await asyncio.to_thread(
                db_ops.is_conversation_untitled, conversation_id
            )
            if already_titled:
                return None
            messages = await asyncio.to_thread(
                db_ops.get_conversation_history, conversation_id
            )
            if not messages:
                return None

            relevant_messages = messages[:_TITLE_CONTEXT_MESSAGES]
            conversation_context = format_conversation_history(
                relevant_messages,
                max_messages=None,
            )
            title_prompt = build_title_prompt(conversation_context)

            title = await predict_text(self.llm, title_prompt)
            title = title.strip().strip('"\'').strip()

            if len(title) > _TITLE_MAX_LENGTH:
                if _TITLE_MAX_LENGTH > 3:
                    title = title[:_TITLE_MAX_LENGTH - 3] + "..."
                else:
                    title = title[:_TITLE_MAX_LENGTH]

            if title:
                # Re-check before writing to guard against concurrent naming tasks.
                still_untitled = await asyncio.to_thread(
                    db_ops.is_conversation_untitled, conversation_id
                )
                if not still_untitled:
                    logger.debug(
                        f"Skipping title write for {conversation_id}: already titled by concurrent task"
                    )
                    return None
                await asyncio.to_thread(
                    db_ops.update_conversation_title, conversation_id, title
                )
                logger.info(f"Generated title for conversation {conversation_id}: {title}")
                return title

            return None

        except (MissingProviderKeyError, MissingModelDependencyError) as e:
            logger.warning(f"Title generation skipped: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error generating conversation title: {str(e)}")
            return None
    
    def _get_document_context(self, tool_registry: ToolRegistry) -> Dict[str, Any]:
        """
        Get document context information to inform the orchestrator about document availability.
        This helps the agent make better decisions about when to use document_qa tool.
        """
        try:
            # Import here to avoid circular imports
            from backend.services.document_service import doc_processor

            selected_docs = tool_registry.selected_documents if hasattr(tool_registry, 'selected_documents') else []
            return doc_processor.get_document_context(
                user_id=self.user_id,
                selected_documents=selected_docs if selected_docs else None
            )
        except Exception as e:
            logger.warning(f"Error getting document context: {str(e)}")
            return {
                "has_documents": False,
                "document_count": 0,
                "selected_count": 0,
                "total_chunks": 0
            }
    
    def _format_document_status(self, document_context: Dict[str, Any]) -> str:
        """Format document status information for the system prompt."""
        selected_count = int(document_context.get('selected_count', 0) or 0)
        total_count = int(document_context.get('document_count', 0) or 0)
        context_message = document_context.get("context_message", "")

        if selected_count > 0 and document_context.get('has_documents', False):
            return f"""✅ DOCUMENTS AVAILABLE FOR SEARCH
- {selected_count} document(s) currently selected
- {total_count} total matching document(s) available
- Document search is ENABLED via search_documents tool
- Use search_documents for document-related queries"""

        if selected_count > 0:
            return f"""⚠️ DOCUMENT SEARCH REQUESTED WITH SELECTED IDS
- {selected_count} document reference(s) are selected for this conversation
- Document metadata is unavailable or no processed documents matched the selected IDs
- You may still use search_documents if the user is clearly asking about the selected files
- If search_documents returns no results, explain that you could not find relevant content in the selected documents
- Context detail: {context_message or 'No additional metadata available.'}"""

        if not document_context.get('has_documents', False):
            return f"""❌ NO DOCUMENTS AVAILABLE
- No documents have been uploaded or selected
- Document search is NOT possible
- For document-related queries, say exactly: "{NO_SELECTED_DOCUMENTS_MESSAGE}"
- Do NOT attempt to use tools for document search"""

        return f"""⚠️ DOCUMENTS UPLOADED BUT NONE SELECTED
- {total_count} document(s) uploaded but none selected
- Document search is currently DISABLED
- If the user asks about uploaded documents, say exactly: "{NO_SELECTED_DOCUMENTS_MESSAGE}"."""
