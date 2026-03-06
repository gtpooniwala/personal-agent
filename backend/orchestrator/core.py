from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from backend.llm import create_chat_model, predict_text, MissingProviderKeyError, MissingModelDependencyError
from backend.orchestrator.tool_registry import ToolRegistry
from ..database.operations import db_ops
from typing import Dict, Any, Optional, List
import json
import logging
import re

logger = logging.getLogger(__name__)


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
        self.tool_registry = ToolRegistry(user_id)
        self.current_conversation_id = None
        self.current_memory = None
        self.orchestrator_agent = None
    
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
    
    def _setup_orchestrator_agent(self, conversation_id: str, force_refresh: bool = False):
        """
        Setup the LangGraph ReAct agent that serves as the orchestrator's decision-making brain.
        
        This agent is responsible for:
        - Understanding user intent
        - Deciding which tools/agents to use
        - Coordinating multi-tool workflows
        - Providing natural language responses
        
        Uses LangGraph's create_react_agent which automatically handles tool descriptions
        and provides better state management than legacy AgentExecutor.
        """
        if self.current_conversation_id == conversation_id and self.orchestrator_agent and not force_refresh:
            return  # Already setup for this conversation
        
        self.current_conversation_id = conversation_id
        
        # Get available tools from the registry (no need for manual tool descriptions!)
        available_tools = self.tool_registry.get_available_tools()

        # Get document context to inform the agent about document availability
        document_context = self._get_document_context()

        # Default system prompt (always included)
        system_prompt = """# PERSONAL ASSISTANT CORE ORCHESTRATOR

## IDENTITY & ROLE
You are an intelligent personal assistant's orchestrator agent. Your purpose is to understand user needs and execute appropriate tools to fulfill them efficiently. You operate using a Reasoning-Acting (ReAct) framework.

## AGENT BEHAVIOR GUIDELINES
- Use available tools when appropriate to answer user queries or perform actions.
- Your job is to analyze the user request, decide which tools to use (including document search, calculator, etc.), and provide a direct final response to the user.
- Avoid asking the user for clarification; always attempt to execute the task to the best of your ability with the information provided.
- Never explain which tool you will use—just use it.
- Never guess or use a tool inappropriately; if unsure, do your best with the available information.
- You can use some tools multiple times if needed, but only if you expect to get new information or perform a different action.
- For document-related queries, use the `search_documents` tool to find relevant information even if you are not sure which document the answer is in.
- **You operate in an iterative, cyclical fashion:** After each tool call, re-evaluate the current state and decide if another tool/action is needed. Continue this loop until all necessary actions are complete, then provide a final response.
- If you still cant find sufficient information to answer the user query after using all available tools iteratively, clearly tell the user what is missing and suggest they try rephrasing their question or using a different approach.

## SUCCESS METRICS
Your effectiveness is measured by:
1. **Accuracy**: Right tool for the right query
2. **Efficiency**: No unnecessary tool usage
3. **Naturalness**: Smooth, conversational responses
4. **Correct Workflow**: Use tools only when needed and provide a clear final answer.
"""

        # If files are available, append document context
        if document_context.get('has_documents', False) and document_context.get('selected_count', 0) > 0:
            system_prompt += f"""
\n## CONTEXT\nThe following documents have been selected and available to you. Use search_documents tool in case you need additional context for this conversation:\n{self._format_document_status(document_context)}"""

        # Create memory saver for this conversation
        memory = MemorySaver()
        
        self._ensure_llm()
        # Create LangGraph ReAct agent with automatic tool binding
        self.orchestrator_agent = create_react_agent(
            model=self.llm,
            tools=available_tools,
            prompt=system_prompt,
            checkpointer=memory  # Provides persistent conversation memory
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
    
    async def process_request(
        self, 
        user_request: str, 
        conversation_id: str,
        selected_documents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Main orchestrator method that processes user requests.
        
        This is the core orchestration logic:
        1. Setup the orchestrator agent for the conversation
        2. Update available tools based on context (e.g., selected documents)
        3. Let the agent analyze and delegate tasks
        4. Track and return the orchestration results
        """
        try:
            self._ensure_llm()
            # Update tool registry with selected documents if provided
            if selected_documents is not None:
                self.tool_registry.update_selected_documents(selected_documents)
                # Force agent re-setup with updated tools
                self._setup_orchestrator_agent(conversation_id, force_refresh=True)
            else:
                # Normal setup
                self._setup_orchestrator_agent(conversation_id)
            
            # Save user message to database
            db_ops.save_message(conversation_id, "user", user_request)

            # Use condensed conversation history for agent context
            condensed_history = self.get_condensed_conversation_history(conversation_id)
            messages = []
            for msg in condensed_history:
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))
                elif msg['role'] == 'system':
                    # Some LangGraph model integrations reject system messages inside rolling history.
                    continue
                # Optionally, handle other system/tool messages here if needed
            token_usage = None
            total_cost = None
            try:
                config = {"configurable": {"thread_id": conversation_id}}
                result = self.orchestrator_agent.invoke({"messages": messages}, config=config)
                orchestration_actions = self._extract_langgraph_actions(result["messages"]) if result and "messages" in result else []
                tool_results = orchestration_actions if orchestration_actions else []
                response_agent_tool = self.tool_registry._tools.get("response_agent")
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
            except Exception as e:
                logger.warning(f"LangGraph agent processing failed: {str(e)}")
                orchestration_actions = self._run_rule_based_fallback(user_request)
                if orchestration_actions:
                    response_agent_tool = self.tool_registry._tools.get("response_agent")
                    if response_agent_tool:
                        conversation_history = self.get_condensed_conversation_history(conversation_id)
                        response = response_agent_tool._run(
                            user_query=user_request,
                            tool_results=orchestration_actions,
                            conversation_history=conversation_history
                        )
                    else:
                        response = orchestration_actions[-1].get("output", "")
                else:
                    response = await predict_text(self.llm, user_request)
                    orchestration_actions = []
            
            # Save orchestrator response to database
            db_ops.save_message(
                conversation_id, 
                "assistant", 
                response,
                agent_actions=json.dumps(orchestration_actions) if orchestration_actions else None,
                token_usage=token_usage
            )

            # Trigger summarisation in the background (do not await)
            import asyncio
            asyncio.create_task(self.maybe_summarise_conversation(conversation_id))

            # Return response immediately
            return {
                "response": response,
                "conversation_id": conversation_id,
                "orchestration_actions": orchestration_actions,
                "token_usage": token_usage,
                "cost": total_cost
            }
            
        except (MissingProviderKeyError, MissingModelDependencyError) as e:
            logger.warning(f"LLM setup error: {str(e)}")
            response = str(e)
            db_ops.save_message(conversation_id, "assistant", response)
            return {
                "response": response,
                "conversation_id": conversation_id,
                "error": True
            }
        except Exception as e:
            logger.error(f"Error in orchestrator processing: {str(e)}")
            error_response = f"I apologize, but I encountered an error while processing your request: {str(e)}"
            
            # Save error response
            db_ops.save_message(conversation_id, "assistant", error_response)
            
            return {
                "response": error_response,
                "conversation_id": conversation_id,
                "error": True
            }
    
    async def maybe_summarise_conversation(self, conversation_id: str, context_window_tokens: int = 4096, threshold: float = 0.8) -> bool:
        """
        If conversation history exceeds a threshold ratio of the context window, summarise it and save the summary.
        """
        conversation_history = db_ops.get_conversation_history(conversation_id)
        # Concatenate all messages for token estimation
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        # Estimate tokens (very rough: 1 token ≈ 4 chars)
        token_count = len(history_text) // 4
        if token_count > int(context_window_tokens * threshold):
            # Summarise
            summarisation_agent = self.tool_registry._tools.get("summarisation_agent")
            if summarisation_agent:
                try:
                    summary = await summarisation_agent._arun(history_text)
                    if summary:
                        # Save summary as a special message
                        db_ops.save_message(conversation_id, "system", f"[CONVERSATION SUMMARY]\n{summary}")
                        return True
                except Exception as e:
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

    def _run_rule_based_fallback(self, user_request: str) -> Optional[List[Dict[str, Any]]]:
        """
        Deterministic fallback routing when graph execution fails.
        Keeps common intents functional even if model/tool runtime has transient issues.
        """
        actions: List[Dict[str, Any]] = []
        query = (user_request or "").strip()
        query_lower = query.lower()

        math_expression = self._extract_math_expression(query)
        if math_expression and "calculator" in self.tool_registry._tools:
            output = self.tool_registry._tools["calculator"]._run(expression=math_expression)
            actions.append({
                "tool": "calculator",
                "input": json.dumps({"expression": math_expression}, ensure_ascii=False),
                "output": output,
            })

        if any(token in query_lower for token in ("time", "date", "day")) and "current_time" in self.tool_registry._tools:
            output = self.tool_registry._tools["current_time"]._run(query=query)
            actions.append({
                "tool": "current_time",
                "input": json.dumps({"query": query}, ensure_ascii=False),
                "output": output,
            })

        document_intent = any(token in query_lower for token in ("document", "uploaded", "file", "contract", "pdf"))
        if document_intent:
            search_tool = self.tool_registry._tools.get("search_documents")
            if search_tool:
                output = search_tool._run(query=query, max_results=3)
            else:
                output = "No documents are currently selected. Please select one or more documents to enable document search."
            actions.append({
                "tool": "search_documents",
                "input": json.dumps({"query": query, "max_results": 3}, ensure_ascii=False),
                "output": output,
            })

        internet_intent = any(token in query_lower for token in ("internet", "latest", "news", "headline", "headlines", "search the internet"))
        if internet_intent and "internet_search" in self.tool_registry._tools:
            output = self.tool_registry._tools["internet_search"]._run(query=query, provider="duckduckgo")
            actions.append({
                "tool": "internet_search",
                "input": json.dumps({"query": query, "provider": "duckduckgo"}, ensure_ascii=False),
                "output": output,
            })

        return actions if actions else None

    def _extract_math_expression(self, query: str) -> Optional[str]:
        """Extract likely arithmetic expression from free text user input."""
        candidates = re.findall(r"[\d\.\s\+\-\*\/\(\)]{3,}", query)
        for candidate in candidates:
            expression = candidate.strip()
            if not expression:
                continue
            if not re.search(r"\d", expression):
                continue
            if not re.search(r"[\+\-\*\/]", expression):
                continue
            return expression
        return None

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
        
        This is a specialized orchestrator task that doesn't require delegation.
        """
        try:
            self._ensure_llm()
            # Get conversation history
            messages = db_ops.get_conversation_history(conversation_id)
            
            if len(messages) < 2:  # Need at least user message and assistant response
                return None
            
            # Take first few messages for context (limit to avoid token overflow)
            relevant_messages = messages[:6]  # First 3 exchanges
            
            # Build context for title generation
            conversation_context = "\n".join([
                f"{msg['role'].capitalize()}: {msg['content']}"
                for msg in relevant_messages
            ])
            
            # Create title generation prompt
            title_prompt = f"""Based on the following conversation, generate a concise, descriptive title (maximum 5 words) that captures the main topic or purpose of the conversation.

Conversation:
{conversation_context}

Generate only the title, no additional text or quotes. The title should be specific and meaningful, avoiding generic phrases like "General Chat" or "Conversation".

Title:"""

            # Generate title using orchestrator LLM
            title = await predict_text(self.llm, title_prompt)
            
            # Clean up the title
            title = title.strip().strip('"\'').strip()
            
            # Ensure reasonable length
            if len(title) > 50:
                title = title[:47] + "..."
            
            # Update conversation title in database
            if title:
                db_ops.update_conversation_title(conversation_id, title)
                logger.info(f"Orchestrator generated title for conversation {conversation_id}: {title}")
                return title
            
            return None
            
        except (MissingProviderKeyError, MissingModelDependencyError) as e:
            logger.warning(f"Title generation skipped: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error generating conversation title: {str(e)}")
            return None
    
    def _get_document_context(self) -> Dict[str, Any]:
        """
        Get document context information to inform the orchestrator about document availability.
        This helps the agent make better decisions about when to use document_qa tool.
        """
        try:
            # Import here to avoid circular imports
            from backend.services.document_service import doc_processor
            
            # Get document context for the current user
            selected_docs = self.tool_registry.selected_documents if hasattr(self.tool_registry, 'selected_documents') else []
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
        if not document_context.get('has_documents', False):
            return """❌ NO DOCUMENTS AVAILABLE
- No documents have been uploaded or selected
- Document search is NOT possible
- For document-related queries, inform user that no documents are available
- Do NOT attempt to use tools for document search"""
        
        selected_count = document_context.get('selected_count', 0)
        total_count = document_context.get('document_count', 0)
        
        if selected_count > 0:
            return f"""✅ DOCUMENTS AVAILABLE FOR SEARCH
- {selected_count} document(s) currently selected
- {total_count} total documents uploaded
- Document search is ENABLED via search_documents tool
- Use search_documents tool for any document-related queries"""
        else:
            return f"""⚠️ DOCUMENTS UPLOADED BUT NONE SELECTED
- {total_count} document(s) uploaded but none selected
- Document search is currently DISABLED
- Inform user they need to select documents to enable search"""
