from langchain.memory.chat_memory import BaseChatMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from backend.database.operations import db_ops
from typing import Dict, Any, List
import json


class SQLiteConversationMemory(BaseChatMemory):
    """Custom LangChain memory that persists to SQLite database."""
    
    conversation_id: str = ""
    memory_key: str = "chat_history"
    
    def __init__(self, conversation_id: str, return_messages: bool = True, **kwargs):
        super().__init__(return_messages=return_messages, **kwargs)
        self.conversation_id = conversation_id
        self.memory_key = "chat_history"
    
    @property
    def memory_variables(self) -> List[str]:
        """Return the memory variables."""
        return [self.memory_key]
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save conversation context to database."""
        # Save the current interaction
        input_str = inputs.get(self.input_key, "")
        output_str = outputs.get(self.output_key, "")
        
        # Create messages
        human_message = HumanMessage(content=input_str)
        ai_message = AIMessage(content=output_str)
        
        # Add to chat memory
        self.chat_memory.add_message(human_message)
        self.chat_memory.add_message(ai_message)
        
        # Save to database
        messages_data = [
            {"type": "human", "content": human_message.content},
            {"type": "ai", "content": ai_message.content}
        ]
        
        db_ops.save_conversation_memory(
            self.conversation_id,
            self.memory_key,
            json.dumps(messages_data)
        )
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables from database."""
        # Load from database if memory is empty
        if not self.chat_memory.messages:
            memory_data = db_ops.load_conversation_memory(self.conversation_id)
            
            if self.memory_key in memory_data:
                try:
                    messages_data = json.loads(memory_data[self.memory_key])
                    for msg_data in messages_data:
                        if msg_data["type"] == "human":
                            self.chat_memory.add_message(HumanMessage(content=msg_data["content"]))
                        elif msg_data["type"] == "ai":
                            self.chat_memory.add_message(AIMessage(content=msg_data["content"]))
                except json.JSONDecodeError:
                    pass  # Handle corrupted data gracefully
        
        # Return memory variables
        if self.return_messages:
            return {self.memory_key: self.chat_memory.messages}
        else:
            return {self.memory_key: self.buffer}
    
    def clear(self) -> None:
        """Clear memory."""
        super().clear()
        # Clear from database as well
        db_ops.save_conversation_memory(self.conversation_id, self.memory_key, "[]")
    
    @property
    def buffer(self) -> str:
        """Get string buffer of conversation."""
        messages = self.chat_memory.messages
        if not messages:
            return ""
        
        string_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                string_messages.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                string_messages.append(f"AI: {message.content}")
        
        return "\n".join(string_messages)
