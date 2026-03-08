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
TEST_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5433/personal_agent_test
EVAL_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5433/personal_agent_test
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
- Frontend: `http://127.0.0.1:3001` by default
- Backend: `http://127.0.0.1:8001` by default
- Swagger: `http://127.0.0.1:8001/docs` by default

These Docker ports come from:
- `DOCKER_FRONTEND_PORT`
- `DOCKER_API_PORT`

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
python3 tests/run_runtime_evals.py
```

If you changed prompt behavior or tool-calling behavior, also run:
```bash
python3 tests/run_llm_evals.py --mode mock
python3 tests/run_llm_evals.py --mode live
```

Live eval notes:
- `python3` is fine; the harness re-execs into the repo `.venv` automatically when needed
- if you are using Docker Compose Postgres, keep `TEST_DATABASE_URL` and `EVAL_DATABASE_URL` on `localhost:5433`
- the live harness can create the dedicated `*_test` / `*_eval` database once the Postgres server itself is reachable

## Common Problems

### Database connection failures
```bash
pg_isready -h localhost -p 5433 -U personal_agent -d personal_agent
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
