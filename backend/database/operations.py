from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.database.models import Base, Conversation, Message, MemoryStore, RuntimeCounter
from backend.config import settings
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, timezone
import atexit


class DatabaseOperations:
    """Database operations for the personal agent."""
    
    def __init__(self):
        self.engine = create_engine(f"sqlite:///{settings.database_path}")
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()

    def close(self):
        """Dispose database engine and release pooled connections."""
        if getattr(self, "engine", None) is not None:
            self.engine.dispose()
    
    def create_conversation(self, title: Optional[str] = None, user_id: str = "default") -> str:
        """Create a new conversation and return its ID."""
        if not title:
            title = f"Conversation {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        
        session = self.get_session()
        try:
            conversation = Conversation(title=title, user_id=user_id)
            session.add(conversation)
            session.commit()
            return conversation.id
        finally:
            session.close()
    
    def get_conversations(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """Get all conversations for a user."""
        session = self.get_session()
        try:
            conversations = session.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.updated_at.desc()).all()
            
            return [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages)
                }
                for conv in conversations
            ]
        finally:
            session.close()
    
    def save_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str,
        agent_actions: Optional[str] = None,
        token_usage: Optional[int] = None
    ) -> str:
        """Save a message to the database."""
        session = self.get_session()
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                agent_actions=agent_actions,
                token_usage=token_usage
            )
            session.add(message)
            
            # Update conversation timestamp
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if conversation:
                conversation.updated_at = datetime.now(timezone.utc)
            
            session.commit()
            return message.id
        finally:
            session.close()
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation message history."""
        session = self.get_session()
        try:
            messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.timestamp.asc()).all()
            
            return [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "agent_actions": json.loads(msg.agent_actions) if msg.agent_actions else None,
                    "token_usage": msg.token_usage
                }
                for msg in messages
            ]
        finally:
            session.close()
    
    def save_conversation_memory(self, conversation_id: str, key: str, value: str):
        """Save conversation memory data for LangChain."""
        session = self.get_session()
        try:
            # Remove existing entry for this key
            session.query(MemoryStore).filter(
                MemoryStore.conversation_id == conversation_id,
                MemoryStore.key == key
            ).delete()
            
            # Add new entry
            memory_entry = MemoryStore(
                conversation_id=conversation_id,
                key=key,
                value=value
            )
            session.add(memory_entry)
            session.commit()
        finally:
            session.close()
    
    def load_conversation_memory(self, conversation_id: str) -> Dict[str, str]:
        """Load conversation memory data for LangChain."""
        session = self.get_session()
        try:
            memory_entries = session.query(MemoryStore).filter(
                MemoryStore.conversation_id == conversation_id
            ).all()
            
            return {entry.key: entry.value for entry in memory_entries}
        finally:
            session.close()
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation by ID."""
        session = self.get_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return None
            
            return {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "user_id": conversation.user_id
            }
        finally:
            session.close()
    
    def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        """Update the title of a conversation."""
        session = self.get_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return False
            
            conversation.title = title
            conversation.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            session.close()
    
    def is_conversation_untitled(self, conversation_id: str) -> bool:
        """Check if a conversation has a default/generated title."""
        session = self.get_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return False
            
            # Check if title looks like a default generated one
            default_patterns = [
                "Conversation ",
                "New Conversation",
                "Chat "
            ]
            
            return any(conversation.title.startswith(pattern) for pattern in default_patterns)
        finally:
            session.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its related data."""
        session = self.get_session()
        try:
            # First, delete all messages in the conversation
            session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).delete()
            
            # Delete all memory entries for this conversation
            session.query(MemoryStore).filter(
                MemoryStore.conversation_id == conversation_id
            ).delete()
            
            # Finally, delete the conversation itself
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return False
            
            session.delete(conversation)
            session.commit()
            return True
        finally:
            session.close()

    def increment_runtime_counter(self, key: str, amount: int = 1) -> int:
        """Increment and return a runtime counter."""
        if amount < 0:
            raise ValueError("Counter increment amount must be non-negative")

        session = self.get_session()
        try:
            counter = session.query(RuntimeCounter).filter(RuntimeCounter.key == key).first()
            if counter is None:
                counter = RuntimeCounter(key=key, value=0)
                session.add(counter)
                session.flush()

            counter.value += amount
            counter.updated_at = datetime.now(timezone.utc)
            session.commit()
            return counter.value
        finally:
            session.close()

    def get_runtime_counters(self, prefix: Optional[str] = None) -> Dict[str, int]:
        """Return runtime counters optionally filtered by key prefix."""
        session = self.get_session()
        try:
            query = session.query(RuntimeCounter)
            if prefix:
                query = query.filter(RuntimeCounter.key.like(f"{prefix}%"))
            rows = query.order_by(RuntimeCounter.key.asc()).all()
            return {row.key: row.value for row in rows}
        finally:
            session.close()


# Global database operations instance
db_ops = DatabaseOperations()
atexit.register(db_ops.close)
