from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_community.callbacks.manager import get_openai_callback
from agent.memory import SQLiteConversationMemory
from agent.tools import ToolRegistry
from database.operations import db_ops
from config import settings
from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class PersonalAgent:
    """Main personal agent using LangChain with ReAct pattern."""
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.llm = self._setup_llm()
        self.tool_registry = ToolRegistry(user_id)
        self.current_conversation_id = None
        self.current_memory = None
        self.agent = None
    
    def _setup_llm(self) -> ChatOpenAI:
        """Setup the language model."""
        return ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
            max_tokens=1000
        )
    
    def _setup_agent(self, conversation_id: str):
        """Setup the LangChain agent for a specific conversation."""
        if self.current_conversation_id == conversation_id and self.agent:
            return  # Already setup for this conversation
        
        self.current_conversation_id = conversation_id
        self.current_memory = SQLiteConversationMemory(conversation_id)
        
        tools = self.tool_registry.get_available_tools()
        
        self.agent = initialize_agent(
            tools=tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.current_memory,
            verbose=True,
            max_iterations=3,
            early_stopping_method="generate",
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    async def process_message(
        self, 
        message: str, 
        conversation_id: str
    ) -> Dict[str, Any]:
        """Process a user message and return agent response."""
        try:
            # Setup agent for this conversation
            self._setup_agent(conversation_id)
            
            # Save user message to database
            db_ops.save_message(conversation_id, "user", message)
            
            # Process with agent and track token usage
            with get_openai_callback() as cb:
                # Check if the message likely needs tools
                needs_tools = self._message_needs_tools(message)
                
                if needs_tools:
                    try:
                        # Use agent for tool-requiring questions
                        result = self.agent({"input": message})
                        response = result.get("output", "")
                        intermediate_steps = result.get("intermediate_steps", [])
                    except Exception as e:
                        logger.warning(f"Agent processing failed: {str(e)}")
                        # Fallback to direct LLM
                        response = await self.llm.apredict(message)
                        intermediate_steps = []
                else:
                    # Use direct LLM for simple questions
                    response = await self.llm.apredict(message)
                    intermediate_steps = []
            
            # Extract agent actions from intermediate steps
            agent_actions = self._extract_agent_actions(intermediate_steps) if intermediate_steps else None
            
            # Save assistant response to database
            db_ops.save_message(
                conversation_id, 
                "assistant", 
                response,
                agent_actions=json.dumps(agent_actions) if agent_actions else None,
                token_usage=cb.total_tokens
            )
            
            return {
                "response": response,
                "conversation_id": conversation_id,
                "agent_actions": agent_actions,
                "token_usage": cb.total_tokens,
                "cost": cb.total_cost
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_response = f"I apologize, but I encountered an error: {str(e)}"
            
            # Save error response
            db_ops.save_message(conversation_id, "assistant", error_response)
            
            return {
                "response": error_response,
                "conversation_id": conversation_id,
                "error": True
            }
    
    def _message_needs_tools(self, message: str) -> bool:
        """Determine if a message likely needs tools."""
        message_lower = message.lower()
        
        # Mathematical expressions and calculations
        math_indicators = [
            'calculate', 'compute', 'math', 'multiply', 'divide', 
            'add', 'subtract', 'power', 'square', 'sum', 'product'
        ]
        
        # Time-related queries
        time_indicators = [
            'what time', 'current time', 'what date', 'current date', 
            'what day', 'today', 'now', 'time is it'
        ]
        
        # Check for explicit mathematical expressions
        import re
        if re.search(r'\d+\s*[\+\-\*\/\^x]\s*\d+', message):
            return True
            
        if re.search(r'\d+\s*[\*x]\s*\d+', message):  # multiplication
            return True
            
        if re.search(r'\d+\s*/\s*\d+', message):  # division
            return True
            
        if re.search(r'\d+\s*\+\s*\d+', message):  # addition
            return True
            
        if re.search(r'\d+\s*-\s*\d+', message):  # subtraction
            return True
            
        if re.search(r'\d+\^+\d+', message):  # exponentiation
            return True
        
        # Check for mathematical expressions with words
        if any(indicator in message_lower for indicator in math_indicators):
            # But exclude general "what is" questions
            if not any(phrase in message_lower for phrase in ['capital', 'country', 'city', 'president', 'king', 'queen']):
                return True
            
        # Check for time queries
        if any(indicator in message_lower for indicator in time_indicators):
            return True
            
        return False

    def _extract_agent_actions(self, intermediate_steps: List = None) -> Optional[List[Dict[str, Any]]]:
        """Extract agent actions for transparency when tools are used."""
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
    
    def create_conversation(self, title: str = None) -> str:
        """Create a new conversation."""
        return db_ops.create_conversation(title, self.user_id)
    
    def get_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations for the user."""
        return db_ops.get_conversations(self.user_id)
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation message history."""
        return db_ops.get_conversation_history(conversation_id)
    
    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get list of available tools."""
        tools = self.tool_registry.get_available_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ]
