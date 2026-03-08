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

## Current Maturity Notes
- The runtime contract itself is real and usable.
- Tool selection is still partly split between LLM behavior and deterministic fallback branches.
- Some background work is still in-process rather than durable.
- Streaming updates are not implemented yet; the UI relies on polling.

## Placeholder Or Planned Capability Areas
- Task-to-task chaining with `trigger_run`
- External trigger framework
- Email-triggered runs
- Telegram/mobile interaction layer
- Calendar and task-manager integrations
- Multi-user auth and tenant isolation
- Cloud deployment hardening

## Where To Go Next
- For current execution order, read [`WORKBOARD.md`](WORKBOARD.md).
- For sequencing rationale, read [`ROADMAP.md`](ROADMAP.md).
- For feature-specific behavior, read the docs under [`features/`](features/).
