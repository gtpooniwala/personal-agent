# Personal Agent MVP

A sophisticated AI-powered personal assistant built with FastAPI, LangGraph, and an intelligent orchestrator architecture. The system features modular tool delegation, automatic conversation management, document Q&A capabilities, and a clean web interface.

## ✨ Key Features

- **🎼 Orchestrator Architecture**: Centralized `CoreOrchestrator` that intelligently delegates to specialized tools/agents
- **🔧 Modular Tool System**: Dynamic tool registry with easy addition/removal of capabilities
- **📄 Document Q&A**: Upload PDFs and ask questions using RAG (Retrieval Augmented Generation)
- **💬 Smart Conversations**: Automatic title generation and conversation cleanup
- **🌐 Web Interface**: Clean, responsive chat interface with document management
- **🔄 Passive Maintenance**: Backend-driven conversation organization
- **⚙️ Scalable Design**: Adding new tools only requires implementing the tool and updating orchestrator prompts
- **🧠 LangGraph Architecture**: Modern graph-based orchestration with persistent memory and automatic tool binding

## 🆕 Recent Major Improvements

- **Gmail Tool Expanded**: Gmail integration now supports advanced search, filtering, and multi-email results using Gmail's full search syntax.
- **Frontend Refactor**: Modular JavaScript, improved sidebar, and real-time conversation highlighting for a modern UI/UX.
- **Long-Term Memory/Profile**: Robust user profile memory tool with LLM-powered merging and persistent storage.
- **Internet Search Tool**: Modular search with provider selection (DuckDuckGo, Bing, Google, SerpAPI).
- **LangGraph Upgrade**: Modern agent orchestration, automatic tool binding, and enhanced memory management.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Conda (recommended)
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/gtpooniwala/personal-agent.git
   cd personal-agent
   ```

2. **Set up environment**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Configure environment**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env and add your OpenAI API key
   ```

4. **Start the server**
   ```bash
   ./start_server.sh
   ```

5. **Open the interface**
   - Backend API: http://127.0.0.1:8000
   - Web Interface: Open `frontend/index.html` in your browser
   - API Documentation: http://127.0.0.1:8000/docs

## 🎯 Usage

### Basic Chat
- Start typing in the web interface
- The agent automatically decides when to use tools
- Conversations are automatically titled and organized

### Document Q&A
1. Upload PDF documents using the right sidebar
2. Enable "Smart Search" 
3. Select documents to include in your queries
4. Ask questions about your documents

### Tool System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          LANGGRAPH ORCHESTRATOR                                │
│                         (Modern Graph-Based Hub)                               │
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐            │
│  │  Tool Registry  │    │  LangGraph      │    │ Memory Manager  │            │
│  │  (Dynamic)      │◄──►│  Agent          │◄──►│  (MemorySaver)  │            │
│  └─────────────────┘    │ (ReAct Pattern) │    └─────────────────┘            │
│                          │ Auto Tool Bind  │                                   │
│                          └─────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                │           TOOL EXECUTION          │
                └─────────────────┬─────────────────┘
                                  │
    ┌─────────────┬───────────────┼───────────────┬─────────────┬─────────────┬─────────────┐
    │             │               │               │             │             │             │
    ▼             ▼               ▼               ▼             ▼             ▼             ▼
┌─────────┐ ┌─────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│Calculator│ │  Time   │ │ Document Q&A │ │ Scratchpad  │ │    Gmail    │ │  Calendar   │ │  Todoist    │
│  Tool    │ │  Tool   │ │    Tool      │ │    Tool     │ │    Tool     │ │    Tool     │ │    Tool     │
│    ✅    │ │    ✅    │ │      ✅       │ │     ✅      │ │     🚧      │ │     🚧      │ │     🚧      │
│IMPLEMENTED│ │IMPLEMENTED│ │ IMPLEMENTED  │ │IMPLEMENTED  │ │ IMPLEMENTED │ │ PLACEHOLDER │ │ PLACEHOLDER │
└─────────┘ └─────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### Tool Inventory & Status

#### ✅ **Implemented Tools** (Production Ready)

**1. Calculator Tool**
- **Status**: ✅ Fully Implemented
- **Purpose**: Mathematical expressions and calculations
- **Features**: 
  - Secure expression evaluation (`^` → `**` conversion)
  - Input validation for security
  - Support for basic arithmetic and exponentiation
- **Usage**: "What is 2^4?", "Calculate 364 * 3"
- **Availability**: Always available

**2. Time Tool**
- **Status**: ✅ Fully Implemented  
- **Purpose**: Date and time information
- **Features**:
  - Current time/date in multiple formats
  - Natural language processing for time queries
  - Timezone-aware responses
- **Usage**: "What time is it?", "What's today's date?"
- **Availability**: Always available

**3. Document Q&A Tool**
- **Status**: ✅ Fully Implemented
- **Purpose**: RAG-based search through uploaded PDF documents
- **Features**:
  - Vector embeddings (OpenAI text-embedding-ada-002)
  - Semantic search with relevance scoring
  - Multi-document search capabilities
  - Source attribution and context
- **Usage**: "What does my contract say about termination?"
- **Availability**: Context-dependent (only when documents are selected)

**4. Scratchpad Tool**
- **Status**: ✅ Fully Implemented
- **Purpose**: Persistent note-taking and information storage across conversations
- **Features**:
  - Save and retrieve notes across sessions
  - Search through saved notes
  - Delete specific notes or clear all
  - User-specific note storage
- **Usage**: "Save a note that I need to call the dentist", "Show my notes", "Search for dentist"
- **Availability**: Always available

**5. Gmail Tool**
- **Status**: ✅ Expanded Implementation
- **Purpose**: Search, filter, and read emails from Gmail inbox
- **Features**:
  - OAuth authentication
  - Full Gmail search syntax support (by sender, subject, date, label, etc.)
  - Fetch multiple emails with sender, subject, date, and snippet
- **Usage**: "Show emails from Alice last week", "Find unread messages with 'invoice' in the subject"
- **Availability**: Requires Gmail setup

**6. User Profile Tool**
- **Status**: ✅ Fully Implemented
- **Purpose**: Persistent, user-specific memory (facts, preferences, background)
- **Features**:
  - Read/update user profile with natural language instructions
  - LLM-powered profile extraction and merging
  - Used for personalization and long-term memory
- **Usage**: "Remember my favorite color is blue", "What do you know about me?"
- **Availability**: Always available

**7. Response Agent Tool**
- **Status**: ✅ Fully Implemented
- **Purpose**: Synthesizes the final user-facing response from tool results and conversation history
- **Features**:
  - Integrates tool outputs into a single, natural response
  - Avoids technical jargon/tool names in user answers
- **Usage**: Internal orchestration step
- **Availability**: Always available

#### 🚧 **Placeholder Tools** (Framework Ready)

**8. Gmail Read Tool**
- **Status**: 🚧 Basic Implementation (Read only)
- **Purpose**: Fetches the most recent email from the user's Gmail inbox
- **Features**:
  - OAuth authentication
  - Returns sender, subject, snippet, and date
- **Usage**: "Show my latest email"
- **Availability**: Requires Gmail setup

**9. Calendar, Todoist (Full Integrations)**
- **Status**: 🚧 Placeholder
- **Purpose**: Email, calendar, and task management
- **Planned Features**: See AGENT.md and docs/features for details

### Information Flow Architecture

The orchestrator operates as an **iterative, cyclical state machine**—not a simple linear pipeline. Each user request triggers a loop where the system repeatedly analyzes state, decides on actions, executes tools, and updates context until a final response is ready.

#### **State Flow Diagram**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR STATE                                │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ 1. Analyze user input, context, and memory                               │ │
│ │ 2. Decide: Is a tool/action needed?                                      │ │
│ │ 3. If yes, select tool(s) and prepare input                              │ │
│ │ 4. Execute tool(s) and collect result(s)                                 │ │
│ │ 5. Update state with new info, tool outputs, and conversation context     │ │
│ │ 6. Decide: Is another tool/action needed?                                │ │
│ │    └─► If yes, repeat from step 3 (loop)                                 │ │
│ │    └─► If no, proceed to response synthesis                              │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RESPONSE SYNTHESIS (AGENT)                           │
│   - Integrate tool results, memory, and conversation context                │
│   - Generate final user-facing response                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER RESPONSE                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key Points:**

- The orchestrator **loops** through state analysis and tool execution as many times as needed, not just once.
- Each cycle can update memory, context, and available tools.
- The process ends only when the orchestrator determines that no further tool actions are needed and a final response can be synthesized.
- This enables complex, multi-step reasoning and tool chaining within a single user request.

**Example Flow:**

1. User asks: "Summarize my latest email and add a note about it."
2. Orchestrator fetches latest email (Gmail tool), then loops to invoke the Scratchpad tool to save a note, then loops again to synthesize a final response.
3. Each step updates the state, and the loop continues until all actions are complete.

This cyclical, state-driven approach is what enables advanced, multi-tool workflows and dynamic reasoning in the agent.

## 🏗️ Architecture

The system uses a **modular orchestrator architecture** designed for scalability:

### Core Components

- **CoreOrchestrator**: Central decision-making component that analyzes user requests and delegates to appropriate tools
- **ToolRegistry**: Dynamic registry system for managing available tools and their availability contexts
- **Specialized Tools**: Individual tool modules for specific capabilities (calculator, time, document Q&A, etc.)
- **Memory System**: Conversation persistence and context management
- **API Layer**: FastAPI-based REST API with automatic route handling

### Orchestrator Design

The `CoreOrchestrator` serves as the intelligent hub that:
- Analyzes incoming user requests
- Determines which tools (if any) are needed
- Delegates tasks to appropriate specialized tools
- Manages conversation flow and context
- Handles error scenarios gracefully

### Adding New Tools

The architecture is designed for easy expansion:
1. Create a new tool module in `backend/orchestrator/tools/`
2. Implement the tool class with proper documentation
3. Register the tool in the `ToolRegistry`
4. Update orchestrator prompts if needed
5. The tool becomes immediately available

### Technology Stack

- **Backend**: FastAPI with LangChain orchestrator system
- **Frontend**: Single-page HTML/CSS/JavaScript application  
- **Database**: SQLite for conversations, messages, and documents
- **AI**: OpenAI GPT models with intelligent tool routing
- **Documents**: Vector embeddings for semantic search

## 📁 Project Structure

```text
personal-agent/
├── README.md                 # This file - User documentation
├── AGENT.md                 # Technical documentation for AI agents/developers
├── backend/                 # FastAPI backend with orchestrator architecture
│   ├── main.py             # Application entry point
│   ├── test_comprehensive.py # Main test suite (moved for easy access)
│   ├── test_imports.py     # Environment validation test
│   ├── orchestrator/       # 🎯 Core orchestrator architecture
│   │   ├── core.py         # CoreOrchestrator - main decision maker
│   │   ├── tool_registry.py # Dynamic tool management system
│   │   ├── memory.py       # Conversation memory system
│   │   └── tools/          # Individual specialized tool modules
│   │       ├── calculator.py    # ✅ Mathematical calculations
│   │       ├── time.py          # ✅ Date/time queries  
│   │       ├── search_documents.py # ✅ RAG-based document search
│   │       ├── scratchpad.py    # ✅ Persistent note-taking tool
│   │       └── integrations.py  # 🚧 Gmail, Calendar, Todoist placeholders
│   ├── agent/              # Legacy agent system (compatibility)
│   │   ├── core.py         # PersonalAgent class
│   │   ├── tools.py        # Original tool implementations
│   │   └── memory.py       # SQLite conversation memory
│   ├── api/                # FastAPI routes and models
│   │   ├── routes.py       # API endpoints using orchestrator
│   │   └── models.py       # Pydantic request/response schemas
│   ├── services/           # External service integrations
│   │   └── document_service.py # PDF processing & vector search
│   ├── database/           # Data persistence layer
│   │   ├── models.py       # SQLAlchemy table definitions
│   │   └── operations.py   # Database abstraction layer
│   ├── config/             # Configuration management
│   └── data/               # Runtime data storage
│       ├── agent.db        # SQLite database
│       └── uploads/        # Document uploads directory
├── frontend/               # Web interface
│   └── index.html          # Single-page chat application with document management
├── docs/                   # Comprehensive documentation
│   ├── API.md             # API reference documentation
│   ├── ARCHITECTURE.md    # System architecture details
│   ├── SETUP.md          # Installation and setup guide
│   └── features/         # Feature-specific documentation
└── tests/                 # Test infrastructure
    └── backend/tests/     # Backend test files
```

**Key Architecture Notes**:
- 🎯 **`orchestrator/`**: New modular architecture with tool delegation
- ✅ **Implemented Tools**: calculator, time, document_qa, scratchpad
- 🚧 **Placeholder Tools**: gmail, calendar, todoist (framework ready)
- 🔄 **`agent/`**: Legacy system maintained for compatibility

## 🔧 Development

For detailed development information, see:
- [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md) - Development workflow
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Technical architecture
- [`docs/API.md`](docs/API.md) - API documentation
- [`AGENT.md`](AGENT.md) - Technical documentation for AI agents

## 📊 System Status

**✅ Production Ready Features:**
- Modular orchestrator architecture with CoreOrchestrator
- Dynamic tool registry with context-dependent availability
- Mathematical calculations and time queries via specialized tools
- Document upload and Q&A with RAG using dedicated tool
- Persistent scratchpad for note-taking across conversations
- Conversation management with automatic titles
- Professional web interface with seamless orchestrator integration
- Comprehensive error handling and tool delegation
- Backward compatibility layer for smooth migration

**🚧 Future Enhancements:**
- Gmail, Calendar, and Todoist integration tools (structure ready)
- Multi-user support with role-based orchestration
- Cloud deployment with distributed orchestrator
- Advanced memory and learning capabilities
- Additional specialized tools (weather, news, web search, etc.)

## 📋 Development Roadmap & TODOs

### 🔧 **New Tools (High Priority)**

#### Core Productivity Tools
- [x] **Scratchpad Tool**: Persistent note-taking and information storage across conversations ✅ **COMPLETED**
- [x] **Internet Search Tool**: Web search capabilities with result summarization ✅ **COMPLETED**
- [ ] **Gmail Tool**: Complete email management (reading, sending, organizing)
- [ ] **Calendar Tool**: Full calendar integration with scheduling intelligence
- [ ] **Todoist Tool**: Advanced task and project management
- [ ] **Notion Tool**: Search through notion docs

#### Additional Tool Ideas  

- [ ] **Response Agent**: Dedicated agent for improving response quality, style, and tone
- [ ] **Weather Tool**: Current conditions and forecasts
- [ ] **News Tool**: Curated news summaries and updates
- [ ] **File Management Tool**: Local file operations and organization
- [ ] **Code Execution Tool**: Safe code running in sandboxed environment
- [ ] **Translation Tool**: Multi-language translation capabilities
- [ ] **Web Scraper Tool**: Extract content from web pages for analysis
- [ ] **QR Code Generator**: Generate QR codes for text, URLs, and data
- [ ] **Password Generator**: Secure password generation with customizable criteria
- [ ] **Base64 Encoder/Decoder**: Encode and decode Base64 strings
- [ ] **JSON Formatter**: Format and validate JSON data

### 🏗️ **Architecture Improvements (Medium Priority)**

#### Memory & Personalization

- [ ] **User-Specific Memory**: Persistent user preferences and context across sessions
- [ ] **Long-term Context Storage**: Advanced memory system beyond conversation history
- [ ] **User Profile Management**: Individual user settings and customization

#### Integration & Protocols

- [ ] **MCP Integration**: Model Context Protocol support for tool standardization
- [ ] **Alternative Agent Framework**: Evaluate replacing LangChain with Strand or similar
- [ ] **Plugin Architecture**: Standardized plugin system for third-party tools

#### Scalability & Performance

- [ ] **Async Tool Execution**: Parallel tool processing for complex workflows
- [ ] **Tool Result Caching**: Cache expensive operations for better performance
- [ ] **Distributed Orchestrator**: Multi-instance orchestrator deployment

### 🚀 **Low-Hanging Fruit / High Impact Tasks**

#### User Experience Improvements

- [ ] **Tool Usage Hints**: Dynamic suggestions for when to use specific tools
- [ ] **Dark Mode**: Toggle between light and dark themes
- [ ] **Keyboard Shortcuts**: Quick actions for power users
- [ ] **Mobile Responsive Design**: Better mobile interface optimization

#### Developer Experience

- [ ] **Tool Development CLI**: Command-line tool for scaffolding new tools
- [ ] **Hot Reload Tools**: Live tool updates without server restart
- [ ] **Tool Testing Framework**: Automated testing for individual tools
- [ ] **API Rate Limiting**: Smart rate limiting for external API calls
- [ ] **Tool Performance Metrics**: Monitor tool usage and performance

#### Integration & Deployment

- [ ] **Docker Containerization**: Complete Docker setup for easy deployment
- [ ] **Environment Variables UI**: Web interface for configuration management
- [ ] **Health Monitoring**: System health dashboard and alerts
- [ ] **Backup & Restore**: Database backup and restoration utilities
- [ ] **SSL/HTTPS Support**: Production-ready security configuration

#### Advanced Features

- [ ] **Voice Interface**: Speech-to-text and text-to-speech integration
- [ ] **Workflow Automation**: Chain multiple tools into automated workflows
- [ ] **Tool Marketplace**: Community-contributed tool sharing
- [ ] **A/B Testing Framework**: Test different orchestrator prompts and configurations
- [ ] **Analytics Dashboard**: Usage analytics and insights

### 🎯 **Quick Wins (Immediate Impact)**

#### Documentation & Polish

- [ ] **Tool Usage Examples**: Interactive examples for each tool in documentation
- [ ] **Video Tutorials**: Screen recordings showing key features
- [ ] **Error Message Improvements**: More helpful error messages with suggested actions
- [ ] **Loading States**: Better visual feedback during tool execution

#### Quality of Life

- [ ] **Conversation Search**: Search through conversation history
- [ ] **Auto-save Conversations**: Prevent data loss during network issues
- [ ] **Tool Favorites**: Quick access to frequently used tools
- [ ] **Response Formatting**: Better markdown rendering in responses

#### Orchestrator Improvements (Code-Level)

- [ ] **Dynamic Tool Discovery**: Auto-update orchestrator prompt when new tools are added
- [ ] **Tool Usage Analytics**: Track which tools are used most frequently
- [ ] **Smart Tool Suggestions**: Proactive tool recommendations based on context
- [ ] **Conversation Context Optimization**: Better memory management for long conversations
- [ ] **Tool Execution Timeout**: Handle long-running tool operations gracefully
- [ ] **Tool Input Validation**: Better validation and error handling for tool inputs
- [ ] **Parallel Tool Processing**: Execute multiple tools simultaneously when possible
- [ ] **Tool Output Caching**: Cache frequently used tool results for better performance
- [ ] **Tool Dependency Management**: Handle tools that depend on other tools
- [ ] **Custom Tool Prompts**: Allow tools to customize their own prompts dynamically

### 🎖️ **Recommended Next Steps (Prioritized by Impact/Effort Ratio)**

#### **🥇 Immediate Wins (< 1 hour each)**

- [ ] **Add Conversation Timestamps**: Show when messages were sent
- [ ] **Improve Error Messages**: More helpful error descriptions with suggested actions
- [ ] **Add Loading Indicators**: Visual feedback during tool execution
- [ ] **Keyboard Shortcuts**: Ctrl+Enter to send messages, ESC to clear input
- [ ] **Message Copy Button**: Easy copy functionality for assistant responses
- [ ] **Tool Usage Counter**: Show how many times each tool has been used
- [ ] **Auto-focus Input**: Keep input field focused after sending messages
- [ ] **Better Mobile Layout**: Responsive design improvements for mobile devices

#### **🥈 Quick Implementation (< 4 hours each)**

- [ ] **Export Conversations**: Download chat history as PDF, JSON, or TXT
- [ ] **Search Conversations**: Find previous conversations by content
- [ ] **Conversation Bookmarks**: Mark important conversations for easy access
- [ ] **Dark/Light Mode Toggle**: Theme switching functionality
- [ ] **Tool Favorites**: Quick access toolbar for frequently used tools
- [ ] **Conversation Statistics**: Show word count, tool usage, etc.
- [ ] **Auto-save Draft**: Save message drafts automatically
- [ ] **Message Reactions**: Like/dislike responses for feedback

#### **🥉 Medium Effort, High Value (< 8 hours each)**

- [ ] **Voice Input/Output**: Speech-to-text and text-to-speech integration
- [ ] **Workflow Builder**: Chain multiple tools into automated sequences
- [ ] **Template Messages**: Save and reuse common message patterns
- [ ] **Multi-language Support**: Interface translation and i18n
- [ ] **Advanced Search**: Search within documents and conversations simultaneously
- [ ] **Tool Performance Dashboard**: Monitor tool usage and response times
- [ ] **Custom Tool Categories**: Organize tools by user-defined categories
- [ ] **Conversation Sharing**: Share conversations via secure links

---

### Built with ❤️ using FastAPI, LangChain, and OpenAI
