# Setup Guide

Use [`../README.md`](../README.md) for the shortest path. This file adds a little more detail and calls out the environment variables that matter most.

## Recommended Path: Docker

### Prerequisites
- Docker Desktop or Docker Engine with Compose
- A Gemini API key or OpenAI API key

### Basic Setup
```bash
git clone https://github.com/gtpooniwala/personal-agent.git
cd personal-agent
cp .env.example .env
```

Set at least one model provider key in `.env`:
```env
GEMINI_API_KEY=...
# or
OPENAI_API_KEY=...
```

Useful database variables:
```env
DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5432/personal_agent
DATABASE_URL_DOCKER=postgresql+psycopg://personal_agent:personal_agent@postgres:5432/personal_agent
TEST_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5432/personal_agent_test
EVAL_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5432/personal_agent_test
```

Optional observability:
```env
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

Optional Gmail in Docker:
```bash
mkdir -p data/gmail
```

Start services:
```bash
docker compose up --build
```

Access:
- Frontend: `http://127.0.0.1:3000`
- Backend: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

## Local Debug Path
Use this when you need local Python or frontend debugging outside containers.

### Prerequisites
- Python 3.11+
- Node.js 20.9+
- Local PostgreSQL

### Backend
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Validation After Setup
Run the standard local validation command:
```bash
scripts/run_local_checks.sh
```

If you changed runtime or orchestration behavior, also run:
```bash
python tests/run_runtime_evals.py
```

If you changed prompt behavior or tool-calling behavior, also run:
```bash
python tests/run_llm_evals.py --mode mock
```

## Common Problems

### Database connection failures
```bash
pg_isready -h localhost -p 5432 -U personal_agent -d personal_agent
```

### Port already in use
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### Missing provider key
The app requires at least one of:
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`

### Gmail not available
Gmail support is conditional. Make sure:
- Gmail credentials are present
- any required auth files are mounted or available
- `ENABLE_GMAIL_INTEGRATION` is not disabling it
```bash
# View server logs
tail -f logs/server.log

# View error logs
tail -f logs/error.log
```

#### Database Debugging
```bash
# Check database contents
psql postgresql://personal_agent:personal_agent@localhost:5432/personal_agent
\dt
\d conversations
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
