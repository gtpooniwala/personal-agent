from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from orchestrator.tool_registry import ToolRegistry
from database.operations import db_ops
from config import settings
from typing import Dict, Any, Optional, List
import json
import logging

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
        self.llm = self._setup_llm()
        self.tool_registry = ToolRegistry(user_id)
        self.current_conversation_id = None
        self.current_memory = None
        self.orchestrator_agent = None
    
    def _setup_llm(self) -> ChatOpenAI:
        """Setup the language model for the orchestrator."""
        return ChatOpenAI(
            model="gpt-3.5-turbo",  # Revert back to GPT-3.5 Turbo
            temperature=0.3,  # Lower temperature for more focused decision-making
            openai_api_key=settings.openai_api_key,
            max_tokens=800   # Optimized for orchestration decisions
        )
    
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
        
        # Setup system prompt using best practices: no hard-coded tool descriptions or selection criteria
        system_prompt = f"""# PERSONAL ASSISTANT CORE ORCHESTRATOR

## IDENTITY & ROLE
You are an intelligent personal assistant orchestrator. Your purpose is to understand user needs and execute appropriate tools to fulfill them efficiently. You operate using a Reasoning-Acting (ReAct) framework.

## CONTEXT
The following documents have been selected for this conversation:
{self._format_document_status(document_context)}

## AGENT BEHAVIOR GUIDELINES
- Use available tools when appropriate to answer user queries or perform actions.
- Respond conversationally and naturally when no tool is needed.
- Never ask the user for clarification; always attempt to execute the task to the best of your ability with the information provided.
- Never explain which tool you will use—just use it.
- Never guess or use a tool inappropriately; if unsure, do your best with the available information.
- Never manually answer when an appropriate tool exists.
- Integrate tool results into your responses when tools are used.
- For document-related queries, use the `search_documents` tool to find relevant information even if you are not sure which document the answer is in.

## SUCCESS METRICS
Your effectiveness is measured by:
1. **Accuracy**: Right tool for the right query
2. **Efficiency**: No unnecessary tool usage
3. **Naturalness**: Smooth, conversational responses"""

        # Create memory saver for this conversation
        memory = MemorySaver()
        
        # Create LangGraph ReAct agent with automatic tool binding
        self.orchestrator_agent = create_react_agent(
            model=self.llm,
            tools=available_tools,
            prompt=system_prompt,
            checkpointer=memory  # Provides persistent conversation memory
        )
    
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
            
            # Process with LangGraph agent and track token usage
            with get_openai_callback() as cb:
                try:
                    # Let the LangGraph agent analyze and delegate
                    # LangGraph uses messages format instead of input/output
                    config = {"configurable": {"thread_id": conversation_id}}
                    
                    # Create message format for LangGraph
                    messages = [HumanMessage(content=user_request)]
                    
                    # Run the agent
                    result = self.orchestrator_agent.invoke(
                        {"messages": messages}, 
                        config=config
                    )
                    
                    # Extract response and tool actions from LangGraph result
                    if result and "messages" in result:
                        # Get the last AI message as the response
                        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                        if ai_messages:
                            response = ai_messages[-1].content
                        else:
                            response = "I apologize, but I couldn't process your request properly."
                        
                        # Extract tool usage from all messages in the conversation
                        orchestration_actions = self._extract_langgraph_actions(result["messages"])
                    else:
                        response = "I apologize, but I encountered an issue processing your request."
                        orchestration_actions = []
                        
                except Exception as e:
                    logger.warning(f"LangGraph agent processing failed: {str(e)}")
                    # Fallback to direct LLM only if agent completely fails
                    response = await self.llm.apredict(user_request)
                    orchestration_actions = []
            
            # Save orchestrator response to database
            db_ops.save_message(
                conversation_id, 
                "assistant", 
                response,
                agent_actions=json.dumps(orchestration_actions) if orchestration_actions else None,
                token_usage=cb.total_tokens
            )
            
            return {
                "response": response,
                "conversation_id": conversation_id,
                "orchestration_actions": orchestration_actions,
                "token_usage": cb.total_tokens,
                "cost": cb.total_cost
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
    
    def _extract_langgraph_actions(self, messages: List) -> Optional[List[Dict[str, Any]]]:
        """
        Extract LangGraph actions for transparency.
        
        Analyzes the message history to identify tool calls and their results.
        """
        if not messages:
            return None
            
        actions = []
        
        # Find tool calls and their responses in the message history
        for i, message in enumerate(messages):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # This is an AI message with tool calls
                for tool_call in message.tool_calls:
                    # Look for the corresponding tool message response
                    tool_response = None
                    for j in range(i + 1, len(messages)):
                        if (isinstance(messages[j], ToolMessage) and 
                            hasattr(messages[j], 'tool_call_id') and
                            messages[j].tool_call_id == tool_call.get('id')):
                            tool_response = messages[j].content
                            break
                    
                    actions.append({
                        "tool": tool_call.get('name', 'unknown'),
                        "input": tool_call.get('args', {}),
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
            title = await self.llm.apredict(title_prompt)
            
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
            from services.document_service import doc_processor
            
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
