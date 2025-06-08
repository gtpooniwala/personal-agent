# Personal Agent MVP

A sophisticated AI-powered personal assistant built with LangChain and FastAPI. This MVP provides a scalable foundation for personal productivity automation with conversation memory, tool integration, and a clean web interface.

## ✨ Key Features

- **🤖 Intelligent AI Agent**: LangChain ReAct pattern with OpenAI integration
- **💬 Conversation Memory**: Persistent chat history across sessions
- **🔧 Tool Integration**: Extensible tool system (calculator, time, future: Gmail, Calendar, Todoist)
- **🌐 Modern Web Interface**: Clean, responsive HTML/CSS/JavaScript frontend
- **📊 Analytics**: Token usage tracking and cost monitoring
- **🏗️ Scalable Architecture**: Ready for cloud deployment and multi-user support

## 🚀 Quick Start

### Prerequisites
- Anaconda or Miniconda installed
- OpenAI API key ([get one here](https://platform.openai.com/))

### Installation
```bash
# Clone and setup (automated)
chmod +x setup.sh
./setup.sh

# Configure API key
nano backend/.env  # Add your OpenAI API key
```

### Launch
```bash
# Start backend
conda activate personalagent
cd backend && python main.py

# Open frontend
# Navigate to: file:///path/to/frontend/index.html
```

The application will be running at `http://127.0.0.1:8000` with interactive API docs at `/docs`.

## 🎯 Current Capabilities

### Working Features ✅
- **Mathematical Calculations**: "What is 15 * 23?" → 345
- **Current Time**: "What time is it?" → Current date/time
- **Conversation History**: Persistent chat across sessions
- **Token Tracking**: Usage monitoring and cost calculation
- **API Integration**: Full REST API with documentation

### Tools Available
- 🧮 **Calculator**: Basic mathematical operations
- ⏰ **Current Time**: Date and time queries
- 📧 **Gmail** (Placeholder): Ready for implementation
- 📅 **Calendar** (Placeholder): Ready for implementation  
- ✅ **Todoist** (Placeholder): Ready for implementation

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[USAGE_GUIDE.md](USAGE_GUIDE.md)** | Complete setup and usage instructions |
| **[CURRENT_STATUS.md](CURRENT_STATUS.md)** | Detailed feature status and metrics |
| **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** | Development setup and roadmap |

## 🏗️ Architecture

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
                    │   Tools &       │
                    │   External APIs │
                    └─────────────────┘
```

### Technology Stack
- **Backend**: FastAPI + LangChain + SQLAlchemy
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Database**: SQLite (local) → PostgreSQL (production)
- **AI**: OpenAI GPT models
- **Tools**: Extensible Python-based tool system

## 🔧 Development

### Quick Development Setup
```bash
# Install dependencies
conda create -n personalagent python=3.11
conda activate personalagent
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Add your OpenAI API key to backend/.env

# Run tests (when implemented)
pytest backend/tests/
```

### Adding New Tools
See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for detailed instructions on extending the agent with new capabilities.

## 🗺️ Roadmap Overview

### Phase 1: Core Enhancements (2-4 weeks)
- Authentication & user management
- Enhanced memory system
- Tool improvements

### Phase 2: External Integrations (1-2 months)
- Gmail integration
- Calendar management
- Todoist task management

### Phase 3: Multi-user & Cloud (2-3 months)
- Cloud deployment
- Multi-tenant architecture
- Advanced security

### Phase 4: Advanced AI Features (3-6 months)
- Long-term memory
- Context learning
- Autonomous task execution

### Phase 5: Enterprise Features (6+ months)
- Team workspaces
- Advanced analytics
- Custom integrations

## 🤝 Contributing

We welcome contributions! Please see our [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- Contribution workflow

## 📊 Project Status

| Component | Status | Coverage |
|-----------|--------|----------|
| Backend API | ✅ Complete | Core functionality |
| Chat Interface | ✅ Complete | Basic UI |
| Agent System | ✅ Complete | LangChain integration |
| Memory System | ✅ Complete | SQLite-backed |
| Tool System | ✅ Complete | Calculator, Time |
| Authentication | ⏳ Planned | Phase 1 |
| External APIs | ⏳ Planned | Phase 2 |
| Cloud Deploy | ⏳ Planned | Phase 3 |

## 📧 Support

- **Documentation**: Check our comprehensive guides in the `docs/` section
- **Issues**: Report bugs or request features via GitHub Issues
- **Development**: See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for technical details

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Ready to get started?** Follow the [Quick Start](#-quick-start) guide above or dive deeper with our [USAGE_GUIDE.md](USAGE_GUIDE.md)!
