from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_community.callbacks.manager import get_openai_callback
from orchestrator.memory import SQLiteConversationMemory
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
            model="gpt-3.5-turbo",
            temperature=0.3,  # Lower temperature for more focused decision-making
            openai_api_key=settings.openai_api_key,
            max_tokens=800   # Optimized for orchestration decisions
        )
    
    def _generate_tools_description(self, available_tools) -> str:
        """
        Dynamically generate tool descriptions from actual tool objects.
        This ensures the system prompt always reflects the current available tools.
        """
        tool_descriptions = []
        
        # Icons for different tool types
        tool_icons = {
            "calculator": "🧮",
            "current_time": "⏰", 
            "scratchpad": "🗂️",
            "search_documents": "🔍"
        }
        
        for i, tool in enumerate(available_tools, 1):
            icon = tool_icons.get(tool.name, "🔧")
            tool_name = tool.name.upper().replace("_", " ")
            
            # Use the tool's actual description
            description = tool.description.strip()
            
            tool_descriptions.append(f"{i}. {icon} {tool_name} - {description}")
        
        return "\n\n".join(tool_descriptions)
    
    def _setup_orchestrator_agent(self, conversation_id: str, force_refresh: bool = False):
        """
        Setup the LangChain ReAct agent that serves as the orchestrator's decision-making brain.
        
        This agent is responsible for:
        - Understanding user intent
        - Deciding which tools/agents to use
        - Coordinating multi-tool workflows
        - Providing natural language responses
        """
        if self.current_conversation_id == conversation_id and self.orchestrator_agent and not force_refresh:
            return  # Already setup for this conversation
        
        self.current_conversation_id = conversation_id
        self.current_memory = SQLiteConversationMemory(conversation_id)
        
        # Get available tools from the registry
        available_tools = self.tool_registry.get_available_tools()
        
        # Get document context to inform the agent about document availability
        document_context = self._get_document_context()
        
        # Generate dynamic tool descriptions
        tools_description = self._generate_tools_description(available_tools)
        
        # Setup the orchestrator agent with action-focused prompting
        orchestrator_prompt = f"""You are the Core Orchestrator - the brain of a personal assistant system. Your job is to EXECUTE the right tools for user requests.

CORE DIRECTIVE: When you identify that a tool should be used, USE IT IMMEDIATELY. Do not explain what you will do - DO IT.

AVAILABLE TOOLS:
{tools_description}

DOCUMENT STATUS:
{self._format_document_status(document_context)}

MANDATORY TOOL USAGE RULES:

1. MATHEMATICAL QUERIES → MUST use calculator tool
   Examples: "calculate", "what is", "multiply", "divide", numbers with operators
   
2. TIME/DATE QUERIES → MUST use current_time tool  
   Examples: "what time", "current time", "what's the time", "date", "today"
   
3. DOCUMENT QUERIES → MUST use search_documents tool
   Examples: "documents", "files", "uploaded", "my documents", "tell me about files", "about the uploaded", "about uploaded files"
   
4. MEMORY/NOTES → MUST use scratchpad tool
   Examples: "remember", "save note", "what did I", "my notes"

5. SIMPLE CONVERSATION → Respond directly (no tools)
   Examples: "hello", "hi", "how are you", "thank you"

EXECUTION PROTOCOL:
- If query matches tool category → USE THE TOOL (no explanation needed)
- If query is conversational → respond directly  
- If uncertain → use scratchpad to think through it
- NEVER say "I will use a tool" - just use it
- NEVER provide manual answers when tools exist for the task

Your success is measured by TOOL EXECUTION, not explanations."""
        
        # Use STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION for multi-input tool support
        self.orchestrator_agent = initialize_agent(
            tools=available_tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.current_memory,
            verbose=True,
            max_iterations=3,  # Allow multiple tool calls if needed
            early_stopping_method="generate",
            handle_parsing_errors=True,
            return_intermediate_steps=True
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
            
            # Process with orchestrator agent and track token usage
            with get_openai_callback() as cb:
                try:
                    # Let the orchestrator agent analyze and delegate
                    orchestration_result = self.orchestrator_agent({"input": user_request})
                    response = orchestration_result.get("output", "")
                    intermediate_steps = orchestration_result.get("intermediate_steps", [])
                except Exception as e:
                    logger.warning(f"Orchestrator agent processing failed: {str(e)}")
                    # Fallback to direct LLM only if orchestrator completely fails
                    response = await self.llm.apredict(user_request)
                    intermediate_steps = []
            
            # Extract tool/agent actions from orchestration steps
            orchestration_actions = self._extract_orchestration_actions(intermediate_steps) if intermediate_steps else None
            
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
    
    def _extract_orchestration_actions(self, intermediate_steps: Optional[List] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Extract orchestration actions for transparency.
        
        This shows users which tools/agents were used in the orchestration process.
        """
        if not intermediate_steps:
            return None
            
        actions = []
        for action, observation in intermediate_steps:
            # Skip parsing errors and exceptions
            if hasattr(action, 'tool') and action.tool not in ['_Exception', '_exception']:
                actions.append({
                    "tool": action.tool,
                    "input": action.tool_input,
                    "output": str(observation)
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
