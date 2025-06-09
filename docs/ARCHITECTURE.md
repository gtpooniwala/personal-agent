# Architecture Documentation

## System Overview

The Personal Agent MVP is built on a **hybrid intelligence routing architecture** that combines the power of LangChain agents with intelligent tool selection, providing both fast direct responses and enhanced tool-powered capabilities.

## Core Architecture Principles

### 1. Hybrid Intelligence Routing

```text
User Query → LangChain Agent Intelligence → Dynamic Route Decision
                                                    ↓
        General Knowledge → Direct LLM → Natural Response (Fast)
                                                    ↓  
        Computational Task → Agent + Tools → Tool-Enhanced Response
```

**Key Innovation**: Agent-driven tool selection rather than hardcoded rules, allowing natural conversation flow and context-aware tool usage.

### 2. Component Architecture

```text
┌─────────────────┐    ┌─────────────────────────────────┐    ┌─────────────────┐
│   Frontend      │    │         Backend                 │    │   Database      │
│   (HTML/JS)     │◄──►│      (FastAPI)                  │◄──►│   (SQLite)      │
│                 │    │                                 │    │                 │
│ • Chat UI       │    │  ┌─────────────────────────────┐ │    │ • Conversations │
│ • Tool Display  │    │  │    HYBRID INTELLIGENCE      │ │    │ • Messages      │
│ • History       │    │  │     ROUTING LAYER           │ │    │ • Tool Usage    │
│ • Doc Mgmt      │    │  │                             │ │    │ • Documents     │
└─────────────────┘    │  │  ┌─────────────────────────┐ │ │    │ • Embeddings    │
                       │  │  │   LangChain Agent       │ │ │    └─────────────────┘
                       │  │  │   (ReAct Pattern)       │ │ │
                       │  │  │                         │ │ │
                       │  │  │ • Analyzes user input   │ │ │
                       │  │  │ • Decides tool usage    │ │ │
                       │  │  │ • Manages conversation  │ │ │
                       │  │  │ • Executes reasoning    │ │ │
                       │  │  └─────────────────────────┘ │ │
                       │  │              │               │ │
                       │  │              ▼               │ │
                       │  │  ┌─────────────────────────┐ │ │
                       │  │  │    Tool Registry        │ │ │
                       │  │  │                         │ │ │
                       │  │  │ • Calculator Tool       │ │ │
                       │  │  │ • Time Tool             │ │ │
                       │  │  │ • Document Search       │ │ │
                       │  │  │ • Future: Gmail, etc.   │ │ │
                       │  │  └─────────────────────────┘ │ │
                       │  └─────────────────────────────┐ │ │
                       └─────────────────────────────────┘ │
                                        │                   │
                                        ▼                   │
                              ┌─────────────────┐           │
                              │   OpenAI GPT    │           │
                              │   External API  │           │
                              └─────────────────┘           │
```

## Technical Stack

### Backend Components

#### 1. FastAPI Application (`backend/main.py`)
- **Purpose**: ASGI web server with automatic OpenAPI documentation
- **Features**: CORS middleware, lifespan management, static file serving
- **Configuration**: Environment-based settings with Pydantic

#### 2. LangChain Agent System (`backend/agent/`)

**Core Agent (`backend/agent/core.py`)**
- Main `PersonalAgent` class implementing ReAct pattern
- Smart routing logic (agent-driven, not hardcoded)
- Conversation management and persistent memory
- Token tracking and cost monitoring
- Graceful fallback from agent to direct LLM

**Memory System (`backend/agent/memory.py`)**
- Custom SQLite-backed LangChain memory
- Extends `ConversationBufferMemory`
- Persistent conversation context across sessions
- Integrates with database operations

**Tool Registry (`backend/agent/tools.py`)**
- `CalculatorTool`: Mathematical expressions with exponentiation
- `CurrentTimeTool`: Date/time queries with natural language processing
- `ToolRegistry`: Manages available tools dynamically
- Placeholder frameworks for Gmail, Calendar, Todoist

#### 3. API Layer (`backend/api/`)

**Routes (`backend/api/routes.py`)**
- RESTful API endpoints with full CRUD operations
- Conversation management with passive maintenance
- Document upload and management
- Real-time chat processing
- Health checks and tool listing

**Models (`backend/api/models.py`)**
- Pydantic request/response schemas
- Type validation and automatic documentation
- Consistent API contract

#### 4. Database Layer (`backend/database/`)

**Models (`backend/database/models.py`)**
- SQLAlchemy ORM models
- Relationships: Conversations → Messages → Memory entries
- Document storage with chunk relationships
- Auto-generating UUIDs and timestamps

**Operations (`backend/database/operations.py`)**
- Abstraction layer for database interactions
- Thread-safe operations for concurrent access
- CRUD operations with proper transaction handling
- Conversation maintenance utilities

#### 5. Document Processing (`backend/services/`)

**Document Service (`backend/services/document_service.py`)**
- PDF processing and text extraction
- Vector embedding generation with OpenAI
- Chunking strategy for optimal retrieval
- RAG (Retrieval Augmented Generation) implementation

### Frontend Architecture

#### Single-Page Application (`frontend/index.html`)
- **Technology**: Vanilla HTML5, CSS3, JavaScript ES6+
- **Design**: Responsive layout with sidebar navigation
- **Features**: 
  - Real-time chat interface
  - Document upload and management
  - Tool usage visualization
  - Conversation history management
  - RAG controls and document selection

**Key Frontend Components:**
- Chat container with message rendering
- Conversation sidebar with automatic title display
- Document management panel with upload/selection
- Professional tool action display
- Real-time status indicators

## Data Flow

### 1. Message Processing Flow

```text
User Input → Frontend → API → Agent Processing → Tool Execution → Response
                                    ↓
                            Database Storage ← Memory Update
```

### 2. Document Q&A Flow

```text
Document Upload → PDF Processing → Text Extraction → Chunking → Embedding Generation → Vector Storage
                                                                          ↓
User Query → Document Selection → Vector Search → Context Retrieval → Agent + RAG → Response
```

### 3. Conversation Maintenance Flow

```text
Load Conversations → Maintenance Check → Title Generation (Async) → Empty Cleanup (Async)
                                              ↓                           ↓
                                      Update Database              Delete Old Conversations
```

## Security Considerations

### 1. Input Validation
- Pydantic models for request validation
- File type and size restrictions for uploads
- SQL injection prevention through ORM

### 2. API Security
- CORS configuration for cross-origin requests
- Request size limits
- Error handling without information leakage

### 3. Data Storage
- Local SQLite database (no external dependencies)
- File uploads stored in controlled directory
- No sensitive data in logs

## Performance Characteristics

### 1. Response Times
- Direct LLM responses: 1-2 seconds
- Agent with tools: 2-4 seconds
- Document uploads: 5-15 seconds (processing)
- Vector search: <100ms

### 2. Token Optimization
- Smart routing reduces unnecessary API calls by ~60%
- Conversation memory limits prevent token overflow
- Efficient prompt engineering for tool selection

### 3. Scalability Considerations
- SQLite suitable for single-user deployment
- Async processing for non-blocking operations
- Modular design allows easy component scaling

## Future Architecture Enhancements

### 1. Multi-User Support
- Database migration to PostgreSQL
- User authentication and authorization
- Tenant isolation for conversations and documents

### 2. Cloud Deployment
- Containerization with Docker
- Horizontal scaling with load balancers
- External vector database (Pinecone, Weaviate)

### 3. Advanced Features
- Real-time collaboration
- Advanced memory and learning systems
- Plugin architecture for third-party integrations

---

This architecture provides a solid foundation for building sophisticated AI assistants while maintaining simplicity, performance, and extensibility.
