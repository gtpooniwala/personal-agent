# Features Overview

This file is a capability inventory, not a marketing snapshot. It lists what exists today and how mature each area is.

## Implemented Core Platform
- Async runtime submission and polling via `/chat`, `/runs`, `/runs/{id}/status`, and `/runs/{id}/events`
- Durable run ledger with retries, leases, and orphan recovery
- Next.js frontend for chat, conversations, documents, and runtime status
- PostgreSQL-backed persistence for conversations, documents, embeddings, counters, runs, and scheduled tasks
- LangGraph-based orchestration with tool binding and response synthesis

## Implemented User-Facing Tools

### Always Available
- Calculator
- Current time
- Scratchpad
- User profile memory

### Context Or Config Dependent
- Document search and RAG over uploaded PDFs
- Internet search
- Gmail read integration when credentials and dependencies are present

### Internal Helper Tools Or Flows
- Response synthesis
- Conversation summarisation
- Conversation title generation

## Implemented Runtime Support
- Per-conversation serialization via leases
- Retry loop and terminal run state recording
- Heartbeat orphan sweep
- Scheduled recurring task storage and dispatch
- Runtime counters and Langfuse-compatible observability hooks
- External trigger framework: `ExternalTrigger` registry, `TriggerEvent` deduplication log, `TriggerDispatcher` service, and webhook receiver + CRUD routes

## Current Maturity Notes
- The runtime contract itself is real and usable.
- Normal tool selection is owned by the orchestrator LLM from the currently exposed tool set.
- Deterministic code is limited to capability gating and honest failure boundaries.
- Some background work is still in-process rather than durable.
- SSE streaming is live end-to-end; the UI uses SSE with a polling fallback.
- Trigger webhook receivers (`/triggers/telegram`, `/triggers/email`, `/triggers/poll`) are stubbed — actual Telegram and email parsing land in #92 and #91.

## Placeholder Or Planned Capability Areas
- Task-to-task chaining with `trigger_run` (#90)
- Email-triggered runs (#91)
- Telegram bot integration (#92)
- Workflow matching algorithm for `_resolve_conversation()` in `TriggerDispatcher`
- Calendar and task-manager integrations
- Multi-user auth and tenant isolation
- Cloud deployment hardening

## Where To Go Next
- For current execution order, read [`WORKBOARD.md`](WORKBOARD.md).
- For sequencing rationale, read [`ROADMAP.md`](ROADMAP.md).
- For feature-specific behavior, read the docs under [`features/`](features/).
