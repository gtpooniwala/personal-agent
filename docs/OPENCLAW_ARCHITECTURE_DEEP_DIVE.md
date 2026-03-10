# OpenClaw vs Personal Agent: Deep Architecture Comparison

Last updated: March 10, 2026
Companion to: [OPENCLAW_COMPARISON.md](OPENCLAW_COMPARISON.md)

This document is a technical deep-dive comparing the two codebases across five dimensions:
system boundaries and communication, scheduling and concurrency, task isolation, architectural
features, and tool architecture. It is written to be read as a reference for design decisions,
not as a feature wishlist.

---

## 1. System Boundaries, Frontend/Backend/DB, and Communication

### Personal Agent

**Topology:**

```
Browser (Next.js)
    │  HTTP REST + SSE
    ▼
FastAPI Backend (Python)
    │  SQLAlchemy
    ▼
PostgreSQL
```

Three distinct, independently deployable tiers. The frontend and backend are separate processes.
The frontend knows nothing about internal execution; it submits runs and reads events.

**Frontend responsibilities:**

- Renders conversations, messages, tool actions, and document state.
- Submits runs via `POST /chat` or `POST /runs`.
- Reads run progress via polling (`GET /runs/{id}/status`, `GET /runs/{id}/events`) or SSE
  (`GET /runs/{id}/stream`).
- Manages document upload and selection state.
- Has no direct DB access; everything goes through the backend API.

**Backend responsibilities:**

- HTTP routing, CORS, bearer-token auth middleware (all in FastAPI).
- Run lifecycle coordination: submission, event emission, retry, lease management (RuntimeService).
- Blocking LLM/tool execution offloaded to a thread pool (OrchestrationExecutionPlane).
- Conversation, document, and memory CRUD under `/api/v1/`.
- Scheduler polling loop for recurring tasks.
- Heartbeat service for orphan recovery.

**REST API surface:**

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | POST | Submit chat run, return run_id |
| `/runs` | POST | Submit generic run, return run_id |
| `/runs/{id}/status` | GET | Latest run lifecycle snapshot |
| `/runs/{id}/events` | GET | Cursor-paginated run event stream |
| `/runs/{id}/stream` | GET | SSE live run event stream |
| `/api/v1/conversations` | GET/POST | List or create conversations |
| `/api/v1/conversations/{id}` | GET/DELETE | Get or delete a conversation |
| `/api/v1/conversations/{id}/messages` | GET | Fetch conversation message history |
| `/api/v1/documents` | GET/POST | List documents or upload a new one |
| `/api/v1/documents/{id}` | DELETE | Delete a document |
| `/api/v1/tools` | GET | List available tools |
| `/api/v1/health` | GET | Health check |
| `/api/v1/scheduler/tasks` | GET/POST | List or create scheduled tasks |
| `/api/v1/scheduler/tasks/{id}` | PATCH/DELETE | Update or delete a scheduled task |

**Auth:** Single `AGENT_API_KEY` bearer token on all routes. Local development can run without
auth. No session cookies, no OAuth flows for the backend itself.

**Database schema (PostgreSQL):**

```
conversations
  id (PK)          title            created_at
  updated_at       user_id (future)

messages
  id (PK)          conversation_id (FK)   role
  content          timestamp              agent_actions (JSON)
  token_usage

memory_store                         ← scratchpad tool backing store
  id (PK)          conversation_id (FK)   key
  value            timestamp

documents
  id (PK)          filename               file_size
  content_type     processed              total_chunks
  summary          file_content (BLOB)    upload_date

document_chunks
  id (PK)          document_id (FK)       chunk_index
  content          embedding (BLOB)       embedding_model
  page_number

runs                                 ← durable run ledger
  id (PK)          conversation_id (FK)   status
  error            result                 attempt_count
  created_at       started_at             completed_at

run_events                           ← append-only event log
  id (autoincrement PK)  run_id (FK)      event_type
  status                 message          tool
  error                  payload          created_at

leases                               ← distributed serialization
  lease_key (PK)   owner_id               fencing_token
  acquired_at      expires_at

runtime_counters                     ← lightweight observability
  key (PK)         value              updated_at

scheduled_tasks                      ← cron-scheduled jobs
  id (PK)          name (unique)          conversation_id (FK)
  message          cron_expr              enabled
  next_run_at      last_run_at            last_run_id (FK → runs)
```

All state is in PostgreSQL. There is no file-based state (documents were previously filesystem;
are now DB BLOBs). The database is the single source of truth for everything: conversations,
messages, memory, documents, runs, scheduling, and leases.

---

### OpenClaw

**Topology:**

```
WebChat (static HTML)  ──┐
CLI                    ──┤  WebSocket
macOS/iOS/Android app  ──┤  (port 18789)
                         ▼
                   Gateway (Node.js daemon)
                         │
                    ┌────┴────┐
              JSONL files   JSON config
              (sessions)    (cron, store)
                         │
                      SQLite
                   (memory index)
```

There is no traditional frontend/backend/database separation. The Gateway **is** the backend,
the control plane, and the channel router all in one process. Clients connect to it over
WebSocket. There is no relational database. All persistence is file-based.

**Gateway responsibilities:**

- Owns all channel connections (WhatsApp, Telegram, Slack, Discord, and 16+ more). Each channel
  runs a connector inside the gateway process.
- Maintains a WebSocket server for all control-plane clients (web UI, CLI, mobile apps, nodes).
- Routes inbound messages to agents via bindings config.
- Manages device pairing and auth (signed challenge nonces, device tokens).
- Runs the CronService for scheduled jobs.
- Manages session state and transcript I/O.
- Executes agent runs directly (no separate execution process).
- Serves the WebChat static UI and canvas host over HTTP on the same port.

**WebSocket protocol (not REST):**

Clients do not call REST endpoints for the core agent functionality. All interaction is via WS
request/response frames:

```
Client → Server:  { type: "req", id, method, params }
Server → Client:  { type: "res", id, ok, payload | error }
Server → Client:  { type: "event", event, payload, seq? }     ← server-push
```

Key methods:

- `connect` (first frame, mandatory, includes auth challenge)
- `agent` (run an agent turn; response includes runId + streaming events)
- `send` (deliver a message to a channel)
- `status` / `health` / `sessions.list` (query operations)
- `cron.add` / `cron.list` / `cron.run` (scheduler management)

There are also HTTP endpoints for: WebChat static files, canvas host, OpenAI-compatible
completion endpoint (`/v1/chat/completions`), and probe/health checks. These are secondary.

**File-based persistence (no relational DB, no migrations):**

```
~/.openclaw/openclaw.json          ← all config
~/.openclaw/agents/<id>/
  sessions/sessions.json           ← session key → sessionId map
  sessions/<sessionId>.jsonl       ← per-session transcript (append-only)
  agent/auth-profiles.json         ← per-agent model auth credentials
  qmd/                             ← QMD memory search state (optional)
~/.openclaw/memory/<agentId>.sqlite ← vector memory index
~/.openclaw/cron/<jobId>.json      ← persistent cron jobs
~/.openclaw/credentials/           ← OAuth tokens, API keys
~/.openclaw/workspace/             ← agent workspace (Markdown files, skills)
  AGENTS.md  SOUL.md  USER.md      ← user-editable context files
  MEMORY.md                        ← curated long-term memory
  memory/YYYY-MM-DD.md             ← daily memory logs
  skills/                          ← workspace-local skills
```

No schema migrations. Structural changes are handled by in-process store migration code
that upgrades JSON files on startup.

---

### Key structural difference

PA is a classical three-tier web application. Every piece of state goes through PostgreSQL.
The frontend is a separate process. Clients are passive consumers of a REST API.

OpenClaw collapses all tiers into one long-running process. The "database" is a set of files
and SQLite indexes. There is no frontend/backend split — the gateway serves both. Clients
are active participants in a WebSocket protocol, not REST consumers. This is a deliberate
design: the gateway is meant to run as a daemon and never go down. REST is a poor fit for
that model because HTTP is request-scoped; WebSocket + server-push is better for an always-on
assistant.

---

## 2. Scheduling and Concurrency

### Personal Agent

**Concurrency model:**

```
FastAPI async event loop (single thread)
    │
    ├── I/O operations run here directly (DB queries, HTTP responses)
    │
    └── ThreadPoolExecutor (4 workers default)
           │
           └── Blocking LangGraph/Python execution runs here
                 Each worker runs asyncio.run() for the coroutine
```

Python's async/await does not help with CPU-bound or blocking library code. LangGraph, the
LLM SDK calls (even though they use async under the hood), and other orchestration work
are dispatched from the event loop into a bounded `ThreadPoolExecutor`. The event loop
calls `loop.run_in_executor(executor, ...)` to move work off the event loop, then awaits
the future. Each orchestration attempt runs in its own thread from the pool.

The thread pool has a hard cap (default 4 workers). More than 4 simultaneous orchestrations
will queue behind the pool. This cap prevents unbounded resource consumption but means
the concurrency ceiling is defined by this setting.

**Scheduling:**

`SchedulerService` runs an async polling loop (`asyncio.create_task`) that checks due
scheduled tasks every 30 seconds. Due tasks are dispatched by calling
`RuntimeService.submit_run()` with the task's `conversation_id` and `message`. The
scheduler uses a `leases` table row to prevent double-dispatch across concurrent workers.
After dispatching, `next_run_at` is advanced regardless of success to prevent tight
retry loops.

The scheduled task shares the same execution path as a user-submitted run. It appears
in the conversation's message history.

**Background tasks:**

Conversation summarization and title generation still use `asyncio.create_task()` directly
from within the orchestration path. These are fire-and-forget on the event loop and are
not durable — if the process restarts mid-summarization, the task is silently lost.

---

### OpenClaw

**Concurrency model:**

```
Node.js event loop (single thread)
    │
    └── All agent runs are async I/O tasks here
          No thread pool needed: LLM calls are async HTTP, no blocking work
```

Node.js is inherently async. All LLM API calls (`await fetch(...)`, streaming async iterators)
are non-blocking. There is no equivalent of "blocking orchestration work" that would need
to be moved to a thread pool. The entire agent turn — from receiving the inbound message
to streaming back tokens — happens on the event loop through async/await chaining.

This means OpenClaw can run multiple concurrent agent turns on the same thread without any
thread pool, as long as each turn is waiting on I/O (which they almost always are). The only
CPU-bound operations are token counting and schema validation, which are fast enough to stay
on the event loop.

**The command queue:**

Because multiple concurrent runs on the same session would corrupt the JSONL transcript,
OpenClaw uses an in-memory lane-aware queue to serialize work:

```
runEmbeddedPiAgent(params)
    │
    ├── enqueueSession(task)   ← session lane: "session:agent:main:dm:+1234"
    │       maxConcurrent = 1  ← only one active run per session at a time
    │
    └── enqueueGlobal(task)    ← global lane: "main" | "cron" | "subagent"
            maxConcurrent = 4/8 ← caps total parallel runs
```

Every agent run enqueues itself into two lanes simultaneously. The session lane guarantees
at most one active run per session. The global lane caps total system parallelism. The queue
is a pure JavaScript Map of Promise chains. No I/O, no DB — entirely in memory.

**What this means for durability:** The queue is process-local. If the gateway crashes, all
queued and in-flight work is gone with no recovery mechanism. Crash recovery relies entirely
on process reliability (launchd/systemd supervision) and the fact that clients can resend.

**Scheduling (CronService):**

The `CronService` manages persistent cron jobs stored as JSON files. It uses `setTimeout`-based
timers, not polling. When a job fires:

- **Main session mode:** injects a system event into the session's next heartbeat turn.
  The job shares the session with normal user messages.
- **Isolated mode:** calls `runCronIsolatedAgentTurn()`, which uses `cron:<jobId>` as the
  session key. This creates a completely separate JSONL transcript and session state. The
  run goes into the `cron` global lane, not `main`.

The session key is the entire isolation mechanism. `cron:<jobId>` is just a string that
maps to its own per-session lane and its own transcript file. No DB, no lease, no fencing.

---

### Key concurrency difference

| | Personal Agent | OpenClaw |
|---|---|---|
| Execution model | Async event loop + ThreadPoolExecutor | Single async event loop, no threads |
| Why threads are needed | LangGraph/Python execution is blocking | Node.js LLM calls are async, no blocking |
| Concurrency ceiling | Thread pool size (default 4) | Global lane maxConcurrent config |
| Session serialization | PostgreSQL lease (distributed, durable) | In-memory session lane (process-local) |
| Scheduling mechanism | DB polling every 30s, lease-protected | setTimeout timers, file-backed job store |
| Scheduled task durability | PostgreSQL row survives restarts | JSON file survives restarts; in-flight run does not |
| Background task durability | asyncio.create_task (ephemeral) | Not applicable (no in-process background tasks) |

The thread pool is not a weakness of PA's design — it is a necessary consequence of using
Python with blocking library code. PA has a genuinely more durable execution model for
everything that gets past the submission point (runs, events, leases all survive crashes).
OpenClaw compensates for its lack of durability with process reliability and idempotency
keys on submissions.

---

## 3. Task Isolation

### Personal Agent

**What "isolation" means in PA today:**

A run is identified by `run_id`. Its state is in the `runs` and `run_events` tables. Its
execution context is scoped by `conversation_id`: the orchestrator loads conversation history
from the `messages` table using that ID.

Isolation between different users' runs: each run has its own `run_id`, its own event log,
and its own lease key (`conversation:{conversation_id}`). Two runs on different conversations
never share state.

Isolation between foreground runs and background tasks: poor today. Summarization and title
generation use `asyncio.create_task()`, sharing the event loop with foreground runs and
the same thread pool slots (the executor is shared, tracked by issue #109).

Isolation between scheduled tasks and user conversations: poor today. `SchedulerService`
calls `submit_run()` with the task's `conversation_id`, so the scheduled task appears in
the user's conversation history alongside their own messages. The scheduled task message
is indistinguishable from user-submitted messages at the DB level.

**Statelessness:**

Each foreground run constructs a fresh `OrchestratorRunContext` dataclass:

```python
@dataclass(frozen=True)
class OrchestratorRunContext:
    user_request: str
    conversation_id: str
    selected_documents: Tuple[str, ...]
    condensed_history: Tuple[Dict[str, Any], ...]
    llm: Any
    run_registry: ToolRegistry   # cloned per-run
    run_agent: Any               # LangGraph agent built fresh per run
```

The `ToolRegistry` is cloned per-run using `clone_with_selected_documents()` so each run
gets its own registry instance. The LangGraph agent is built fresh (`create_react_agent`)
with an in-memory `MemorySaver` so no agent state leaks between runs. Conversation history
is loaded from the DB at run start and passed in as a frozen tuple. This is solid per-run
isolation for foreground runs.

The `CoreOrchestrator` itself is long-lived and shared across runs (one per process),
but it only holds: `user_id`, `llm` handle (stateless), and `tool_registry` (a baseline
from which per-run registries are cloned). There is no mutable per-run state on the
orchestrator instance.

**Where isolation breaks down today:**

1. Scheduled tasks inject into user conversations (design gap, tracked in #157 / addressed in #105 design).
2. Background follow-up tasks (summarization, title) are fire-and-forget coroutines that
   share event loop and executor budget with foreground runs (#109).
3. The `leases` table provides distributed serialization (one active run per conversation)
   but this is optimistic — a stale lease after a crash can block a conversation until
   heartbeat sweeps it (#102).

---

### OpenClaw

**What "isolation" means in OpenClaw:**

Isolation is purely by session key. Every agent run is associated with a session key, which
maps to a JSONL transcript file and a per-session lane in the command queue. Two runs with
different session keys cannot affect each other's transcript because they write to different
files and drain different session-lane queues.

```
Session key         →  Transcript file                →  Lane
─────────────────────────────────────────────────────────────
agent:main:main     →  .../main/sessions/<id>.jsonl   →  session:agent:main:main
cron:morning-brief  →  .../main/sessions/<id>.jsonl   →  session:cron:morning-brief
subagent:abc123     →  .../main/sessions/<id>.jsonl   →  session:subagent:abc123
```

**Statelessness:**

OpenClaw does not maintain a long-lived mutable orchestrator object. Each call to
`runEmbeddedPiAgent()` assembles its full execution context from scratch:

- Workspace directory resolved from config + session key + agentId
- Tool set assembled from pi-tools.ts + openclaw-tools.ts, filtered by tool policy
- System prompt built from workspace files + skills
- Auth profiles read from disk for the agentId
- Session transcript read from JSONL file and passed into the pi-mono agent runner

No shared mutable state across calls. Every run is effectively a pure function of its inputs
(config, session key, inbound message) plus the JSONL transcript on disk. Multiple concurrent
runs on different session keys are safe because they operate on different files and different
queue lanes.

**Sub-agent isolation:**

When a sub-agent is spawned via `sessions_spawn`, it gets:

- A new session key: `subagent:<parentSessionKey>:<uuid>` (or a named key)
- Its own JSONL transcript
- Its own per-session lane (`subagent` global lane, not `main`)
- A depth limit to prevent infinite nesting
- A registry entry in the `SubagentRegistry` for lifecycle tracking

The sub-agent shares the workspace with its parent (same filesystem directory) but not the
session transcript. It can be given a different tool policy. When the sub-agent completes,
the parent can receive its output via the announce flow.

**Where isolation is fragile:**

1. The workspace is shared across sessions for the same agent — all sessions read/write the
   same Markdown files. This is intentional (shared memory) but means a busy sub-agent
   writing to `memory/today.md` can be seen by a concurrent main session.
2. In-memory queue state is not replicated. A crash loses all queued and in-flight work.
3. Auth profile state is shared across sessions for the same agentId — `auth-profiles.json`
   is read and written by all concurrent sessions for that agent.

---

### Key isolation difference

| Concern | Personal Agent | OpenClaw |
|---|---|---|
| Per-run state | OrchestratorRunContext (frozen dataclass, cloned registry) | Everything assembled fresh from config + JSONL |
| Serialization mechanism | PostgreSQL lease (distributed, cross-process safe) | In-memory session lane (single-process only) |
| Scheduled task context | Shares conversation_id with user messages (gap) | Isolated session key per job |
| Sub-agent isolation | No sub-agent concept yet | Separate session key, transcript, lane, depth-limited |
| Crash-safe isolation | Yes — leases, heartbeat recovery, run events are durable | No — in-memory queue, JSONL is only transcript |
| Workspace isolation | N/A (no workspace concept) | Shared per-agent, not per-session |

PA's isolation model is safer across crashes and across processes (important for Cloud Run).
OpenClaw's isolation is simpler and more elegant for the single-process always-on daemon model.

---

## 4. Architectural Features

### Personal Agent: current feature inventory

**Core execution:**

- Async run submission (POST /chat, POST /runs) → durable run row
- Run event stream (append-only, cursor-paginated)
- SSE live stream with backlog replay on reconnect
- Per-conversation lease serialization (one active run per conversation)
- Retry with attempt count tracking (up to 3 attempts)
- Heartbeat sweep for orphaned runs

**Conversation management:**

- Full conversation and message history in PostgreSQL
- Automatic title generation (background, post-run)
- Automatic conversation summarization (background, post-run)
- Document upload + RAG (per-conversation document selection)

**Scheduling:**

- DB-backed scheduled tasks with cron expressions
- SchedulerService polling loop
- Per-task dispatch lease

**Planned but not yet implemented:**

- Durable queued task types for background work (#105)
- External trigger framework (#88)
- Sub-agents / agent-spawned runs (#90)
- Run cancellation (#158)
- MCP integration (#155)
- Workspace-native memory files (#154)

---

### OpenClaw: feature inventory

**Core execution:**

- Inbound message routing from any connected channel to the appropriate agent
- In-memory lane queue for serialization
- LLM agent turn via pi-mono embedded runner
- Streaming output back to channel (block streaming / preview streaming)
- Context compaction (automatic summarization + token pruning)
- Session pruning and retention policies

**Multi-channel inbox:**

- 20+ channel connectors (messaging: WhatsApp, Telegram, Slack, Discord, Signal, iMessage,
  and more; each with send/receive, typing indicators, reactions, attachments)
- Channel-aware tool availability (some tools only available on certain channels)
- Block streaming and preview streaming per-channel

**Scheduling and automation:**

- CronService with persistent jobs (main-session and isolated execution styles)
- Heartbeat runs (recurring agent check-ins on a configurable interval)
- Hook system: event-driven scripts for agent lifecycle events (/new, /reset, /stop, boot)
- Inbound webhooks for external trigger delivery
- BOOT.md startup ritual

**Multi-agent:**

- Multi-agent routing: multiple agent configs with different workspaces, bindings to route
  inbound by channel/peer/account
- Sub-agents: sessions_spawn tool spawns a child agent run with its own session
- Agent-to-agent messaging: sessions_send tool (opt-in, explicit allowlist)
- Sub-agent registry: lifecycle tracking, depth limits, announce flows
- Per-agent tool policy, sandbox configuration, workspace, and auth profiles

**Memory:**

- Markdown-native memory (MEMORY.md + daily logs)
- Hybrid BM25+vector search with temporal decay and MMR re-ranking
- Automatic pre-compaction memory flush
- Session transcript indexing (experimental)

**Skills and extensibility:**

- Skills: SKILL.md prompt-injection directories (bundled/managed/workspace precedence)
- Plugin API: npm packages that add tools, skills, hooks to the runtime
- MCP via mcporter bridge

**Operational:**

- `openclaw doctor` for health diagnostics
- `openclaw security audit` for multi-user security review
- In-chat `/status`, `/context list`, `/stop`, `/queue`, `/compact`
- Device pairing for multi-client trust management

---

### Architectural feature gap summary

The features PA is missing that OpenClaw has, grouped by whether they matter:

**High relevance for PA's goals:**

- Workspace-native memory files + pre-compaction flush (tracked: #154)
- User-editable context files (AGENTS.md / USER.md) (tracked: #156)
- Run cancellation (tracked: #158)
- MCP integration (tracked: #155)
- Isolated execution context for scheduled/background tasks (tracked: #105 design)

**Medium relevance, already roadmapped:**

- Durable queued background tasks (tracked: #105, #109)
- External trigger framework (tracked: #88)
- Sub-agent / agent-spawned runs (tracked: #90)
- Telegram channel (tracked: #92)

**Low relevance / intentionally deferred:**

- Multi-channel inbox (WhatsApp, Discord, etc.) — PA is web-UI-first
- Multi-agent routing — PA is single-user by design
- Plugin ecosystem / ClawHub — premature for current scope
- Device pairing — single-user, single client

---

## 5. Tool Architecture

### Personal Agent

**How tools are assembled:**

There is one `ToolRegistry` per `CoreOrchestrator` (one per process). It is initialized at
startup with all static tools. For each run, `clone_with_selected_documents()` creates a
shallow copy with document-dependent state refreshed for that run's selected documents.

```python
# Startup (once per process)
tool_registry = ToolRegistry(user_id="default")
# → calculator, time, scratchpad, internet_search, user_profile,
#   response_agent, summarisation_agent, gmail_read (optional)

# Per-run (foreground execution)
run_registry = tool_registry.clone_with_selected_documents(selected_docs)
# → same static tool instances + fresh SearchDocumentsTool if docs selected

# Tools exposed to LangGraph model:
available = run_registry.get_available_tools()
# → calculator, time, scratchpad, internet_search, user_profile, gmail_read?,
#    search_documents?  (capability gating only; model selects from these)
```

**Tool categories:**

| Category | Tools | Notes |
|---|---|---|
| Utility | calculator, current_time | Always available |
| Memory | scratchpad (KV read/write), user_profile | Always available |
| Search | internet_search, search_documents | search_documents conditional on doc selection |
| External | gmail_read | Conditional on credentials |
| Internal | response_agent, summarisation_agent | Not exposed to model; called by orchestrator |

**Tool policy:**

There is no runtime tool allow/deny policy. Tool availability is determined at registry
initialization time (environment/credentials) and at clone time (document selection). The
model sees the full available set and selects freely. There is no per-conversation or
per-context restriction mechanism.

**Tool definitions:**

Tools are Python classes inheriting from LangChain's `BaseTool` or a similar interface.
Schemas are defined in Python code. Tool descriptions and parameters live in the tool
class definition. Adding a new tool requires writing a Python class and registering it
in `ToolRegistry._initialize_tools()`.

**Extensibility:**

No plugin mechanism. No runtime tool registration from external sources. Tools are static.
The `register_tool()` and `unregister_tool()` methods exist but are unused in production.

---

### OpenClaw

**How tools are assembled:**

Tools are assembled fresh on each call to `runEmbeddedPiAgent()`. There is no shared tool
registry object. Instead, `pi-tools.ts` assembles the full tool set from several sources
and applies policy filtering before passing tools to the LLM:

```
runEmbeddedPiAgent(params)
  │
  ├── pi-mono tools (from pi-coding-agent):
  │     read, write, edit, exec, apply_patch, browser, process
  │
  ├── OpenClaw tools (createOpenClawTools):
  │     session_status, sessions_list, sessions_history, sessions_send,
  │     sessions_spawn, subagents, cron, message, gateway, browser,
  │     canvas, nodes, web_fetch, web_search, pdf, image, tts, agents_list
  │     + plugin tools (resolved from enabled plugins)
  │
  └── Tool policy pipeline (resolveEffectiveToolPolicy):
        → owner-only filter (elevated tools only for session owner)
        → group policy filter (exec/write/edit restricted in group chats)
        → per-agent allow/deny (agents.list[].tools.allow/deny)
        → subagent depth policy (restricted tool set for deeply nested agents)
        → sandbox wrapping (filesystem tools redirect to sandbox directory)
```

**Tool categories:**

| Category | Examples | Notes |
|---|---|---|
| Filesystem | read, write, edit, exec, apply_patch | From pi-mono; sandbox-aware |
| Session | sessions_spawn, sessions_send, sessions_list, session_status | Agent-to-agent capabilities |
| Scheduling | cron | Create/manage cron jobs from within agent turn |
| Messaging | message | Send messages to channels from within agent turn |
| Web | web_fetch, web_search | Web access tools |
| Media | image, pdf, tts, browser | Rich content tools |
| Compute | exec, process | Shell execution |
| Device | nodes, canvas | For connected devices and live canvas |
| Platform | gateway | Gateway management from within agent |
| External (plugin) | e.g. Spotify, Notion, GitHub issues | Loaded from enabled plugins |

**Tool policy: the key architectural difference**

OpenClaw has a multi-stage tool policy pipeline that runs at tool assembly time for every
agent turn:

1. **Owner-only filter**: "elevated" tools (exec, write, edit) are blocked for non-owner
   senders. In group chats, only the owner (the person who runs the gateway) can use
   destructive tools.

2. **Group policy filter**: In group chat sessions, a tighter tool policy applies by default.
   This prevents a random group member from triggering shell execution.

3. **Per-agent config**: `agents.list[].tools.allow` and `.deny` provide explicit include/
   exclude lists for each agent's tool set. A "family" agent can be restricted to `["read"]`
   only, completely excluding exec/write.

4. **Subagent depth policy**: Sub-agents at depth 2+ get a more restricted tool set to
   prevent runaway nested execution.

5. **Sandbox wrapping**: If sandboxing is enabled, filesystem tools are replaced with
   sandboxed variants that redirect reads/writes to the sandbox directory rather than the host.

**Skills: prompt-layer extensibility**

Skills are directories with a `SKILL.md` file. They do not add tools; they add usage
instructions for existing tools. When the agent starts, all active skills are loaded and
their content is injected into the system prompt. This teaches the agent conventions,
preferred workflows, and tool-specific guidance without changing the tool API.

Skills are loaded from three locations (workspace wins over managed over bundled), allowing
per-agent override. A skill can be gated by config key or environment variable, so it only
appears when relevant tools are available.

**Tool definitions: typed schemas**

Tools are defined with TypeBox schemas (`Type.Object`, `Type.String`, etc.). These schemas
are used both for LLM function-call descriptions and for runtime input validation. A tool
is a plain TypeScript object with a `name`, `description`, `schema`, and `execute` function.
The schema is the contract; the framework handles serialization.

Adding a new tool means writing a TypeScript object + TypeBox schema. The tool can be
registered via the plugin API without touching core code.

**Extensibility:**

The plugin API (`openclaw.plugin.json`) allows npm packages to register additional tools,
skills, and hooks at runtime without gateway code changes. MCP servers can be connected via
mcporter to add even more tools from the external MCP ecosystem.

---

### Key tool architecture difference

| | Personal Agent | OpenClaw |
|---|---|---|
| Registry lifetime | Process-level singleton, cloned per-run | Assembled fresh per agent turn |
| Tool definitions | Python classes (LangChain BaseTool) | TypeScript objects (TypeBox schema) |
| Context-sensitive policy | Document selection only | Full policy pipeline (owner, group, agent config, depth, sandbox) |
| Skills system | None — prompts in code only | SKILL.md directories, injected at session start |
| Plugin extensibility | None | Plugin API, ClawHub registry |
| MCP integration | Not yet | Via mcporter bridge |
| Tool for spawning agents | Not yet | sessions_spawn (sub-agents) |
| Tool for scheduling | Not yet | cron (create/manage cron jobs in-turn) |
| Tool for messaging | Not yet | message (send to any connected channel) |

The most architecturally significant difference is the tool policy pipeline. PA's model is
capability-gating (which tools are available depends on what's configured/selected). OpenClaw's
model is context-gating (which tools are available depends on who is asking, from where,
in which session type, at which sub-agent depth). This distinction matters when PA starts
supporting automation-triggered runs, sub-agents, or multi-user scenarios.

---

## Summary: What Makes Each Architecture What It Is

**Personal Agent** is architected for correctness and observability in a cloud-deployed,
single-user, web-UI-first assistant. Its strengths: durable state everywhere (PostgreSQL),
crash recovery, observable run events, clean frontend/backend separation, standard deployment
model (Cloud Run + Vercel). Its current gaps relative to a mature long-running agent: ephemeral
background tasks, no workspace-native memory, no tool policy beyond capability gating, no
sub-agent support, no external trigger surfaces.

**OpenClaw** is architected for always-on availability and maximum channel reach in a
single-process daemon model. Its strengths: zero-overhead concurrency (async Node.js), rich
channel integrations, sophisticated tool policy pipeline, workspace-native Markdown memory,
skills system, multi-agent support, plugin ecosystem. Its current gaps relative to PA: no
durable run ledger (crash = lost work), no distributed lease mechanism, no structured
frontend/backend separation (everything is in the gateway process), no relational schema
(harder to query cross-session history).

Neither is clearly better overall. They have optimized for different constraints. The
patterns worth bringing from OpenClaw into PA are those that do not require adopting its
fundamental daemon + file-storage architecture: Markdown memory, workspace context files,
tool policy pipeline, isolated task execution, and eventually sub-agent support.

---

## Related Docs

- [`OPENCLAW_COMPARISON.md`](OPENCLAW_COMPARISON.md) — decision table (port/adapt/defer/reject)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — PA current architecture
- [`ROADMAP.md`](ROADMAP.md) — PA evolution roadmap including selected adaptations
- [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md) — PA runtime migration history
