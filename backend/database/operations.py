from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.database.models import (
    Base,
    Conversation,
    MemoryStore,
    Message,
    Run,
    RunEvent,
    RuntimeCounter,
)
from backend.config import settings
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, timedelta, timezone
import atexit

from backend.runtime import RUN_EVENT_TYPE_SET, RUN_STATUS_SET


class DatabaseOperations:
    """Database operations for the personal agent."""
    
    def __init__(self):
        self.engine = create_engine(settings.database_url, pool_pre_ping=True)
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

    @staticmethod
    def _to_iso(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _serialize_run(run: Run) -> Dict[str, Any]:
        return {
            "id": run.id,
            "conversation_id": run.conversation_id,
            "status": run.status,
            "error": run.error,
            "result": run.result,
            "attempt_count": run.attempt_count,
            "created_at": DatabaseOperations._to_iso(run.created_at),
            "updated_at": DatabaseOperations._to_iso(run.updated_at),
            "started_at": DatabaseOperations._to_iso(run.started_at),
            "completed_at": DatabaseOperations._to_iso(run.completed_at),
        }

    @staticmethod
    def _serialize_run_event(event: RunEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "run_id": event.run_id,
            "type": event.event_type,
            "status": event.status,
            "message": event.message,
            "tool": event.tool,
            "error": event.error,
            "payload": event.payload,
            "created_at": DatabaseOperations._to_iso(event.created_at),
        }

    @staticmethod
    def _serialize_lease_row(row: Any) -> Dict[str, Any]:
        return {
            "lease_key": row["lease_key"],
            "owner_id": row["owner_id"],
            "fencing_token": int(row["fencing_token"]),
            "acquired_at": DatabaseOperations._to_iso(row["acquired_at"]),
            "expires_at": DatabaseOperations._to_iso(row["expires_at"]),
            "updated_at": DatabaseOperations._to_iso(row["updated_at"]),
        }

    @staticmethod
    def _validate_run_status(status: str) -> None:
        if status not in RUN_STATUS_SET:
            raise ValueError(f"Invalid run status: {status}")

    @staticmethod
    def _validate_run_event_type(event_type: str) -> None:
        if event_type not in RUN_EVENT_TYPE_SET:
            raise ValueError(f"Invalid run event type: {event_type}")
    
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

    def create_run(
        self,
        conversation_id: str,
        status: str = "queued",
        error: Optional[str] = None,
        result: Optional[str] = None,
        attempt_count: int = 0,
    ) -> Dict[str, Any]:
        """Create and return a run record."""
        self._validate_run_status(status)
        if attempt_count < 0:
            raise ValueError("attempt_count must be non-negative")

        session = self.get_session()
        try:
            run = Run(
                conversation_id=conversation_id,
                status=status,
                error=error,
                result=result,
                attempt_count=attempt_count,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return self._serialize_run(run)
        finally:
            session.close()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a run record by id."""
        session = self.get_session()
        try:
            run = session.query(Run).filter(Run.id == run_id).first()
            if not run:
                return None
            return self._serialize_run(run)
        finally:
            session.close()

    def update_run(
        self,
        run_id: str,
        status: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[str] = None,
        attempt_count: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update mutable run fields and return the updated record."""
        if status is not None:
            self._validate_run_status(status)
        if attempt_count is not None and attempt_count < 0:
            raise ValueError("attempt_count must be non-negative")

        session = self.get_session()
        try:
            run = session.query(Run).filter(Run.id == run_id).first()
            if not run:
                return None

            if status is not None:
                run.status = status
            if error is not None:
                run.error = error
            if result is not None:
                run.result = result
            if attempt_count is not None:
                run.attempt_count = attempt_count
            if started_at is not None:
                run.started_at = started_at
            if completed_at is not None:
                run.completed_at = completed_at
            run.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(run)
            return self._serialize_run(run)
        finally:
            session.close()

    def append_run_event(
        self,
        run_id: str,
        event_type: str,
        status: str,
        message: Optional[str] = None,
        tool: Optional[str] = None,
        error: Optional[str] = None,
        payload: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append and return a run event."""
        self._validate_run_event_type(event_type)
        self._validate_run_status(status)

        session = self.get_session()
        try:
            event = RunEvent(
                run_id=run_id,
                event_type=event_type,
                status=status,
                message=message,
                tool=tool,
                error=error,
                payload=payload,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return self._serialize_run_event(event)
        finally:
            session.close()

    def list_run_events(
        self,
        run_id: str,
        after_event_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List run events in append order."""
        if limit <= 0:
            raise ValueError("limit must be positive")

        session = self.get_session()
        try:
            query = session.query(RunEvent).filter(RunEvent.run_id == run_id)
            if after_event_id is not None:
                query = query.filter(RunEvent.id > after_event_id)
            events = query.order_by(RunEvent.id.asc()).limit(limit).all()
            return [self._serialize_run_event(event) for event in events]
        finally:
            session.close()

    def acquire_lease(
        self,
        lease_key: str,
        owner_id: str,
        ttl_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        """Acquire or steal an expired lease. Returns lease row on success."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        session = self.get_session()
        try:
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO leases (
                            lease_key, owner_id, fencing_token, acquired_at, expires_at, updated_at
                        )
                        VALUES (
                            :lease_key, :owner_id, 1, :now, :expires_at, :now
                        )
                        ON CONFLICT (lease_key)
                        DO UPDATE SET
                            owner_id = :owner_id,
                            fencing_token = leases.fencing_token + 1,
                            acquired_at = :now,
                            expires_at = :expires_at,
                            updated_at = :now
                        WHERE leases.expires_at <= :now OR leases.owner_id = :owner_id
                        RETURNING lease_key, owner_id, fencing_token, acquired_at, expires_at, updated_at
                        """
                    ),
                    {
                        "lease_key": lease_key,
                        "owner_id": owner_id,
                        "now": now,
                        "expires_at": expires_at,
                    },
                )
                .mappings()
                .first()
            )
            if not row:
                session.rollback()
                return None
            session.commit()
            return self._serialize_lease_row(row)
        finally:
            session.close()

    def renew_lease(
        self,
        lease_key: str,
        owner_id: str,
        ttl_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        """Extend a currently held lease. Returns lease row on success."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        session = self.get_session()
        try:
            row = (
                session.execute(
                    text(
                        """
                        UPDATE leases
                        SET expires_at = :expires_at, updated_at = :now
                        WHERE lease_key = :lease_key
                          AND owner_id = :owner_id
                          AND expires_at > :now
                        RETURNING lease_key, owner_id, fencing_token, acquired_at, expires_at, updated_at
                        """
                    ),
                    {
                        "lease_key": lease_key,
                        "owner_id": owner_id,
                        "expires_at": expires_at,
                        "now": now,
                    },
                )
                .mappings()
                .first()
            )
            if not row:
                session.rollback()
                return None
            session.commit()
            return self._serialize_lease_row(row)
        finally:
            session.close()

    def release_lease(self, lease_key: str, owner_id: str) -> bool:
        """Release a lease when owned by caller."""
        session = self.get_session()
        try:
            row = (
                session.execute(
                    text(
                        """
                        DELETE FROM leases
                        WHERE lease_key = :lease_key
                          AND owner_id = :owner_id
                        RETURNING lease_key
                        """
                    ),
                    {
                        "lease_key": lease_key,
                        "owner_id": owner_id,
                    },
                )
                .mappings()
                .first()
            )
            session.commit()
            return bool(row)
        finally:
            session.close()

    def get_lease(self, lease_key: str) -> Optional[Dict[str, Any]]:
        """Get the current lease row for a key."""
        session = self.get_session()
        try:
            row = (
                session.execute(
                    text(
                        """
                        SELECT lease_key, owner_id, fencing_token, acquired_at, expires_at, updated_at
                        FROM leases
                        WHERE lease_key = :lease_key
                        """
                    ),
                    {"lease_key": lease_key},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            return self._serialize_lease_row(row)
        finally:
            session.close()

    def increment_runtime_counter(self, key: str, amount: int = 1) -> int:
        """Increment and return a runtime counter."""
        if amount < 0:
            raise ValueError("Counter increment amount must be non-negative")

        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)
            session.execute(
                text(
                    """
                    INSERT INTO runtime_counters ("key", value, updated_at)
                    VALUES (:key, :amount, :updated_at)
                    ON CONFLICT("key")
                    DO UPDATE SET
                        value = runtime_counters.value + :amount,
                        updated_at = :updated_at
                    """
                ),
                {
                    "key": key,
                    "amount": amount,
                    "updated_at": now,
                },
            )
            session.commit()
            value = session.execute(
                text('SELECT value FROM runtime_counters WHERE "key" = :key'),
                {"key": key},
            ).scalar_one()
            return int(value)
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
