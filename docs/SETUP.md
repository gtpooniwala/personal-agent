# Setup Guide

This guide provides detailed instructions for setting up the Personal Agent project on your local machine.

## Prerequisites

### System Requirements
- **Python**: 3.11 or higher
- **Node.js**: 18.0 or higher (for frontend development)
- **Operating System**: macOS, Linux, or Windows with WSL2
- **Memory**: At least 4GB RAM available
- **Storage**: 2GB free disk space

### Required Accounts & API Keys
- **OpenAI API Key**: Required for AI agent functionality
- **Optional**: Other AI provider keys (Anthropic, etc.) for extended functionality

## Installation Steps

### 1. Clone the Repository
```bash
git clone <repository-url>
cd personal-agent
```

### 2. Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the project root:
```bash
# Copy the example environment file
cp .env.example .env
```

Edit the `.env` file with your configuration:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
HOST=localhost
PORT=8000
DEBUG=true

# Database Configuration
DATABASE_URL=sqlite:///./data/agent.db

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Logging
LOG_LEVEL=INFO
```

### 4. Initialize the Database
```bash
# From the backend directory
python -c "from database.models import init_db; init_db()"
```

### 5. Make Scripts Executable
```bash
# Make setup and start scripts executable
chmod +x setup.sh
chmod +x start_server.sh
```

### 6. Run Initial Setup
```bash
# Run the automated setup script
./setup.sh
```

## Verification

### 1. Test Backend Server
```bash
# Start the backend server
./start_server.sh

# In another terminal, test the API
curl http://localhost:8000/health
```

Expected response:
```json
{
    "status": "healthy",
    "timestamp": "2025-06-08T10:00:00Z",
    "version": "1.0.0"
}
```

### 2. Test Frontend
Open your browser and navigate to:
- Frontend: `http://localhost:8000` (served by FastAPI)
- API Documentation: `http://localhost:8000/docs`

### 3. Test Agent Functionality
```bash
# Run basic agent tests
cd backend
python test_basic_agent.py
```

## Configuration Options

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API authentication key | - | Yes |
| `HOST` | Server bind address | localhost | No |
| `PORT` | Server port number | 8000 | No |
| `DEBUG` | Enable debug mode | false | No |
| `DATABASE_URL` | Database connection string | sqlite:///./data/agent.db | No |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | * | No |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | INFO | No |
| `MAX_FILE_SIZE` | Maximum upload file size (bytes) | 10485760 | No |
| `MEMORY_RETENTION_DAYS` | Days to retain conversation memory | 30 | No |

### Advanced Configuration

#### Custom AI Models
To use custom AI models, modify `backend/config/settings.py`:
```python
AI_MODEL_CONFIG = {
    "primary_model": "gpt-4",
    "fallback_model": "gpt-3.5-turbo",
    "max_tokens": 4000,
    "temperature": 0.7
}
```

#### Database Configuration
For production environments, consider using PostgreSQL:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/personal_agent
```

#### CORS Configuration
For production deployment:
```env
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## Troubleshooting

### Common Issues

#### 1. Import Errors
**Problem**: `ModuleNotFoundError` when running the application
**Solution**: 
```bash
# Ensure you're in the correct directory and virtual environment is activated
cd backend
source ../venv/bin/activate
pip install -r requirements.txt
```

#### 2. Database Connection Issues
**Problem**: SQLite database errors
**Solution**:
```bash
# Recreate the database
rm data/agent.db
python -c "from database.models import init_db; init_db()"
```

#### 3. OpenAI API Errors
**Problem**: Authentication or rate limit errors
**Solution**:
- Verify your API key is correct and has sufficient credits
- Check rate limits and consider implementing exponential backoff
- Ensure API key has the required permissions

#### 4. Port Already in Use
**Problem**: `Address already in use` error
**Solution**:
```bash
# Find and kill the process using the port
lsof -ti:8000 | xargs kill -9
# Or use a different port
PORT=8001 ./start_server.sh
```

#### 5. File Upload Issues
**Problem**: File upload failures or large file errors
**Solution**:
- Check file size limits in configuration
- Ensure the `data/uploads/` directory exists and is writable
- Verify file permissions

### Logs and Debugging

#### Enable Debug Mode
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

#### Check Logs
```bash
# View server logs
tail -f logs/server.log

# View error logs
tail -f logs/error.log
```

#### Database Debugging
```bash
# Check database contents
sqlite3 data/agent.db
.tables
.schema conversations
SELECT * FROM conversations LIMIT 5;
```

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes for better query performance
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_documents_created_at ON documents(created_at);
```

#### Memory Management
- Monitor memory usage during long conversations
- Configure memory retention settings appropriately
- Consider implementing conversation archiving for very active instances

## Next Steps

After successful setup:
1. Read the [Development Guide](DEVELOPMENT_GUIDE.md) for development workflow
2. Check the [API Documentation](API.md) for integration details
3. Review the [Architecture Guide](ARCHITECTURE.md) to understand the system
4. Run the test suite to ensure everything is working correctly

## Getting Help

If you encounter issues not covered in this guide:
1. Check the [GitHub Issues](https://github.com/your-repo/personal-agent/issues)
2. Review the debugging documentation in `docs/debugging/`
3. Run the diagnostic script: `python backend/test_imports.py`
4. Enable debug logging and check the logs

For development questions, see the [Development Guide](DEVELOPMENT_GUIDE.md).
