# Personal Agent

A local-first AI assistant platform built around a LangGraph orchestrator, with tool-calling, persistent conversation memory, and PDF-based retrieval.

This project demonstrates practical AI product engineering: orchestration patterns, modular tooling, RAG over user documents, and a production-style backend/frontend split.

## What It Does

The assistant can:
- Hold multi-turn conversations with persisted history
- Route requests to tools (calculator, time, internet search, scratchpad, user profile)
- Process uploaded PDFs and answer document-grounded questions
- Show transparent tool actions in the UI
- Maintain conversation titles and summarize long histories to manage context

## Architecture

```mermaid
flowchart LR
    UI["Frontend (Next.js App Router)"] --> API["FastAPI API Layer"]
    API --> ORCH["LangGraph ReAct Orchestrator"]
    ORCH --> REG["Tool Registry"]
    ORCH --> LLM["Gemini Chat Model (Default)"]

    REG --> CALC["Calculator"]
    REG --> TIME["Current Time"]
    REG --> SEARCH["Internet Search"]
    REG --> DOCS["Document Search (RAG)"]
    REG --> PAD["Scratchpad"]
    REG --> PROFILE["User Profile"]
    REG --> GMAIL["Gmail Read (OAuth)"]

    API --> DB["SQLite (SQLAlchemy)"]
    API --> DOCPROC["PDF Processing + Embeddings"]
    DOCPROC --> DB
```

### Request Flow

Current runtime path (today):
1. User sends a message from the frontend.
2. `POST /api/v1/chat` processes the request in-request and returns the assistant response.

Target runtime path (rolling out soon):
1. `POST /chat` or `POST /runs` submits asynchronous work and returns a `run_id`.
2. Backend worker processes run steps asynchronously (tool selection, tool execution, synthesis).
3. Frontend polls `GET /runs/{run_id}/status` and `GET /runs/{run_id}/events`.
4. Legacy `POST /api/v1/chat` synchronous behavior is deprecated and will be removed.

## Implemented Capabilities

| Capability | Status | Notes |
|---|---|---|
| Conversation API + persistence | Implemented | SQLite-backed conversations/messages |
| Tool orchestration (LangGraph ReAct) | Implemented | Dynamic tool availability by context |
| Calculator tool | Implemented | Input-validated arithmetic evaluation |
| Time tool | Implemented | Current date/time responses |
| Document upload + RAG search | Implemented | PDF chunking + embeddings + semantic search |
| Scratchpad tool | Implemented | Persistent per-user notes |
| User profile tool | Implemented | Long-term profile memory (JSON + LLM merge) |
| Internet search tool | Implemented | DuckDuckGo default, optional Bing/Google/SerpAPI |
| Gmail read tool | Conditional | Hidden by default; enable with `ENABLE_GMAIL_INTEGRATION=true` + valid `GMAIL_CREDENTIALS_PATH` and Gmail dependencies |
| Calendar/Todoist tools | Placeholder | Scaffold exists, not wired into active tool set |

## Stack

- Backend: Python, FastAPI, LangChain, LangGraph, SQLAlchemy
- LLM/Embeddings: Gemini by default (`gemini-2.5-flash` + `text-embedding-004`), OpenAI optional via config
- Frontend: Next.js + React
- Storage: SQLite + local filesystem (`data/`)

## LangChain/LangGraph Migration Baseline

Contributor reference for current migration state:
- Dependency source of truth:
  - Backend: `backend/requirements.txt`
  - Frontend: `frontend/package.json`
- Completed baseline:
  - LangGraph ReAct orchestration is the active architecture.
  - Tool routing is centralized in the orchestrator tool registry.
- Runtime migration status:
  - Current implementation uses `POST /api/v1/chat` synchronous request lifecycle.
  - Next target is async `/chat` + `/runs` submission with status/events polling.

## Quick Start (Docker, Recommended)

### 1) Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Gemini API key (default provider)

### 2) Configure environment

```bash
git clone https://github.com/gtpooniwala/personal-agent.git
cd personal-agent
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
# Optional observability: set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL
```

### 3) Start backend + frontend

```bash
docker compose up --build
```

### 4) Access services

- Frontend: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- Backend API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5) Stop services

```bash
docker compose down
```

### Docker Troubleshooting

Rebuild and restart services:

```bash
docker compose up --build -d
docker compose ps
```

Inspect logs:

```bash
docker compose logs -f personal-agent frontend
```

Clean shutdown:

```bash
docker compose down
```

## Debugging Without Docker (Optional)

Use this only when you need local debugging outside containers.

### Prerequisites

- Python 3.11+
- Node.js 18.17+

### Backend (debug)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend (debug, new terminal)

```bash
cd frontend
npm install
npm run dev
```

## Alternative Local Scripts

The repo includes:
- `setup.sh`: conda-based setup
- `start_server.sh`: macOS Terminal automation (`osascript`) for backend + frontend startup

Use these for local debugging if your environment matches their assumptions.

## Running Tests

Standard local validation command:

```bash
scripts/run_local_checks.sh
```

This command:
- creates `.venv` if needed
- installs backend dependencies
- runs guarded unit tests (`tests/run_unit_tests.py`)
- runs deterministic repository checks (`tests/run_repo_checks.py`)

Guardrails:
- no discovered tests = non-pass
- skip-only unit test runs = non-pass

Optional direct unit-test runner:

```bash
python3 tests/run_unit_tests.py
```

Optional (if you use `pytest` directly):

```bash
pytest tests -q
```

Some tests rely on API/LLM behavior and are easier to run in an environment with full project dependencies.

## Running Repository Checks

Run deterministic repository checks:

```bash
python tests/run_repo_checks.py
```

## Observability Baseline

- Structured JSON logs are emitted by the backend (request ID + route + latency fields).
- Runtime counters are stored in SQLite (`runtime_counters` table).
- Langfuse tracing is enabled when the following env vars are set:
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
  - `LANGFUSE_BASE_URL` (defaults to `https://cloud.langfuse.com`)
  - `LANGFUSE_ENABLED=true`
  - Optional: `LANGFUSE_SAMPLE_RATE` (`0.0` to `1.0`)

Langfuse instrumentation currently covers active API endpoints and orchestration paths (excluding `GET /api/v1/health` by design).

These checks run in CI because they are deterministic and fast.

Local report artifact:
- Report: `tests/repo_checks/results.json` (gitignored)

## Running LLM/Workflow Evals

LLM/workflow evals should be run locally when changes affect model prompts, tool-calling behavior, or orchestration flow.

Deterministic harness run:

```bash
python tests/run_llm_evals.py --mode mock
```

Live orchestrator/model run:

```bash
python tests/run_llm_evals.py --mode live
```

Reports are written to `tests/llm_evals/results/latest.json` and timestamped report files.
If the provider key is missing, live mode exits as `blocked` and tells you which key to configure.

## API Surface

Base URL: `http://127.0.0.1:8000`

Route notation:
- Primary notation in docs: bare routes (`/chat`, `/runs`, ...)
- Legacy compatibility notation: `/api/v1/...` (older deployments)
- Current mainline implementation still serves routes under `/api/v1`.
- Bare-route notation is the target runtime contract rolling out next.

Core endpoints:
- Current implementation:
  - `POST /api/v1/chat` (legacy synchronous path)
- Target migration behavior (rolling out soon):
- `POST /runs`
- `GET /runs/{run_id}/status`
- `GET /runs/{run_id}/events`
- `POST /chat`
- `GET /conversations`
- `POST /conversations`
- `GET /conversations/{conversation_id}/messages`
- `GET /tools`
- `POST /documents/upload`
- `GET /documents`
- `DELETE /documents/{document_id}`
- `POST /conversations/{conversation_id}/generate-title`
- `GET /health`

Interactive docs:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

## Repository Layout

```text
personal-agent/
├── backend/
│   ├── api/                   # FastAPI routes + schemas
│   ├── orchestrator/          # LangGraph orchestrator + tool registry
│   ├── orchestrator/tools/    # Tool implementations
│   ├── services/              # Document processing + retrieval
│   ├── database/              # SQLAlchemy models + operations
│   └── main.py                # API entrypoint
├── frontend/                  # Next.js frontend app
├── tests/                     # Unit/integration-style tests
├── docs/                      # Extended architecture + feature docs
└── data/                      # Local runtime data (DB, uploads, profiles, scratchpad)
```

## Engineering Notes

Design choices reflected in this implementation:
- **Graph-based orchestration** over hardcoded routing, so behavior can evolve by adding tools and prompt policy.
- **Context-aware tool gating** (e.g., document search appears only when documents are selected).
- **Separation of orchestration and response synthesis**, which keeps tool execution traces inspectable while preserving fluent final responses.
- **Local-first persistence** for fast iteration and debuggability.

## Current Limitations

- Single-user default (`user_id="default"`) across most flows.
- Document retrieval computes similarity from stored embeddings in SQLite; not yet an external vector DB.
- Tool/model config exists, but some model selections are still hardcoded in tool/orchestrator paths.
- Integration tools (Gmail/Calendar/Todoist) have different maturity levels and setup requirements.

## Roadmap (High-Impact)

- Multi-user auth + tenant isolation
- PostgreSQL + managed vector store option
- Expand eval coverage for tool-selection accuracy and regression checks
- Observability for latency/token/tool metrics
- Production deployment profile (secrets, health checks, structured logging)

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Runtime Migration Architecture](docs/MIGRATION_RUNTIME_ARCHITECTURE.md)
- [Feature Overview](docs/FEATURES_OVERVIEW.md)
- [Development Guide](docs/DEVELOPMENT_GUIDE.md)
- [Project Status](docs/PROJECT_STATUS.md)
- [Workboard](docs/WORKBOARD.md)
- [Roadmap](docs/ROADMAP.md)
- [Suggested Changes Tracker](docs/SUGGESTED_CHANGES.md)
- [Engineering Workflow](docs/ENGINEERING_WORKFLOW.md)
- [GitHub Issues](https://github.com/gtpooniwala/personal-agent/issues)

## License

MIT. See [LICENSE](LICENSE).
