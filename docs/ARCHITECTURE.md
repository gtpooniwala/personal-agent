# Architecture Documentation

## System Overview

The Personal Agent MVP is built on a **modern LangGraph orchestration architecture** that combines the power of graph-based agent execution with intelligent tool selection, providing both fast direct responses and enhanced tool-powered capabilities.

## Core Architecture Principles

### 1. LangGraph-Based Intelligence Routing

```text
User Query → LangGraph Agent → Dynamic Route Decision (Graph-Based)
                                              ↓
        General Knowledge → Direct LLM → Natural Response (Fast)
                                              ↓  
        Computational Task → Tool Execution → Tool-Enhanced Response
```

**Key Innovation**: Graph-based agent execution with automatic tool binding, enabling natural conversation flow and persistent memory management.

## Long-Running Runtime Architecture (Migration Direction)

- **Primary contract**: asynchronous run submission (`POST /runs` and `POST /chat`) plus status/events polling.
- **Execution model**: dedicated worker processing with durable run state and event history.
- **Compatibility**: runtime endpoints are bare routes (`/chat`, `/runs`); non-runtime endpoints remain under `/api/v1`.
- **Ordering model**: first implementation enforces one active run per conversation/session.

This model decouples request acceptance from execution, enables retries/recovery, and prevents single long tool call from blocking the HTTP request lifecycle.

Current implementation:
- async `/chat` and `/runs` runtime with status/events polling is active.
- conversations/tools/documents/health remain served from `/api/v1/*`.

### 2. Component Architecture

```text
┌─────────────────┐    ┌─────────────────────────────────┐    ┌─────────────────┐
│   Frontend      │    │         Backend                 │    │   Database      │
│   (Next.js)     │◄──►│      (FastAPI)                  │◄──►│   (SQLite)      │
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

#### 2. LangGraph Orchestrator System (`backend/orchestrator/`)

**Core Orchestrator (`backend/orchestrator/core.py`)**
- Main `CoreOrchestrator` class implementing LangGraph ReAct pattern
- Modern graph-based agent execution with `create_react_agent()`
- Automatic tool binding and description generation
- Built-in memory management with `MemorySaver()`
- Enhanced conversation persistence and state management

**Tool Registry (`backend/orchestrator/tool_registry.py`)**
- Dynamic tool management with context-aware availability
- Automatic tool discovery and binding
- Pydantic-based tool validation and type safety
- Support for document-dependent tool activation

**Memory System (`backend/orchestrator/core.py` + `backend/database/operations.py`)**
- LangGraph `MemorySaver()` checkpoints for thread-scoped state
- Conversation persistence in SQLite via database operations
- Background summarization to keep context windows manageable

**Tool Modules (`backend/orchestrator/tools/`)**
- `calculator.py`: Mathematical expressions with Pydantic validation
- `time.py`: Date/time queries with structured input handling
- `search_documents.py`: RAG-based document search with context
- `scratchpad.py`: Persistent note-taking across conversations
- `integrations.py`: Framework for Gmail, Calendar, Todoist tools

#### 3. API Layer (`backend/api/`)

**Routes (`backend/api/routes.py`)**
- RESTful API endpoints with full CRUD operations
- Conversation management with passive maintenance
- Document upload and management
- Async runtime submission (`/runs`) with status/events polling
- Async conversational submission endpoint (`/chat`) during migration
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

#### Next.js Application (`frontend/`)
- **Technology**: Next.js + React
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

Migration-target flow (to be finalized during runtime implementation):

```text
User Input → Frontend → POST /runs → Worker Queue → Agent Processing → Tool Execution → Persisted Message
                                   ↓                        ↓
                          Status/Events API       Database Storage ← Memory Update
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
- Dedicated worker runtime for non-blocking operations
- Run-state persistence for restart-safe behavior
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
