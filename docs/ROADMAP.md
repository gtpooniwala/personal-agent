# Roadmap

Last updated: March 8, 2026

## Goal
Turn the repository from a strong local prototype into a durable personal-agent platform that an implementation agent can extend without rediscovering architecture intent each time.

That means:
- the runtime accepts work quickly and exposes durable progress,
- orchestration behavior is easier to reason about,
- background follow-up work is explicit and observable,
- the path to cloud deployment and event-driven automation is already sequenced.

## Current State

### What Is Already Landed
- Async run submission is the primary execution contract via `POST /chat` and `POST /runs`.
- Run state is durable in PostgreSQL-backed runtime tables: `runs`, `run_events`, and `leases`.
- Polling clients can observe progress through `GET /runs/{run_id}/status` and `GET /runs/{run_id}/events`.
- Per-conversation serialization, retry behavior, orphan recovery heartbeat, and scheduled task support are already implemented.
- The `#51` migration step is landed: runtime coordination stays on the event loop while blocking orchestration attempts run on a bounded worker pool.
- Frontend is on Next.js and the local workflow, eval harness, naming behavior, and Gmail Docker path have all been tightened recently.

### What Still Matters Most
- Tool-selection ownership is still split between the LangGraph agent and rule-based fallback logic.
- Some follow-up work still runs as in-process background tasks instead of durable queued work.
- The runtime is responsive during blocking orchestration now, but it still relies on a worker-pool execution plane rather than true end-to-end async internals.
- Executor lifecycle policy and background execution budgeting still need a cleaner final contract.

## Recommended Execution Order

### Phase 1: Make Runtime Ownership Clear
1. [#101](https://github.com/gtpooniwala/personal-agent/issues/101) Move normal tool selection fully into the orchestrator LLM contract.
2. [#102](https://github.com/gtpooniwala/personal-agent/issues/102) Define executor ownership and graceful shutdown behavior.
3. [#109](https://github.com/gtpooniwala/personal-agent/issues/109) Separate background execution budget from foreground run attempts.

Why this first:
- It removes the biggest reasoning ambiguity in the current architecture.
- It makes later runtime changes easier to test and document.
- It turns the post-`#51` worker-pool runtime from "responsive" into "predictable."

### Phase 2: Make Follow-Up Work Durable
1. [#105](https://github.com/gtpooniwala/personal-agent/issues/105) Persist summarisation and other follow-up work as queued task types.
2. [#106](https://github.com/gtpooniwala/personal-agent/issues/106) Refactor `CoreOrchestrator` toward stateless execution.
3. [#103](https://github.com/gtpooniwala/personal-agent/issues/103) Investigate true async runtime/orchestrator paths.

Why this second:
- It removes ephemeral behavior that is hard to observe and recover.
- It keeps concurrency decisions out of hidden in-memory task scheduling.
- It positions the runtime for broader automation and cloud hosting.

### Phase 3: Improve Client Experience On Top Of Stable Runtime
1. [#104](https://github.com/gtpooniwala/personal-agent/issues/104) Add SSE streaming while keeping polling as fallback.
2. [#64](https://github.com/gtpooniwala/personal-agent/issues/64) Improve document UX and RAG clarity.
3. [#68](https://github.com/gtpooniwala/personal-agent/issues/68) Continue prompt architecture hardening.

Why this third:
- Streaming and UX polish are more valuable once the underlying runtime contract is stable.
- Prompt and UX changes are safer after routing ownership is simplified.

## Cloud Deployment Track
This remains a real goal, but it should build on the runtime order above rather than compete with it.

Recommended order:
1. [#81](https://github.com/gtpooniwala/personal-agent/issues/81) Keep the GCP ADR current and resolve remaining design decisions.
2. [#80](https://github.com/gtpooniwala/personal-agent/issues/80) Cloud SQL production baseline.
3. [#82](https://github.com/gtpooniwala/personal-agent/issues/82) Secret Manager integration.
4. [#79](https://github.com/gtpooniwala/personal-agent/issues/79) GCS-backed document storage.
5. [#85](https://github.com/gtpooniwala/personal-agent/issues/85) Cloud Run service definitions.
6. [#83](https://github.com/gtpooniwala/personal-agent/issues/83) IAP and authentication boundary.
7. [#86](https://github.com/gtpooniwala/personal-agent/issues/86) CI/CD deployment pipeline.
8. [#87](https://github.com/gtpooniwala/personal-agent/issues/87) Cold-start and min-instances tuning.

## Event-Driven Automation Track
The runtime already includes scheduler primitives and scheduled tasks. The remaining work is the external trigger layer and mobile-facing surfaces.

Recommended order:
1. [#88](https://github.com/gtpooniwala/personal-agent/issues/88) Trigger framework and dispatcher.
2. [#90](https://github.com/gtpooniwala/personal-agent/issues/90) `trigger_run` for agent-spawned runs.
3. [#91](https://github.com/gtpooniwala/personal-agent/issues/91) Email-triggered execution.
4. [#92](https://github.com/gtpooniwala/personal-agent/issues/92) Telegram bot integration.

Already done:
- [#89](https://github.com/gtpooniwala/personal-agent/issues/89) Scheduled recurring task runner.

## Vision
The target shape is a personal agent with:
- durable runs and explicit background task types,
- orchestration policy owned primarily by prompt and tool contracts rather than ad hoc routing branches,
- optional streaming and richer trigger surfaces on top of the same run ledger,
- a cloud deployment path that stays simple enough for a single-user system.

## Compressed Completed Context
- `#7` to `#13`, `#20`, `#40`: baseline hardening and local workflow quality.
- `#14` to `#19`: async runtime design, storage, API contract, worker semantics, scheduler, and eval coverage.
- `#50`, `#51`, `#72`, `#73`, `#74`, `#89`: follow-up runtime isolation, worker-pool responsiveness, naming, validation, and recurring task support.
- `#78`: deployment and trigger planning docs.
