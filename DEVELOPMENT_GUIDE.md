# Personal Agent MVP - Development Guide

## 🎯 Development Overview

This guide provides comprehensive instructions for developers who want to extend, modify, or deploy the Personal Agent MVP. The system is designed for scalability from local development to cloud deployment and from single-user to multi-user environments.

## 🏗️ Architecture Deep Dive

### System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (HTML/JS)     │◄──►│   (FastAPI)     │◄──►│   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   LangChain     │
                    │   Agent         │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   External      │
                    │   Services      │
                    │   (OpenAI, etc) │
                    └─────────────────┘
```

### Key Components

1. **FastAPI Backend** (`backend/main.py`)
   - Async HTTP server with CORS support
   - RESTful API with automatic documentation
   - Environment-based configuration

2. **LangChain Agent** (`backend/agent/core.py`)
   - ReAct pattern implementation
   - Tool registry and execution
   - Conversation memory management

3. **Database Layer** (`backend/database/`)
   - SQLAlchemy ORM models
   - Database operations abstraction
   - Migration-ready design

4. **Tool System** (`backend/agent/tools.py`)
   - Extensible tool registry
   - Built-in tools (calculator, time)
   - Placeholder for external services

## 🛠️ Development Setup

### Environment Setup

```bash
# Activate the development environment
conda activate personalagent

# Install additional development dependencies
pip install pytest black flake8 mypy

# Set development environment
export ENVIRONMENT=development
```

### IDE Configuration

Recommended VS Code extensions:
- Python
- Pylance
- Black Formatter
- REST Client (for API testing)

### Code Style

The project follows Python standards:
- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking

```bash
# Format code
black backend/

# Lint code
flake8 backend/

# Type checking
mypy backend/
```

## 🔧 Adding New Features

### 1. Adding New Tools

Tools are the primary way to extend the agent's capabilities. Here's how to add a new tool:

#### Example: Weather Tool

```python
# In backend/agent/tools.py

class WeatherTool(BaseTool):
    """Get current weather information."""
    
    name = "weather"
    description = "Get weather information for a location. Input should be a city name."
    
    def _run(self, query: str) -> str:
        """Get weather for the specified location."""
        # Implement weather API integration
        # For now, return placeholder
        return f"Weather for {query}: Sunny, 72°F"
    
    async def _arun(self, query: str) -> str:
        return self._run(query)

# Add to ToolRegistry._initialize_tools()
def _initialize_tools(self):
    # ...existing tools...
    self._tools["weather"] = WeatherTool()
```

#### Tool Development Guidelines

1. **Inherit from BaseTool**: All tools must inherit from LangChain's BaseTool
2. **Define name and description**: Clear, descriptive names help the agent choose tools
3. **Implement _run method**: Synchronous execution
4. **Implement _arun method**: Asynchronous execution (can call _run if no async needed)
5. **Error handling**: Wrap API calls in try/catch blocks
6. **Add to registry**: Register the tool in ToolRegistry

### 2. External Service Integration

For production-ready integrations with Gmail, Calendar, and Todoist:

#### Gmail Integration Example

```python
# backend/agent/services/gmail.py

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class GmailService:
    def __init__(self, user_credentials):
        self.service = build('gmail', 'v1', credentials=user_credentials)
    
    def search_emails(self, query: str, max_results: int = 10):
        """Search emails matching the query."""
        try:
            results = self.service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()
            return results.get('messages', [])
        except Exception as e:
            return {"error": str(e)}

# Update GmailTool in tools.py
class GmailTool(BaseTool):
    name = "gmail_search"
    description = "Search Gmail emails. Query can include sender, subject, date filters."
    
    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id
        # Initialize with user credentials
        self.gmail_service = GmailService(self._get_user_credentials())
    
    def _run(self, query: str) -> str:
        results = self.gmail_service.search_emails(query)
        return self._format_email_results(results)
```

### 3. Database Schema Changes

When adding new features that require database changes:

#### 1. Update Models (`backend/database/models.py`)

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, unique=True)
    preferences = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 2. Add Database Operations (`backend/database/operations.py`)

```python
def create_user_profile(user_id: str, preferences: dict) -> str:
    """Create a new user profile."""
    profile = UserProfile(
        user_id=user_id,
        preferences=json.dumps(preferences)
    )
    db.add(profile)
    db.commit()
    return profile.id
```

#### 3. Create Migration Script

```python
# backend/migrations/add_user_profiles.py

def upgrade():
    """Add user_profiles table."""
    # SQLAlchemy migration code
    pass

def downgrade():
    """Remove user_profiles table."""
    # Rollback code
    pass
```

### 4. API Endpoint Development

Adding new API endpoints:

#### 1. Define Pydantic Models (`backend/api/models.py`)

```python
class UserPreferencesRequest(BaseModel):
    timezone: str
    language: str = "en"
    email_notifications: bool = True

class UserPreferencesResponse(BaseModel):
    user_id: str
    preferences: UserPreferencesRequest
    updated_at: datetime
```

#### 2. Implement Route (`backend/api/routes.py`)

```python
@router.post("/users/{user_id}/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    user_id: str,
    preferences: UserPreferencesRequest
):
    """Update user preferences."""
    try:
        profile_id = db_ops.update_user_preferences(user_id, preferences.dict())
        return UserPreferencesResponse(
            user_id=user_id,
            preferences=preferences,
            updated_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 🌐 Cloud Deployment

### 1. Environment Configuration

For production deployment, update configuration:

```python
# backend/config/settings.py

class ProductionSettings(BaseSettings):
    environment: str = "production"
    database_url: str  # PostgreSQL connection string
    redis_url: str     # Redis for caching
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Security
    secret_key: str
    cors_origins: List[str] = ["https://yourdomain.com"]
    
    # External services
    openai_api_key: str
    gmail_client_id: str
    gmail_client_secret: str
```

### 2. Database Migration

For production, migrate from SQLite to PostgreSQL:

```python
# backend/config/database.py

def get_database_url():
    if settings.environment == "production":
        return settings.database_url  # PostgreSQL
    else:
        return f"sqlite:///{settings.database_path}"  # SQLite

engine = create_engine(get_database_url())
```

### 3. Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/personal_agent
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: personal_agent
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 4. Cloud Platform Deployment

#### AWS Deployment
- **EC2**: Docker containers on EC2 instances
- **ECS**: Container orchestration
- **RDS**: Managed PostgreSQL database
- **ElastiCache**: Redis for caching

#### Google Cloud Platform
- **Cloud Run**: Serverless container deployment
- **Cloud SQL**: Managed PostgreSQL
- **Cloud Storage**: File storage

#### Azure
- **Container Instances**: Docker deployment
- **Azure Database**: Managed PostgreSQL
- **Azure Storage**: File storage

## 🔐 Security Implementation

### 1. Authentication & Authorization

```python
# backend/auth/jwt_auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

def get_current_user(token: str = Depends(security)):
    """Verify JWT token and return user info."""
    try:
        payload = jwt.decode(token.credentials, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Use in routes
@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    # User is authenticated
    pass
```

### 2. API Rate Limiting

```python
# backend/middleware/rate_limit.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    # Rate limited endpoint
    pass
```

## 🧪 Testing

### Unit Tests

```python
# tests/test_tools.py

import pytest
from backend.agent.tools import CalculatorTool

def test_calculator_basic():
    calc = CalculatorTool()
    result = calc._run("5 + 3")
    assert "8" in result

def test_calculator_error_handling():
    calc = CalculatorTool()
    result = calc._run("invalid expression")
    assert "Error" in result
```

### Integration Tests

```python
# tests/test_api.py

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_chat_endpoint():
    response = client.post(
        "/api/v1/chat",
        json={"message": "What is 2 + 2?"}
    )
    assert response.status_code == 200
    assert "4" in response.json()["response"]
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=backend tests/

# Run specific test file
pytest tests/test_tools.py -v
```

## 📈 Monitoring & Analytics

### 1. Application Monitoring

```python
# backend/monitoring/metrics.py

from prometheus_client import Counter, Histogram, generate_latest
import time

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_DURATION.observe(process_time)
    
    return response
```

### 2. Logging

```python
# backend/config/logging.py

import structlog

logger = structlog.get_logger()

# Usage in code
logger.info("Chat request received", user_id=user_id, message_length=len(message))
logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
```

## 🚀 Future Development Roadmap

### Phase 1: Core Enhancements (Immediate - 2-4 weeks)

#### 1. Tool Execution Reliability
- **Priority**: High
- **Effort**: Medium
- **Tasks**:
  - Debug current tool execution inconsistencies
  - Improve LangChain agent configuration
  - Add tool execution retry logic
  - Enhance error handling and recovery

#### 2. Conversation Memory Enhancement
- **Priority**: High
- **Effort**: Medium
- **Tasks**:
  - Improve context retrieval from database
  - Implement conversation summarization for long histories
  - Add conversation search functionality
  - Optimize memory loading performance

#### 3. User Interface Improvements
- **Priority**: Medium
- **Effort**: Low
- **Tasks**:
  - Add conversation sidebar with history
  - Implement conversation renaming
  - Add message timestamps
  - Improve mobile responsiveness

### Phase 2: External Integrations (1-2 months)

#### 1. Gmail Integration
- **Priority**: High
- **Effort**: High
- **Tasks**:
  - OAuth 2.0 authentication flow
  - Gmail API integration
  - Email search and reading capabilities
  - Email composition and sending
  - Email organization and labeling

**Technical Implementation**:
```python
# Example Gmail tool capabilities
- "Show me emails from John from last week"
- "Compose an email to team@company.com about the meeting"
- "Archive all promotional emails"
- "Set up a filter for newsletter emails"
```

#### 2. Google Calendar Integration
- **Priority**: High
- **Effort**: High
- **Tasks**:
  - Calendar API authentication
  - Event viewing and creation
  - Meeting scheduling
  - Calendar conflict detection
  - Reminder management

**Technical Implementation**:
```python
# Example Calendar tool capabilities
- "Schedule a meeting with Sarah tomorrow at 2 PM"
- "What's on my calendar for next week?"
- "Find a free 1-hour slot this week for a team meeting"
- "Reschedule my 3 PM meeting to 4 PM"
```

#### 3. Todoist Integration
- **Priority**: Medium
- **Effort**: Medium
- **Tasks**:
  - Todoist API integration
  - Task creation and management
  - Project organization
  - Due date and priority handling
  - Productivity analytics

**Technical Implementation**:
```python
# Example Todoist tool capabilities
- "Add 'Buy groceries' to my personal project"
- "Show me all tasks due today"
- "Mark 'Finish report' as completed"
- "Create a task to call the dentist with high priority"
```

### Phase 3: Multi-User & Cloud (2-3 months)

#### 1. User Authentication System
- **Priority**: High
- **Effort**: High
- **Tasks**:
  - JWT-based authentication
  - User registration and login
  - OAuth social login (Google, GitHub)
  - User profile management
  - Password reset functionality

#### 2. Multi-Tenant Architecture
- **Priority**: High
- **Effort**: High
- **Tasks**:
  - User data isolation
  - Per-user conversation history
  - User-specific tool configurations
  - Resource usage tracking
  - Billing and usage analytics

#### 3. Cloud Deployment
- **Priority**: High
- **Effort**: Medium
- **Tasks**:
  - PostgreSQL database migration
  - Redis for caching and sessions
  - Container orchestration (Docker/Kubernetes)
  - Load balancing and auto-scaling
  - CI/CD pipeline setup

### Phase 4: Advanced Features (3-6 months)

#### 1. Advanced AI Capabilities
- **Priority**: Medium
- **Effort**: High
- **Tasks**:
  - RAG (Retrieval Augmented Generation) for document search
  - Custom knowledge base integration
  - Multi-modal support (images, documents)
  - Voice interface integration
  - Conversation summarization and insights

#### 2. Workflow Automation
- **Priority**: Medium
- **Effort**: High
- **Tasks**:
  - IFTTT-style automation rules
  - Scheduled tasks and reminders
  - Cross-service workflows
  - Custom automation scripting
  - Trigger-based actions

#### 3. Analytics & Insights
- **Priority**: Medium
- **Effort**: Medium
- **Tasks**:
  - User behavior analytics
  - Productivity insights
  - Usage patterns and recommendations
  - Performance optimization suggestions
  - Custom dashboard creation

### Phase 5: Enterprise Features (6+ months)

#### 1. Team Collaboration
- **Priority**: Low
- **Effort**: High
- **Tasks**:
  - Shared conversations
  - Team workspaces
  - Role-based access control
  - Collaboration tools integration
  - Team analytics

#### 2. Advanced Security
- **Priority**: High (for enterprise)
- **Effort**: Medium
- **Tasks**:
  - End-to-end encryption
  - Audit logging
  - Compliance frameworks (SOC2, GDPR)
  - Data retention policies
  - Security monitoring

#### 3. API & Integrations
- **Priority**: Medium
- **Effort**: Medium
- **Tasks**:
  - Public API for third-party integrations
  - Webhook support
  - Plugin system
  - Marketplace for custom tools
  - Developer documentation and SDKs

## 🎯 Immediate Next Steps (This Week)

### Priority 1: Fix Tool Execution
```bash
# Debug agent tool execution
# File: backend/agent/core.py
# Issue: Tools not executing consistently
# Solution: Review LangChain agent configuration
```

### Priority 2: Enhance Conversation Memory
```bash
# Improve memory retrieval
# File: backend/agent/memory.py
# Issue: Context not always loaded properly
# Solution: Debug load_memory_variables method
```

### Priority 3: Add Development Tooling
```bash
# Set up development tools
pip install pytest black flake8 mypy
black backend/
flake8 backend/
pytest tests/
```

### Priority 4: Create Test Suite
```bash
# File: tests/test_basic_functionality.py
# Test all current features
# Ensure regression testing
```

## 📚 Development Resources

### Documentation
- [LangChain Documentation](https://python.langchain.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

### Code Quality Tools
- **Black**: Code formatting
- **Flake8**: Linting
- **MyPy**: Type checking
- **Pytest**: Testing framework

### Monitoring & Debugging
- **Structlog**: Structured logging
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards
- **Sentry**: Error tracking

---

*This development guide is a living document. Update it as the project evolves and new requirements emerge.*
