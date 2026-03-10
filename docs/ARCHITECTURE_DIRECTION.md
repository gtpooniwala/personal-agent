# Architecture Direction: PA vs OpenClaw Model

Last updated: March 10, 2026
Based on: [OPENCLAW_ARCHITECTURE_DEEP_DIVE.md](OPENCLAW_ARCHITECTURE_DEEP_DIVE.md)

## The question

Personal Agent is incomplete. OpenClaw is a more mature personal agent with a different
architectural shape. Should PA refactor toward OpenClaw's model, or stay with its current
structure and expand it deliberately?

This document answers that question with a clear recommendation.

---

## What the two architectures fundamentally are

**Personal Agent's model:** A classical three-tier web application. Clients (Next.js) talk
to a stateless API server (FastAPI) over REST. All state lives in a relational database
(PostgreSQL). Execution is async with a thread pool for blocking Python work. The database
is the source of truth for everything: conversations, runs, events, leases, schedules.

**OpenClaw's model:** A monolithic always-on daemon. There is no frontend/backend separation.
All clients connect over WebSocket to a single long-running process that owns channels,
session state, and execution. State is stored in JSON and JSONL files. Execution is purely
async on a single Node.js event loop. The process being alive is the source of truth for
in-flight work.

These are not just implementation differences — they reflect different **deployment assumptions**:
- OpenClaw assumes a machine that stays on (Raspberry Pi, Mac mini, home server).
- PA assumes a cloud-deployed stateless service (Cloud Run, scale-to-zero, multiple instances).

That deployment assumption is the most important factor in this analysis.

---

## PA's architectural strengths (where it is ahead)

### 1. Durable state is the right default for cloud

PA's PostgreSQL run ledger means a crashed process leaves nothing behind except fully
recoverable state. The heartbeat service sweeps orphaned runs. Scheduled tasks survive
restarts. Every in-flight run can be inspected after the fact.

OpenClaw's in-memory queue means a crash loses all queued and in-flight work, silently.
This is acceptable when a process runs on a dedicated machine with supervised restart.
On Cloud Run (scale-to-zero, cold starts, potential preemption), it would be unacceptable.

**This is a structural PA advantage that should never be given up.**

### 2. Three-tier separation scales better

PA's frontend is a Next.js deployment (Vercel). The backend is a Python service (Cloud Run).
They are independently deployable, independently scalable. The frontend can change without
redeploying the backend, and vice versa.

OpenClaw's monolithic gateway means every change touches everything. The frontend (WebChat)
is served by the same process as the channel connectors, scheduler, and agent runtime.
Updating the frontend means restarting the daemon, which drops all active sessions.

For PA's target deployment (Vercel + Cloud Run), the three-tier model is the natural fit.

### 3. REST + SSE is the right API model for a web client

OpenClaw's WebSocket protocol is designed for clients that need server-push across a
long-lived connection — messaging apps, always-on dashboards. PA's web client is a
page-refresh-tolerant React app. HTTP request/response + SSE streaming covers the same
use cases without the complexity of WS state management, reconnect handling, and
device pairing.

PA already has SSE with backlog replay. That solves the only hard part of streaming without
adopting the WS protocol.

### 4. Relational schema is more powerful for history and queries

OpenClaw stores sessions as JSONL files. Querying "all sessions from the last week" or
"all runs that called the gmail tool" requires reading and parsing files. PostgreSQL gives
you indexed queries, foreign keys, and aggregations for free.

For a personal agent that accumulates years of conversation history, document uploads,
and run records, a relational schema is strictly better than flat files for anything beyond
simple append-and-read.

---

## OpenClaw's structural advantages PA does not currently have

### 1. Async I/O everywhere — no thread pool complexity

Node.js async is frictionless. OpenClaw never needs to think about whether work is blocking
because all LLM calls, file I/O, and HTTP calls are non-blocking by default. PA's thread pool
(`OrchestrationExecutionPlane`) is a genuine source of complexity: executor lifecycle,
context var propagation, blocking-in-async risk, concurrency cap tuning.

**Implication for PA:** This is a Python problem, not a PA-specific design choice. Moving to
a different language to fix it would be a complete rewrite. The right path is issue #103
(investigate true async paths), which would reduce reliance on the thread pool over time.
This is a long-term improvement, not a refactor trigger.

### 2. Tool policy pipeline

OpenClaw's per-turn tool assembly with owner/group/agent/depth/sandbox filtering is
architecturally cleaner than PA's static registry with document-gating. PA has no way to
restrict tools based on who sent the message, what context the run is in, or what
sub-agent depth is active.

**Implication for PA:** This matters more as PA adds automation (sub-agents, external
triggers, scheduled tasks that could be triggered by external events). A flat "all tools
available" policy is fine for single-user interactive chat but becomes a safety concern for
autonomous background runs. This is not a reason to refactor the whole system — it is a
specific capability to add to the tool registry.

### 3. Session key as a first-class isolation primitive

OpenClaw's session key is a flexible, composable string that determines everything about
isolation: which transcript file, which lane, which session store entry. This allows
`cron:<jobId>`, `subagent:<parentKey>:<uuid>`, and `agent:<agentId>:<mainKey>` to exist
uniformly without any special-casing in the runtime.

PA does not have this. A run is always tied to a `conversation_id`. There is no concept
of an ephemeral or system-owned context that does not appear in a user conversation.

**Implication for PA:** This is the core of the "isolated task execution" problem (#157 /
addressed in #105 design). PA needs a concept of a "system run" — a run that is not attached
to a user conversation. This can be designed within the current schema (add a nullable
`system_context` flag or a dedicated system conversation per task type) without adopting
OpenClaw's session key model wholesale.

### 4. Workspace-native memory and user-editable context files

OpenClaw's Markdown-first memory and AGENTS.md/SOUL.md/USER.md workspace files are more
accessible than PA's DB-backed scratchpad. A user can open a file in a text editor and
change how the agent behaves. They can commit the workspace to git for backup and versioning.
PA requires either a UI or direct DB access to modify agent behavior.

**Implication for PA:** This is the clearest adaptation worth making immediately. It does
not require any architectural change — it just adds a filesystem layer that the backend reads
at session start. The DB scratchpad and workspace files can coexist during transition.

---

## What would a "refactor toward OpenClaw" actually require?

To genuinely adopt OpenClaw's architecture, PA would need to:

1. **Rewrite in TypeScript/Node.js.** OpenClaw's async model, tool definitions, and plugin
   system are all deeply TypeScript. The thread pool, LangGraph, and LangChain are
   Python-specific. This is a complete rewrite of the backend.

2. **Replace PostgreSQL with files.** Sessions → JSONL, cron jobs → JSON files, memory →
   SQLite. Lose: relational queries, foreign keys, cursor-paginated event streams, structured
   run history.

3. **Replace REST + SSE with WebSocket.** The frontend would need to adopt the WS protocol.
   Vercel-hosted Next.js would lose easy server-side request isolation.

4. **Adopt the always-on daemon model.** Cloud Run's scale-to-zero would no longer work
   because the in-memory queue requires process continuity. Would need a persistent VM or
   Cloud Run min-instances=1 (cost change).

5. **Replace the durable run ledger with an in-memory queue.** Lose: crash recovery, orphan
   detection, observable history, cursor-based event replay.

None of these changes make PA better at what it is trying to be. They all move PA away from
cloud-native deployability toward a home-server model. That is the wrong direction.

---

## Recommendation: stay with PA's architecture; adopt specific patterns selectively

**PA's current architecture is correct for its deployment target and product goals.**

The three-tier REST + PostgreSQL model is not a weakness to be overcome — it is the right
choice for a cloud-deployed, crash-recoverable, observable personal agent. The durable run
ledger is a genuine architectural advantage over OpenClaw. The REST API is the right contract
for a web frontend.

The incompleteness of PA is not an architectural problem. PA is missing features, not
suffering from wrong decisions. The features it is missing (memory, workspace files, tool
policy, background task isolation, sub-agents, triggers) can all be added within the current
architecture.

**What to adopt from OpenClaw, and how:**

| OpenClaw pattern | Adopt as | Within current architecture? |
|---|---|---|
| Markdown memory files | New filesystem layer alongside DB | Yes — backend reads files at session start |
| User-editable context files | AGENTS.md / USER.md in backend/data | Yes — inject into system prompt at run start |
| Pre-compaction memory flush | Prompt injection before context limit | Yes — LangGraph hook |
| Tool policy pipeline | Policy layer in ToolRegistry / per-run assembly | Yes — extend existing registry |
| Isolated task execution | System conversation concept or run flag | Yes — schema extension |
| Sub-agents | sessions_spawn tool + sub-run tracking | Yes — new runtime feature on existing run model |
| MCP client | Python MCP client registered as tool source | Yes — new tool source, not a new architecture |
| Run cancellation | Cancellation endpoint + cooperative check in LangGraph | Yes — new endpoint + signal |

None of these require a rewrite. None require replacing the database, the transport, or the
deployment model. They are features to be added to an existing, correctly-shaped system.

**What to explicitly not do:**

- Do not rewrite the backend in TypeScript to "be more like OpenClaw."
- Do not replace PostgreSQL with JSONL files.
- Do not adopt the WebSocket control plane.
- Do not move away from the Cloud Run deployment model.
- Do not make the process "always-on" as a hard requirement.
- Do not build the Plugin ecosystem / ClawHub distribution until there is a clear need.

---

## The one genuine risk: incomplete features creating technical debt

PA is in an incomplete state, which means some current design decisions are placeholders
rather than final choices. The risk is not that the architecture is wrong, but that
unfinished features accumulate in ways that make the right decisions harder later.

The two highest-risk gaps currently:

**1. In-process background tasks (`asyncio.create_task`).**
If PA's background work stays as ephemeral coroutines indefinitely, it will become harder
to reason about resource consumption, retry behavior, and system shutdown. This is the
most urgent structural incompleteness. Addressing it (#105, #109) aligns PA with its own
architectural goals — it is not a gap relative to OpenClaw, it is a gap relative to what PA
is supposed to be.

**2. Scheduled tasks injecting into user conversations.**
As PA gains more automation (external triggers, agent-spawned tasks, richer scheduling),
the assumption that every run belongs to a user conversation will become a bottleneck.
Designing the "system run" or "isolated context" concept as part of the queued jobs work
(#105) removes this constraint cleanly. Deferring it will require retrofitting later.

Neither of these is an argument for a different architecture — they are arguments for
finishing the current one correctly.

---

## Verdict

**Stick with PA's structure. Expand it selectively.**

PA's architecture is right. The deployment model (Cloud Run + Vercel), the state model
(PostgreSQL), the transport (REST + SSE), and the execution model (async + thread pool)
are all well-suited to what PA is trying to be.

OpenClaw is a mature, well-designed system that has optimized for a different set of
constraints (always-on daemon, multi-channel inbox, single-process home server). Its
architectural patterns are worth studying, but its architectural choices are not worth
copying wholesale.

The features PA needs in the near term — durable background tasks, workspace memory,
workspace context files, tool policy, isolated task execution, and sub-agents — are all
additive features that fit naturally into PA's existing structure. None of them require
questioning the database, the transport, the language, or the deployment model.

Build on what is here. Finish what is incomplete. Adopt specific patterns from OpenClaw
where they add clear value without architectural lock-in.

---

## Related docs

- [OPENCLAW_ARCHITECTURE_DEEP_DIVE.md](OPENCLAW_ARCHITECTURE_DEEP_DIVE.md) — full technical comparison
- [OPENCLAW_COMPARISON.md](OPENCLAW_COMPARISON.md) — port/adapt/defer/reject decision table
- [ROADMAP.md](ROADMAP.md) — PA evolution roadmap
- [ARCHITECTURE.md](ARCHITECTURE.md) — PA current architecture
