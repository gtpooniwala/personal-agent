from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import deferred, relationship, declarative_base
from datetime import datetime, timezone
import uuid

from backend.runtime import RUN_EVENT_TYPES, RUN_STATUSES

EXTERNAL_TRIGGER_TYPES = ("telegram", "email", "webhook", "generic")
INTEGRATION_CREDENTIAL_STATUSES = ("connected", "expired", "revoked", "error")

Base = declarative_base()


def generate_id():
    """Generate a unique ID for database records."""
    return str(uuid.uuid4())


def utcnow():
    """Timezone-aware UTC timestamp helper (avoids deprecated utcnow())."""
    return datetime.now(timezone.utc)


def _sql_string_literals(values):
    """Render Python string literals for SQL check constraints."""
    return ", ".join(f"'{value}'" for value in values)


class Conversation(Base):
    """Conversation model for storing chat sessions."""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user_id = Column(String, default="default")  # For future multi-user support
    
    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    memory_entries = relationship("MemoryStore", back_populates="conversation", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Message model for storing individual chat messages."""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    
    # Agent-specific fields for transparency
    agent_actions = Column(Text, nullable=True)  # JSON string of agent actions
    token_usage = Column(Integer, nullable=True)
    
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")


class MemoryStore(Base):
    """Memory store for LangChain conversation memory."""
    __tablename__ = "memory_store"
    
    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="memory_entries")


class Document(Base):
    """Document model for storing uploaded documents."""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=generate_id)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False, default="application/pdf")
    upload_date = Column(DateTime(timezone=True), default=utcnow)
    user_id = Column(String, default="default")  # For future multi-user support
    
    # Document processing status
    processed = Column(String, default="pending")  # pending, processing, completed, failed
    total_chunks = Column(Integer, default=0)
    
    # Document summary for context
    summary = Column(Text, nullable=True)  # AI-generated one-sentence summary

    # Binary content stored in DB (eliminates filesystem dependency for Cloud Run).
    # Deferred so PDF bytes are not loaded by queries that only need metadata.
    file_content = deferred(Column(LargeBinary, nullable=True))

    # Relationship to document chunks
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Document chunk model for storing text chunks with embeddings."""
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True, default=generate_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    
    # Vector embeddings (stored as binary data)
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String, default="text-embedding-ada-002")
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    # Relationship to document
    document = relationship("Document", back_populates="chunks")


class RuntimeCounter(Base):
    """Aggregated runtime counters for low-cost local observability."""

    __tablename__ = "runtime_counters"

    key = Column(String, primary_key=True)
    value = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Run(Base):
    """Durable run lifecycle state."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_sql_string_literals(RUN_STATUSES)})",
            name="ck_runs_status_valid",
        ),
        Index("ix_runs_status_created_at", "status", "created_at"),
        Index("ix_runs_conversation_created_at", "conversation_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    status = Column(String, nullable=False)
    error = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="runs")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan")


class RunEvent(Base):
    """Append-only run event log for status and progress updates."""

    __tablename__ = "run_events"
    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_sql_string_literals(RUN_EVENT_TYPES)})",
            name="ck_run_events_type_valid",
        ),
        CheckConstraint(
            f"status IN ({_sql_string_literals(RUN_STATUSES)})",
            name="ck_run_events_status_valid",
        ),
        Index("ix_run_events_run_id_id", "run_id", "id"),
        Index("ix_run_events_status_created_at", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    tool = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    run = relationship("Run", back_populates="events")


class Lease(Base):
    """Distributed-lease table for worker ownership and serialization."""

    __tablename__ = "leases"
    __table_args__ = (
        CheckConstraint("expires_at > acquired_at", name="ck_leases_expiry_after_acquire"),
        Index("ix_leases_expires_at", "expires_at"),
    )

    lease_key = Column(String, primary_key=True)
    owner_id = Column(String, nullable=False)
    fencing_token = Column(Integer, nullable=False, default=1)
    acquired_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ScheduledTask(Base):
    """Cron-scheduled autonomous agent task."""

    __tablename__ = "scheduled_tasks"
    __table_args__ = (
        Index("ix_scheduled_tasks_enabled_next_run_at", "enabled", "next_run_at"),
    )

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, nullable=False, unique=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    cron_expr = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_id = Column(String, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    conversation = relationship("Conversation")


class ExternalTrigger(Base):
    """Registry of configured external triggers."""

    __tablename__ = "external_triggers"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({_sql_string_literals(EXTERNAL_TRIGGER_TYPES)})",
            name="ck_external_triggers_type_valid",
        ),
    )

    id = Column(String, primary_key=True, default=generate_id)
    type = Column(String, nullable=False)  # telegram|email|webhook|generic
    name = Column(String, nullable=False, unique=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    config = Column(Text, nullable=True)  # JSON — bot token, sender filter, etc.
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    conversation = relationship("Conversation")
    events = relationship("TriggerEvent", back_populates="trigger", cascade="all, delete-orphan")


class TriggerEvent(Base):
    """Deduplication log for received trigger events."""

    __tablename__ = "trigger_events"
    __table_args__ = (
        Index(
            "ix_trigger_events_trigger_id_external_event_id",
            "trigger_id",
            "external_event_id",
            unique=True,
        ),
    )

    id = Column(String, primary_key=True, default=generate_id)
    trigger_id = Column(String, ForeignKey("external_triggers.id", ondelete="CASCADE"), nullable=False)
    external_event_id = Column(String, nullable=False)  # Dedupe key from external system
    run_id = Column(String, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    received_at = Column(DateTime(timezone=True), default=utcnow)
    dispatched = Column(Boolean, nullable=False, default=False)

    trigger = relationship("ExternalTrigger", back_populates="events")


class IntegrationCredential(Base):
    """Encrypted per-user credentials for external integrations."""

    __tablename__ = "integration_credentials"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_sql_string_literals(INTEGRATION_CREDENTIAL_STATUSES)})",
            name="ck_integration_credentials_status_valid",
        ),
        Index(
            "ix_integration_credentials_user_provider_kind",
            "user_id",
            "provider",
            "credential_kind",
            unique=True,
        ),
    )

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, nullable=False, default="default")
    provider = Column(String, nullable=False)
    credential_kind = Column(String, nullable=False)
    account_label = Column(String, nullable=True)
    scopes = Column(Text, nullable=True)  # JSON array
    status = Column(String, nullable=False, default="connected")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    ciphertext = Column(Text, nullable=False)
    key_version = Column(String, nullable=False, default="v1")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IntegrationOAuthState(Base):
    """Short-lived OAuth state records for integration connect flows."""

    __tablename__ = "integration_oauth_states"
    __table_args__ = (
        Index("ix_integration_oauth_states_state", "state", unique=True),
        Index("ix_integration_oauth_states_expires_at", "expires_at"),
    )

    id = Column(String, primary_key=True, default=generate_id)
    state = Column(String, nullable=False)
    user_id = Column(String, nullable=False, default="default")
    provider = Column(String, nullable=False)
    return_to = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
