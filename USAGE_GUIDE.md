# Personal Agent MVP - Usage Guide

## 🚀 Quick Start

This guide will help you get the Personal Agent MVP running on your local machine in just a few minutes.

## 📋 Prerequisites

Before starting, ensure you have:
- **Anaconda or Miniconda** installed
- **OpenAI API Key** (get one from https://platform.openai.com/)
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

## 🛠️ Installation & Setup

### 1. Clone and Setup Environment

```bash
# Navigate to the project directory
cd /Users/gauravpooniwala/Documents/code/projects/personal-agent

# Run the automated setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a conda environment named `personalagent`
- Install all required Python dependencies
- Create necessary directories
- Set up configuration files

### 2. Configure API Key

Edit the environment file with your OpenAI API key:

```bash
# Open the environment file
nano backend/.env

# Add your OpenAI API key
OPENAI_API_KEY="your_api_key_here"
```

## 🎯 Starting the Application

### 1. Start the Backend Server

```bash
# Activate the conda environment
conda activate personalagent

# Navigate to backend directory
cd backend

# Start the FastAPI server
python main.py
```

You should see output like:
```
INFO: Personal Agent API starting up...
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
```

The backend will be available at: **http://127.0.0.1:8000**

### 2. Open the Frontend

Open your web browser and navigate to:
```
file:///Users/gauravpooniwala/Documents/code/projects/personal-agent/frontend/index.html
```

Or simply double-click the `frontend/index.html` file to open it in your default browser.

**Note:** Replace the path above with your actual project path. You can find the full path by running:
```bash
pwd
```
from within the project directory.

## 💬 Using the Chat Interface

### Basic Usage

1. **Start a Conversation**: Type a message in the input field and press Enter or click Send
2. **View History**: Previous messages appear in the chat area
3. **New Conversation**: Click "New Conversation" to start fresh

### Natural Conversation

The agent now responds naturally to general questions without unnecessary tool information:

```
You: "Hello! How are you doing today?"
Agent: "Hello! I'm here and ready to assist you. How can I help you today?"
```

### Available Commands & Tools

The agent automatically uses tools when needed, but responds naturally for general conversation:

#### 🧮 Mathematical Calculations
```
"What is 15 * 23?"
"Calculate 100 + 25 * 4"
"Can you help me with 456 / 12?"
```

#### ⏰ Current Time
```
"What time is it?"
"What's the current date and time?"
```

#### 💬 General Conversation
```
"Hello! How are you?"
"Tell me about yourself"
"What can you help me with?"
```

## 🔧 API Usage (Advanced)

### Direct API Testing

You can test the API directly using curl or any HTTP client:

#### Health Check
```bash
curl http://127.0.0.1:8000/health
```

#### Send a Chat Message
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 5 + 5?"}'
```

#### Get Conversations
```bash
curl http://127.0.0.1:8000/api/v1/conversations
```

### API Documentation

Visit **http://127.0.0.1:8000/docs** for interactive API documentation with Swagger UI.

## 🗂️ Data Storage

### Conversation History
- All conversations are automatically saved to `backend/data/agent.db`
- Each conversation has a unique ID and timestamp
- Messages are preserved between sessions

### Database Location
```
backend/data/agent.db  # SQLite database file
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Server Won't Start
```bash
# Check if conda environment is activated
conda activate personalagent

# Verify dependencies are installed
pip list | grep fastapi

# Check for port conflicts
lsof -i :8000
```

#### 2. Frontend Can't Connect
- Ensure backend server is running on port 8000
- Check browser console for CORS errors
- Verify the frontend is accessing the correct backend URL

#### 3. API Key Issues
- Verify your OpenAI API key is correctly set in `backend/.env`
- Check that you have sufficient credits in your OpenAI account
- Ensure the API key has the correct permissions

#### 4. Database Errors
```bash
# Check if data directory exists
ls -la backend/data/

# Create data directory if missing
mkdir -p backend/data
```

### Log Files

Monitor the backend logs in the terminal where you started the server. Logs include:
- Request/response information
- Error messages
- Token usage statistics

## 🛑 Stopping the Application

### Stop the Backend
Press `Ctrl+C` in the terminal where the server is running.

### Clean Shutdown
The application handles graceful shutdown and will save any pending data.

## 🔄 Restarting

To restart the application:

1. Stop the backend server (`Ctrl+C`)
2. Start it again with `python main.py`
3. Refresh the frontend browser tab

## 📊 Monitoring Usage

### Token Usage
Each API response includes token usage information:
```json
{
  "response": "The answer is 42",
  "token_usage": 150,
  "cost": 0.0003
}
```

### Conversation Management
- View all conversations via the API or frontend
- Each conversation is automatically titled with timestamp
- Messages are counted for each conversation

## 🎯 Next Steps

Once you have the basic system running:

1. **Explore the Tools**: Try different mathematical expressions and time queries
2. **Test Conversation Memory**: Have multi-turn conversations to see context retention
3. **API Integration**: Use the API endpoints to build custom integrations
4. **Development**: Follow the [Development Guide](DEVELOPMENT_GUIDE.md) to add new features

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review the server logs for error messages
3. Verify all prerequisites are properly installed
4. Check the [Current Status](CURRENT_STATUS.md) for known issues

---

*For development and customization, see [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)*
