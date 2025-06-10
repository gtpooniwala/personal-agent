# Personal Agent MVP

A sophisticated AI-powered personal assistant built with FastAPI, LangChain, and an intelligent orchestrator architecture. The system features modular tool delegation, automatic conversation management, document Q&A capabilities, and a clean web interface.

## ✨ Key Features

- **🎼 Orchestrator Architecture**: Centralized `CoreOrchestrator` that intelligently delegates to specialized tools/agents
- **🔧 Modular Tool System**: Dynamic tool registry with easy addition/removal of capabilities
- **📄 Document Q&A**: Upload PDFs and ask questions using RAG (Retrieval Augmented Generation)
- **💬 Smart Conversations**: Automatic title generation and conversation cleanup
- **🌐 Web Interface**: Clean, responsive chat interface with document management
- **🔄 Passive Maintenance**: Backend-driven conversation organization
- **⚙️ Scalable Design**: Adding new tools only requires implementing the tool and updating orchestrator prompts

## 🆕 Recent Major Improvements

### **Pydantic Tool Conversion (Complete)**
- ✅ **Structured Input Validation**: All tools now use Pydantic models for input validation
- ✅ **Multi-Input Tool Support**: Fixed LangChain agent compatibility for complex tool parameters
- ✅ **95.5% Test Success Rate**: Comprehensive test suite with 21/22 tests passing
- ✅ **Enhanced Calculator**: Now accepts clean expressions like `expression="2**4"`
- ✅ **Improved Time Tool**: Structured input with format preferences
- ✅ **Smart Scratchpad**: Action-based input with better organization
- ✅ **Document QA Enhancement**: Dynamic chunk selection (1-5 results based on complexity)

### **Document Upload System Enhancement**
- ✅ **AI-Generated Summaries**: Automatic one-sentence summaries for all uploaded documents
- ✅ **Context-Aware AI**: System informs AI about available documents and their content
- ✅ **Smart Document Handling**: AI behavior adapts based on document availability
- ✅ **Database Migration**: Seamless upgrade for existing installations

### **Test Suite Organization**
- ✅ **Comprehensive Testing**: Main test suite covers 22 scenarios across all tool categories
- ✅ **Clean Test Structure**: Organized test files with clear separation of concerns
- ✅ **Behavioral Validation**: Tests verify tool usage patterns and response quality

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
│                            CORE ORCHESTRATOR                                    │
│                         (Decision Making Hub)                                  │
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐            │
│  │  Tool Registry  │    │   LLM Agent     │    │ Context Manager │            │
│  │  (Dynamic)      │◄──►│ (GPT-3.5-turbo) │◄──►│   (Documents)   │            │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘            │
└─────────────────────────────────┬───────────────────────────────────────────────┘
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
│IMPLEMENTED│ │IMPLEMENTED│ │ IMPLEMENTED  │ │IMPLEMENTED  │ │ PLACEHOLDER │ │ PLACEHOLDER │ │ PLACEHOLDER │
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

#### 🚧 **Placeholder Tools** (Framework Ready)

**5. Gmail Tool**
- **Status**: 🚧 Placeholder Implementation
- **Purpose**: Email management and automation
- **Planned Features**:
  - Search and read emails
  - Compose and send messages
  - Email organization (labels, folders)
  - Automation workflows
- **Implementation Requirements**: Gmail API integration, OAuth authentication
- **Availability**: Not yet available

**6. Calendar Tool**  
- **Status**: 🚧 Placeholder Implementation
- **Purpose**: Schedule and event management
- **Planned Features**:
  - Read upcoming events
  - Create calendar events
  - Meeting scheduling
  - Reminder management
- **Implementation Requirements**: Google Calendar API, OAuth authentication
- **Availability**: Not yet available

**7. Todoist Tool**
- **Status**: 🚧 Placeholder Implementation  
- **Purpose**: Task and project management
- **Planned Features**:
  - Create and manage tasks
  - Project organization
  - Priority and due date management
  - Completion tracking
- **Implementation Requirements**: Todoist API integration
- **Availability**: Not yet available

### Information Flow Architecture

```text
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    CORE ORCHESTRATOR                        │
│                                                             │
│  1. Receive Request → 2. Analyze Intent → 3. Context Check  │
│           │                    │                    │       │
│           ▼                    ▼                    ▼       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   User Input    │  │  LLM Analysis   │  │ Tool Registry│ │
│  │   Processing    │  │ (GPT-3.5-turbo) │  │   Query     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│           │                    │                    │       │
│           └────────────────────┼────────────────────┘       │
│                                ▼                            │
│                    4. Tool Selection Decision               │
│                                │                            │
└────────────────────────────────┼────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌─────────────────────┐    ┌─────────────────────┐
        │   Direct Response   │    │   Tool Execution    │
        │   (No tools needed) │    │                     │
        └─────────────────────┘    └─────────────────────┘
                    │                         │
                    │              ┌─────────┴─────────┐
                    │              │                   │
                    │              ▼                   ▼
                    │    ┌─────────────────┐  ┌─────────────────┐
                    │    │ Implemented     │  │   Placeholder   │
                    │    │ Tools Execute   │  │ Tools Return    │
                    │    │                 │  │ "Not Available" │
                    │    └─────────────────┘  └─────────────────┘
                    │              │                   │
                    │              └─────────┬─────────┘
                    │                        │
                    ▼                        ▼
        ┌─────────────────────────────────────────────────────┐
        │             RESPONSE GENERATION                     │
        │                                                     │
        │  • Orchestrator compiles final response             │
        │  • Includes tool results (if any)                   │
        │  • Maintains conversation context                   │
        │  • Returns structured response to user              │
        └─────────────────────────────────────────────────────┘
                                 │
                                 ▼
                            User Response
```

**Tool Availability Logic**: The orchestrator dynamically determines which tools to expose based on context:
- **Always Available**: Calculator, Time tools
- **Context-Dependent**: Document Q&A (only when documents are selected)
- **Future Integration**: Gmail, Calendar, Todoist (when implemented and authenticated)

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
- [ ] **Internet Search Tool**: Web search capabilities with result summarization
- [ ] **Gmail Tool**: Complete email management (reading, sending, organizing)
- [ ] **Calendar Tool**: Full calendar integration with scheduling intelligence
- [ ] **Todoist Tool**: Advanced task and project management

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
- [ ] **Conversation Export**: Export chat history in multiple formats (PDF, JSON, etc.)
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

**Priority Legend:**
- 🔧 **New Tools**: Expand system capabilities
- 🏗️ **Architecture**: Foundation improvements  
- 🚀 **Low-Hanging Fruit**: Easy wins with high user impact
- 🎯 **Quick Wins**: Immediate improvements requiring minimal effort

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

- **Documentation**: See [`docs/`](docs/) for detailed guides
- **Issues**: Create GitHub issues for bugs or feature requests
- **Development**: Check [`AGENT.md`](AGENT.md) for technical details

---

**Built with ❤️ using FastAPI, LangChain, and OpenAI**
