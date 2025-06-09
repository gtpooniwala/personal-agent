# Personal Agent MVP

A sophisticated AI-powered personal assistant built with FastAPI, LangChain, and intelligent tool routing. The system features automatic conversation management, document Q&A capabilities, and a clean web interface.

## ✨ Key Features

- **🤖 Intelligent Agent**: LangChain-powered agent with ReAct pattern for smart tool selection
- **🔧 Dynamic Tools**: Calculator, current time, and expandable tool system
- **📄 Document Q&A**: Upload PDFs and ask questions using RAG (Retrieval Augmented Generation)
- **💬 Smart Conversations**: Automatic title generation and conversation cleanup
- **🌐 Web Interface**: Clean, responsive chat interface with document management
- **🔄 Passive Maintenance**: Backend-driven conversation organization

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

### Available Tools
- **Calculator**: Mathematical expressions and calculations
- **Current Time**: Date and time queries
- **Document Search**: Query uploaded PDF documents

## 🏗️ Architecture

- **Backend**: FastAPI with LangChain agent system
- **Frontend**: Single-page HTML/CSS/JavaScript application  
- **Database**: SQLite for conversations, messages, and documents
- **AI**: OpenAI GPT models with intelligent tool routing
- **Documents**: Vector embeddings for semantic search

## 📁 Project Structure

```
personal-agent/
├── README.md                 # This file
├── AGENT.md                 # Technical docs for AI agents
├── backend/                 # FastAPI backend
│   ├── main.py             # Application entry point
│   ├── test_comprehensive.py # Main test suite (moved for easy access)
│   ├── test_imports.py     # Environment validation test
│   ├── agent/              # LangChain agent implementation
│   ├── api/                # API routes and models
│   ├── database/           # Database models and operations
│   └── services/           # Document processing services
├── frontend/               # Web interface
│   └── index.html         # Single-page application
├── docs/                  # Detailed documentation
└── tests/                 # Test suites and validation
```

## 🔧 Development

For detailed development information, see:
- [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md) - Development workflow
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Technical architecture
- [`docs/API.md`](docs/API.md) - API documentation
- [`AGENT.md`](AGENT.md) - Technical documentation for AI agents

## 📊 System Status

**✅ Production Ready Features:**
- Smart agent routing with LangChain ReAct pattern
- Mathematical calculations and time queries
- Document upload and Q&A with RAG
- Conversation management with automatic titles
- Professional web interface
- Comprehensive error handling

**🚧 Future Enhancements:**
- Gmail, Calendar, and Todoist integrations
- Multi-user support
- Cloud deployment
- Advanced memory and learning

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
