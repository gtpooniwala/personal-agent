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
DATABASE_URL_DOCKER=postgresql+psycopg://personal_agent:personal_agent@postgres:5433/personal_agent
TEST_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5433/personal_agent_test
EVAL_DATABASE_URL=postgresql+psycopg://personal_agent:personal_agent@localhost:5433/personal_agent_test
DOCKER_POSTGRES_DATA_DIR=${HOME}/.personal-agent/postgres
```

Optional observability:
```env
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

Optional local auth testing:
```env
AGENT_API_KEY=replace-with-a-long-random-token
ENVIRONMENT=local
```

Optional Gmail setup:
```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8001/api/v1/gmail/callback
CREDENTIALS_MASTER_KEY=...
```

One-time Google Cloud setup for Gmail:
1. Sign in to Google Cloud with the work account that should own the app integration.
2. Create or select the project that backs this app.
3. Enable the Gmail API for that project.
4. Configure an OAuth consent screen for an External app.
5. While the app is still private/internal to your team, keep the consent screen in Testing and add each allowed Gmail user as a test user.
6. Create one OAuth 2.0 Web application client for the app.
7. Add the backend callback URI you will actually use:
   - local Python: `http://localhost:8000/api/v1/gmail/callback`
   - local Docker: `http://localhost:8001/api/v1/gmail/callback`
   - production: `https://<your-backend-host>/api/v1/gmail/callback`
8. Copy the client ID and client secret into `.env` or your secret manager.
9. Generate `CREDENTIALS_MASTER_KEY` once and keep it stable across deploys.

Users do not need their own Google Cloud project or Gmail API enablement. You enable Gmail API once in the app's project, then each user connects Gmail through the app's OAuth flow.

Start services:
```bash
docker compose up --build
```

Access:
- Frontend: `http://127.0.0.1:3001` by default
- Backend: `http://127.0.0.1:8001` by default
- Swagger: `http://127.0.0.1:8001/docs` by default when `AGENT_API_KEY` is unset

These Docker ports come from:
- `DOCKER_FRONTEND_PORT`
- `DOCKER_API_PORT`
- `DOCKER_POSTGRES_PORT`

The Docker Postgres container now uses a shared absolute host path by default:
- `DOCKER_POSTGRES_DATA_DIR=${HOME}/.personal-agent/postgres`

That keeps user-specific integration credentials, including Gmail OAuth tokens stored in Postgres,
available across worktrees by default. If you intentionally want an isolated clean-room database for
one worktree, override `DOCKER_POSTGRES_DATA_DIR` in that worktree's `.env`.

Compose uses those port values directly on both the host and inside each container. There is no
host-to-container remapping layer anymore, so changing `DOCKER_API_PORT=8010` means the backend
listens on `8010` and Docker publishes `8010:8010`.

Auth behavior:
- If `AGENT_API_KEY` is unset and `ENVIRONMENT=local`, the backend stays open for local development.
- If `AGENT_API_KEY` is set, send `Authorization: Bearer <AGENT_API_KEY>` to backend endpoints.
- When local auth is enabled, `/docs` and `/openapi.json` are protected too, so browser-loaded Swagger is not anonymously reachable.
- The Docker frontend proxy talks to the backend over the internal Compose network using `DOCKER_API_BASE_URL` (default `http://personal-agent:8001`), not host `localhost`.
- The Docker frontend reuses `AGENT_API_KEY` when you set one; otherwise it falls back to a local-only proxy token so `/api/agent/...` requests still work during unauthenticated local development.

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

Optional authenticated local backend run:
```bash
export ENVIRONMENT=local
export AGENT_API_KEY="$(openssl rand -base64 48)"
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
- Gmail dependencies are installed
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` are set
- `CREDENTIALS_MASTER_KEY` is set so per-user tokens can be stored encrypted in Postgres
- the user has completed `/api/v1/gmail/connect`
- `ENABLE_GMAIL_INTEGRATION` is not disabling it
- the Google OAuth consent screen is using the correct work-owned project and the user is allowed to authorize it
