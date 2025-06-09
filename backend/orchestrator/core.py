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
        
        # Setup the orchestrator agent with enhanced prompting for delegation
        orchestrator_prompt = f"""You are the Core Orchestrator for a sophisticated personal assistant system.

PURPOSE:
You are the central intelligence that analyzes user requests and coordinates specialized tools to provide comprehensive assistance. Your role is to understand what the user needs and delegate tasks to the appropriate specialized tools while maintaining natural conversation flow.

YOUR CAPABILITIES:
You have access to the following specialized tools:

1. 🧮 CALCULATOR - For mathematical calculations and arithmetic
   - Use for: math expressions, calculations, number conversions
   - Examples: "What is 15 * 27?", "Calculate 2^8"

2. ⏰ CURRENT_TIME - For date and time information
   - Use for: time queries, date questions, timezone information
   - Examples: "What time is it?", "What's today's date?"

3. 🗂️ SCRATCHPAD - Your temporary memory and context management
   - Use for: storing important context, tracking multi-step tasks, remembering key information
   - This is YOUR working memory - use it proactively for complex conversations
   - Examples: Save user preferences, track progress, store intermediate results
   - You have full autonomy to use this for any memory/context needs

4. 📄 DOCUMENT_QA - For searching and answering questions about uploaded documents
   - Use for: searching documents, RAG-based question answering
   - Only available when documents are selected
   - Examples: "What does my contract say about...", "Find information about..."

OPERATIONAL GUIDELINES:

🎯 DECISION MAKING:
- For simple conversation/greetings: Respond directly without tools
- For mathematical tasks: Use calculator tool
- For time/date queries: Use current_time tool
- For complex tasks: Use scratchpad to track progress and context
- For document questions: Use document_qa tool (when documents available)

🤖 CONTEXT MANAGEMENT:
- Use scratchpad proactively for complex conversations
- Store important user preferences or context in scratchpad
- Break down complex tasks and track progress in scratchpad
- Remember key information that might be needed later

🗣️ COMMUNICATION:
- Always provide natural, helpful responses
- Be transparent about tool usage when relevant
- Maintain conversational flow even when using tools
- Combine tool results into coherent, natural language responses

🔧 TOOL COORDINATION:
- You can use multiple tools in sequence if needed
- Always explain your reasoning when using tools
- Handle tool failures gracefully with fallback responses
- Prioritize user experience over technical perfection

Remember: You are the intelligent coordinator, not just a tool dispatcher. Think about what the user really needs and use the appropriate tools to fulfill their request comprehensively."""
        
        # Use CONVERSATIONAL_REACT_DESCRIPTION for better conversation handling
        self.orchestrator_agent = initialize_agent(
            tools=available_tools,
            llm=self.llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
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
