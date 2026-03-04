from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


def generate_id():
    """Generate a unique ID for database records."""
    return str(uuid.uuid4())


class Conversation(Base):
    """Conversation model for storing chat sessions."""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String, default="default")  # For future multi-user support
    
    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    memory_entries = relationship("MemoryStore", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Message model for storing individual chat messages."""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
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
    timestamp = Column(DateTime, default=datetime.utcnow)
    
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
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, default="default")  # For future multi-user support
    
    # Document processing status
    processed = Column(String, default="pending")  # pending, processing, completed, failed
    total_chunks = Column(Integer, default=0)
    
    # Document summary for context
    summary = Column(Text, nullable=True)  # AI-generated one-sentence summary
    
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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to document
    document = relationship("Document", back_populates="chunks")
