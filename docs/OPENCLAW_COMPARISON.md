# OpenClaw Architecture Comparison

Last updated: March 10, 2026 (revised)
Addresses: [#153](https://github.com/gtpooniwala/personal-agent/issues/153)

## Purpose

This document compares the current Personal Agent architecture against OpenClaw across the architectural dimensions that matter for a long-running personal agent. The goal is not to clone OpenClaw, but to make explicit decisions about which OpenClaw patterns are worth porting, adapting, deferring, or rejecting — and to create follow-up issues for the selected changes.

Both systems were analyzed from their current code and docs, not from memory or assumptions.

---

## Systems at a Glance

**Personal Agent (PA)** is a local-first single-user personal assistant with a FastAPI backend, LangGraph ReAct orchestrator, PostgreSQL-backed run/event/lease runtime, and a Next.js frontend. It supports persisted conversations, durable async runs, per-conversation serialization, document upload + RAG, internet search, scratchpad/profile memory, Gmail read, scheduled recurring tasks, and SSE run streaming.

**OpenClaw** is a TypeScript/Node.js personal agent platform running as an always-on daemon. Its architecture centers on a WebSocket gateway as a control plane, 20+ messaging channel integrations, a workspace-native Markdown memory system, a skills/hooks/cron automation layer, multi-agent routing, per-agent sandbox isolation, and a plugin ecosystem. It is terminal-first and primarily single-user, with optional multi-user support.

---

## Comparison by Dimension

### 1. Runtime and Control Plane

**Personal Agent today:**
FastAPI HTTP server with REST endpoints. Work is submitted via `POST /chat` and `POST /runs`, which return a `run_id` immediately. The runtime is request-oriented: clients submit and poll. SSE streaming is supported via `GET /runs/{run_id}/stream` with backlog replay on reconnect. Bearer-token auth protects all endpoints. The backend runs in a single process (Cloud Run target).

**OpenClaw approach:**
A single always-on WebSocket Gateway daemon per host, supervised by launchd or systemd. All channel connections and device pairing live in the gateway. Control-plane clients (macOS app, CLI, web UI) connect over WS. Typed WS API with requests, responses, and server-push events. Idempotency keys on side-effecting operations. Node clients (macOS/iOS/Android) register as WS peers with explicit capabilities.

**Gap and impact:**
OpenClaw's gateway is deeply coupled to its multi-channel messaging architecture, which PA does not have or need. PA's HTTP+SSE model works well for a web-UI-first single-user system. The always-on daemon concept is relevant for background automation, but PA on Cloud Run already handles process lifecycle differently.

**Decision: reject**
PA's HTTP+SSE control plane is the right fit. The WS gateway pattern is not worth porting because it is primarily useful for managing persistent channel connections and device pairing — neither of which applies to PA's web-UI-first design. PA should continue building on its existing runtime contract.

---

### 2. Execution Model and Durability

**Personal Agent today:**
PostgreSQL-backed run ledger (`runs`, `run_events`, `leases`). Lifecycle: `queued → running → succeeded/failed/retrying`. `run_events` is the append-only durable event stream. Per-conversation lease serialization prevents concurrent runs on the same conversation. `OrchestrationExecutionPlane` offloads blocking orchestration to a bounded worker pool. `HeartbeatService` sweeps orphaned runs. Some follow-up work (summarization, title generation) still uses `asyncio.create_task` rather than durable queued tasks.

**OpenClaw approach:**
In-process lane-aware FIFO queue with per-session serialization (one active run per session). No persistent run ledger — runs are transient in-memory. Session transcripts are JSONL on disk. Retry is per-request at the provider/HTTP layer, not per workflow step. The queue supports multiple modes: `steer` (inject into current run), `followup`/`collect` (hold for next turn), `interrupt` (abort and restart). Concurrency is controlled by `maxConcurrent` and lane caps.

**Gap and impact:**
PA's execution model is actually **more durable than OpenClaw's** on this dimension. PA's PostgreSQL-backed run ledger provides crash recovery, orphan detection, and observable progress that OpenClaw's in-memory queue does not. PA's remaining gap is not related to OpenClaw: it is the in-process `asyncio.create_task` follow-up work tracked in [#105](https://github.com/gtpooniwala/personal-agent/issues/105) and [#109](https://github.com/gtpooniwala/personal-agent/issues/109).

OpenClaw's queue mode concepts (`steer`, `collect`, `followup`) are worth noting as patterns for how to handle concurrent inbound messages, but PA's single-user web UI doesn't need these modes yet.

**Decision: reject (porting); PA is ahead here**
PA should not regress to in-memory queueing. Continue the existing roadmap: persist follow-up work as queued task types (#105), separate background budget from foreground attempts (#109). The durable run ledger is a PA strength.

---

### 3. Session Model

**Personal Agent today:**
Sessions correspond to conversations. PostgreSQL-backed `conversations` table with full message history. Per-conversation leases provide run serialization. Single-user — no session routing or isolation between users. Sessions are user-identified by conversation ID, not by sender/channel.

**OpenClaw approach:**
Sessions are mapped from inbound channel/peer pairs via configurable `dmScope` rules (`main`, `per-peer`, `per-channel-peer`, `per-account-channel-peer`). Session keys encode the agent, channel, and peer. JSONL transcripts stored per session. Session lifecycle policies: daily reset (4 AM by default), idle reset, per-type and per-channel overrides, manual reset via `/new`/`/reset`. Session pruning with retention policies (`pruneAfter`, `maxEntries`, `maxDiskBytes`). Session origin metadata.

**Gap and impact:**
The gap is large but intentional. OpenClaw's multi-channel session mapping and isolation are built for a different problem (multi-channel inbox routing to one personal assistant). PA's single-user web UI has one conversation model that is simpler and correct for its scope.

Session lifecycle policies (auto-reset, retention pruning) are potentially useful for PA if conversations accumulate unboundedly. This is already a latent concern but not an active problem.

**Decision: defer**
Session lifecycle / retention policies are worth revisiting when conversation accumulation becomes a real problem. Multi-channel session routing is out of scope for PA.

---

### 4. Memory Model

**Personal Agent today:**
Two memory mechanisms: (1) `scratchpad` tool — key-value pairs stored in PostgreSQL, read/write via tool calls; (2) `user_profile` tool — structured profile data stored in PostgreSQL. Document upload + RAG provides document-scoped semantic search (pgvector). The scratchpad and profile are agent-visible but not human-readable outside the DB. No temporal structure in memory. No automatic memory flush before context limits.

**OpenClaw approach:**
Memory is plain Markdown files in the agent workspace: `MEMORY.md` (curated long-term memory) and `memory/YYYY-MM-DD.md` (daily logs). The model reads and writes these files directly via `memory_get` and `memory_search` tools. `memory_search` uses hybrid BM25+vector search with optional MMR re-ranking (diversity) and temporal decay (recency boost with configurable half-life). Automatic pre-compaction memory flush: a silent agentic turn prompts the model to write durable notes before the context window compacts. Session transcripts can also be indexed (experimental).

**Gap and impact:**
This is a meaningful gap. PA's scratchpad is functional but has three weaknesses compared to OpenClaw's memory:
1. **Not human-readable or versionable.** DB rows are not inspectable without tooling. Markdown files are human-readable and git-committable.
2. **No temporal structure.** The scratchpad has no concept of recency. Temporal decay in OpenClaw ensures old notes don't outrank recent ones.
3. **No pre-compaction flush.** When PA's LangGraph context nears limits, memory is not explicitly written before compaction. Important context can be lost silently.

The Markdown-native memory pattern is directly applicable to PA's product goals and is low-effort to adopt.

**Decision: adapt**
Replace the scratchpad tool with a GCS-backed Markdown memory workspace:

- `MEMORY.md` (curated long-term memory) and `memory/YYYY-MM-DD.md` (daily logs) stored in GCS.
- GCS is the storage backend — not local filesystem (lost on cold start) and not PostgreSQL (not human-readable). Files survive Cloud Run restarts and can be read/edited outside the app.
- Expose `memory_get` and `memory_write` tools that operate on these files. Scratchpad tool is retired.
- Implement a pre-compaction memory flush prompt before context limits are hit.
- Longer-term: hybrid vector+BM25 search with temporal decay (tracked in #6).

Note: the `user_profile` tool is evaluated separately as part of [#156](https://github.com/gtpooniwala/personal-agent/issues/156).

See follow-up: [#154](https://github.com/gtpooniwala/personal-agent/issues/154). GCS infrastructure prerequisite: [#79](https://github.com/gtpooniwala/personal-agent/issues/79).

---

### 5. Tool System

**Personal Agent today:**
`ToolRegistry` with a bound tool set per run: calculator, time, document search (RAG), internet search, scratchpad, user profile, Gmail read, response agent, summarization agent. Document-scoped tool availability (doc-search only activates when documents are selected). Tool selection is model-owned (LangGraph). No per-conversation tool allow/deny. No sandboxed execution. No external tool extensibility standard.

**OpenClaw approach:**
TypeBox-typed first-class tools. Per-agent tool allow/deny lists. Optional Docker sandbox per agent with configurable scope. Agent-to-agent messaging tool. MCP bridge via `mcporter` for connecting external MCP servers. Plugin API for adding tools without core changes.

**Gap and impact:**
Three sub-gaps, each with different priority:

1. **Per-conversation tool policy** — PA has no mechanism to restrict tools for specific contexts (e.g., untrusted inputs, group scenarios). Not relevant for single-user PA today.
2. **Sandboxed execution** — Docker isolation for risky tool calls. Not relevant for personal single-user PA.
3. **MCP integration** — The Model Context Protocol is becoming the standard for connecting external tools and services. PA currently requires custom Python tool implementations for every integration. MCP would allow reusing a growing ecosystem of external tool servers without code changes.

**Decision:**

- **Adapt** per-run tool policy pipeline: replace static registry binding with a `build_tool_set(run_context)` function called at the start of each run. Policy controls which tools are available based on run type (interactive, scheduled, triggered, sub-agent), not just selected documents. See [#159](https://github.com/gtpooniwala/personal-agent/issues/159).
- **Adapt** MCP integration: add MCP client support so external MCP servers can register tools without custom Python implementations. See [#155](https://github.com/gtpooniwala/personal-agent/issues/155).
- **Defer** sandboxing (single-user, low priority).
- **Note on LangGraph migration (#103):** moving to a direct async Anthropic SDK loop makes per-run tool assembly straightforward — the tool list is a plain Python argument to each LLM call, not a LangChain binding step.

---

### 6. Skills and Prompt Extensibility

**Personal Agent today:**
No formal skills system. System prompts are embedded in Python code (`backend/orchestrator/prompts.py`). No user-editable prompt files. Prompt architecture is documented in `docs/PROMPT_ARCHITECTURE.md` but modifications require code changes. Existing pattern: `AGENTS.md`, `CLAUDE.md`, `PROMPT_ARCHITECTURE.md` describe the intent, but the actual prompt content lives in code, not in filesystem files the user can edit.

**OpenClaw approach:**
Workspace-native user-editable files: `AGENTS.md` (operating instructions), `SOUL.md` (persona/tone/boundaries), `USER.md` (user profile), `TOOLS.md` (tool conventions), `IDENTITY.md` (name/emoji). These files are loaded at the start of every session and injected into the agent context. Skills are `SKILL.md` directories (bundled/managed/workspace precedence) that teach the agent how to use specific tools or follow specific workflows. ClawHub provides a public skill registry. Skills can be gated by config and environment.

**Gap and impact:**
This gap is architecturally significant for long-running personal agents. PA currently requires code changes to modify agent behavior. OpenClaw's workspace file pattern means the user can edit `AGENTS.md` to change operating rules, `USER.md` to update their profile, or add a skill to teach the agent a new workflow — without touching code.

For PA, this translates to:
- The existing `scratchpad` and `user_profile` tools handle some of this (structured data), but not unstructured operating instructions or persona definitions.
- A user editing "how the agent should behave" should be a filesystem edit, not a DB transaction or code change.
- The skills concept (SKILL.md prompt-injection pattern) is directly applicable for teaching PA to use new tools or follow new workflows.

**Decision: adapt**
Adopt user-editable workspace context files for PA:
- `AGENTS.md` in the backend data directory for operating instructions.
- `USER.md` for user profile (complement/replace the structured profile tool).
- Load and inject these files at session start.
- For the skills system: adopt the SKILL.md pattern for extensible prompt injection without a full ClawHub integration. This is a lightweight way to extend tool behavior documentation without code changes.

See follow-up: [#156](https://github.com/gtpooniwala/personal-agent/issues/156).

---

### 7. Triggers, Scheduling, and Background Automation

**Personal Agent today:**
`SchedulerService` with PostgreSQL-backed scheduled tasks. Cron-like recurring task support (`next_run_at` advancement). Scheduled tasks are dispatched into the main runtime path using the task's conversation and message. External trigger framework planned but not yet implemented ([#88](https://github.com/gtpooniwala/personal-agent/issues/88)). No hooks/lifecycle event system. No inbound webhooks.

**OpenClaw approach:**
Persistent cron scheduler with two execution styles: (1) **main session** — enqueue a system event into the session's next heartbeat turn; (2) **isolated** — run a dedicated agent turn in a `cron:<jobId>` session, with optional delivery back to a channel. Hooks are event-driven scripts that fire on agent lifecycle events (`/new`, `/reset`, `/stop`, `agent:bootstrap`, gateway boot). Inbound webhooks for external trigger delivery. Heartbeat runs on a configurable interval. `BOOT.md` for gateway startup rituals.

**Gap and impact:**
PA's scheduler is functionally similar to OpenClaw's cron. The meaningful gap is:

1. **Isolated execution context per scheduled task** — PA's scheduler dispatches tasks into existing conversation context. OpenClaw's isolated cron session keeps each job's run state separate. This prevents scheduled tasks from polluting or being polluted by the user's active conversation history.
2. **Hook/lifecycle events** — PA has no event-driven automation hooks. OpenClaw's hooks enable patterns like saving session context before reset or triggering follow-up work when a session starts. These are useful but not urgent for PA.
3. **Inbound webhooks** — PA has no mechanism to accept external trigger payloads (e.g., Gmail push, Zapier webhook). This maps to the planned trigger framework (#88).

**Decision:**

- **Adapt** workflow isolation model: design a session/workflow context that decouples runs from `conversation_id`, so any run type (scheduled, triggered, sub-agent) can operate in an isolated context. The design should be resolved as part of the queued jobs architecture (#105). Three candidate approaches are documented in [#157](https://github.com/gtpooniwala/personal-agent/issues/157); final architecture decision deferred until #105 design is underway.
- **Defer** hooks: useful but not blocking; add after the trigger framework.
- **Defer** inbound webhooks: mapped to existing #88 (trigger framework), which is already in the roadmap.

---

### 8. Channel and Interface Surfaces

**Personal Agent today:**
Next.js web UI only. No messaging channel integrations. Document upload via web. Bearer-token auth for API. SSE run streaming. Telegram integration planned but not implemented ([#92](https://github.com/gtpooniwala/personal-agent/issues/92)).

**OpenClaw approach:**
20+ channel integrations: WhatsApp, Telegram, Slack, Discord, Signal, iMessage, BlueBubbles, IRC, Microsoft Teams, Matrix, Feishu, LINE, Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, WebChat. Native macOS/iOS/Android companion apps. Canvas for dynamic live UI. Each channel has per-account configuration, block streaming, preview streaming.

**Gap and impact:**
The gap is very large, but it is intentional by design. PA is a single-user local-first web assistant. The web UI serves its primary use case well. Adopting OpenClaw's channel architecture wholesale would introduce enormous complexity for marginal gain.

The most valuable addition from this dimension is Telegram, which provides mobile access without requiring a native app. This is already tracked as [#92](https://github.com/gtpooniwala/personal-agent/issues/92).

**Decision: defer all channels except Telegram**
Telegram (#92) is the right next channel addition for mobile access. All other channel integrations are out of scope for PA's current and near-term roadmap. PA should not adopt OpenClaw's multi-channel routing architecture.

---

### 9. Agent Isolation and Multi-Agent Support

**Personal Agent today:**
Single-user, single-agent. No formal agent isolation. No per-agent workspace, state directory, or auth profiles. All conversations share the same agent configuration and tool set.

**OpenClaw approach:**
Multiple isolated agents in one gateway process. Each agent has its own workspace (prompt files, memory, skills), state directory (auth profiles, model registry), and session store. Bindings route inbound messages to agents by channel/peer/account. Per-agent tool allow/deny and sandbox configuration. Agent-to-agent messaging tool (opt-in).

**Gap and impact:**
Large gap, intentionally so. PA is a personal assistant designed for one user. Multi-agent isolation is not a current requirement.

**Decision: reject**
PA should remain single-user, single-agent. If PA ever needs to serve multiple users or personas (e.g., a family scenario), OpenClaw's model shows the clear path: per-agent workspace + state dir + session store. But this is not a PA goal for the foreseeable future.

---

### 10. Observability, Safety, and Operational Controls

**Personal Agent today:**
`run_events` provides observable progress as an append-only stream (durable, cursor-paginated). `GET /runs/{id}/stream` SSE endpoint for live updates. Truthful timing fields on runs (#139 done). `HeartbeatService` for orphan recovery. Bearer-token auth with a single `AGENT_API_KEY`. No per-session send policy. No tool sandboxing. No security audit CLI.

**OpenClaw approach:**
Rich operational CLI: `openclaw status`, `openclaw doctor`, `openclaw security audit`, `/status` in-chat command, `/context list` to inspect context contributors. Per-session send policy (allow/deny rules). Tool allow/deny per agent. Optional Docker sandboxing. Device pairing with signed challenge nonces. In-chat `/stop` to abort current runs. Per-run idempotency keys.

**Gap and impact:**
PA's run observability (durable events, SSE stream) is strong and appropriate. The gaps are:
1. **In-context observability** — no equivalent of `/context list` to see what is in the current session context. Useful for debugging but not blocking.
2. **Operational health tooling** — no `doctor` equivalent. Useful for cloud deployment but can be deferred.
3. **In-chat abort** — no `/stop` command to abort a running run mid-stream. This is a real UX gap for long-running tasks.

**Decision:**
- **Adapt** in-chat run abort: add a `/stop` or abort mechanism for the frontend to cancel an active run. This is a product-correctness issue, not an architecture issue.
- **Defer** doctor/audit tooling: useful for cloud deployment phase, not urgent now.
- **Reject** device pairing and per-session send policy: out of scope for single-user personal assistant.

---

## Summary Table

| Dimension | PA Today | OpenClaw | Decision |
|---|---|---|---|
| Runtime / control plane | HTTP+SSE, REST API, PostgreSQL | WS Gateway daemon, device pairing | **reject** — PA's model is right |
| Execution model / durability | Durable run ledger (PostgreSQL), worker pool | In-memory FIFO queue, JSONL transcripts | **reject** (port) — PA is ahead here |
| Session model | Conversation-based, single-user | Multi-channel session routing, lifecycle policies | **defer** — retention policies only when needed |
| Memory model | Scratchpad (KV), profile (structured), RAG | Markdown-native files, hybrid BM25+vector, temporal decay, pre-compaction flush | **adapt** — GCS-backed Markdown memory, replace scratchpad |
| Tool system | ToolRegistry, model-owned selection | Typed tools, per-agent policy, sandbox, MCP | **adapt** per-run policy (#159) + MCP (#155); **defer** sandbox |
| Skills / prompt extensibility | Prompts in code, no user-editable files | Workspace files, SKILL.md, ClawHub | **adapt** — workspace context files + SKILL.md pattern |
| Triggers / scheduling | DB-backed scheduler, no hooks, no webhooks | Persistent cron (isolated/main), hooks, webhooks | **adapt** isolated task execution; **defer** hooks/webhooks |
| Channel surfaces | Next.js web UI only | 20+ channels, mobile apps | **defer** all except Telegram (#92) |
| Agent isolation / multi-agent | Single-user, single-agent | Per-agent workspace + state + sessions | **reject** — intentionally single-agent |
| Observability / safety | Durable events, SSE, bearer-token auth | Doctor CLI, audit, /stop, device pairing | **adapt** run abort; **defer** doctor/audit |

---

## OpenClaw Patterns Intentionally Not Adopted

The following OpenClaw patterns are worth documenting as rejected or out-of-scope so future contributors don't relitigate these decisions:

1. **WebSocket gateway with device pairing.** PA's HTTP+SSE is the right transport for a web-UI-first personal assistant. WS + device pairing adds complexity with no benefit for PA's architecture.
2. **Multi-agent routing with bindings.** PA is a single-user assistant. Multi-agent isolation and routing infrastructure is out of scope.
3. **20+ channel integrations.** PA's web UI is the primary interface. Wholesale multi-channel adoption would be a multi-month infrastructure investment with unclear personal value beyond Telegram.
4. **Docker sandboxing per agent.** Single-user personal assistant with user-controlled tools. No untrusted-input isolation requirement.
5. **ClawHub public skill registry.** PA does not need a public skills distribution network. Local workspace skills files are sufficient.
6. **Session dmScope / multi-user isolation.** PA is single-user. Session isolation for multiple senders is irrelevant.
7. **In-memory execution queue.** PA's durable PostgreSQL run ledger is a deliberate architectural advantage; reverting to in-memory queues would be a regression.

---

## Follow-Up Issues

The following issues should be created from this comparison:

### Selected for adaptation

| Issue | Title | Decision rationale |
|---|---|---|
| [#154](https://github.com/gtpooniwala/personal-agent/issues/154) | GCS-backed Markdown memory workspace (replaces scratchpad) | Adopt OpenClaw memory model — GCS storage, human-readable, versionable, prevents silent context loss |
| [#155](https://github.com/gtpooniwala/personal-agent/issues/155) | MCP client integration for external tool extensibility | Adopt MCP as the standard for connecting external tools without custom Python implementations |
| [#156](https://github.com/gtpooniwala/personal-agent/issues/156) | User-editable agent context files (AGENTS.md / USER.md, GCS-backed) | Adopt workspace-native prompt customization so agent behavior is configurable without code changes |
| [#157](https://github.com/gtpooniwala/personal-agent/issues/157) | Workflow isolation model — decouple run context from conversation_id | Design session/workflow isolation for all run types; final architecture decision deferred to #105 |
| [#159](https://github.com/gtpooniwala/personal-agent/issues/159) | Per-run tool assembly and dynamic tool policy layer | Replace static tool binding with per-run `build_tool_set(run_context)` for policy-aware tool scoping |

### Existing issues confirmed by this comparison

- [#92](https://github.com/gtpooniwala/personal-agent/issues/92) — Telegram bot (the right next channel surface; confirmed)
- [#105](https://github.com/gtpooniwala/personal-agent/issues/105) — Persist follow-up work as durable task types (OpenClaw comparison confirms value)
- [#109](https://github.com/gtpooniwala/personal-agent/issues/109) — Separate background execution budget (confirmed)
- [#88](https://github.com/gtpooniwala/personal-agent/issues/88) — Trigger framework (OpenClaw webhooks/hooks confirm direction)
- [#120](https://github.com/gtpooniwala/personal-agent/issues/120) — Retry policy (OpenClaw has per-request HTTP retry; PA needs per-workflow-step retry)

---

## Related Docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`WORKBOARD.md`](WORKBOARD.md)
- [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md)
