# Roadmap

Last updated: March 9, 2026

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
- Polling clients can observe progress through `GET /runs/{run_id}/status` and `GET /runs/{run_id}/events`, and the backend now also exposes `GET /runs/{run_id}/stream`.
- Per-conversation serialization, retry behavior, orphan recovery heartbeat, and scheduled task support are already implemented.
- The `#51` migration step is landed: runtime coordination stays on the event loop while blocking orchestration attempts run on a bounded worker pool.
- Normal-path tool selection is now model-owned from the bound tool set; the old handwritten router is no longer the primary orchestration path.
- Foreground orchestration now runs through request-scoped execution context rather than shared per-run instance state.
- Frontend document workflow clarity and prompt/source-card UX have both already improved materially.
- Frontend is on Next.js and the local workflow, eval harness, naming behavior, and Gmail Docker path have all been tightened recently.

### What Still Matters Most
- Retry and degraded-fallback behavior still need a cleaner final contract now that normal-path routing is model-owned.
- The frontend still needs to prefer the SSE run stream and then deduplicate its fallback transport behavior.
- Some product-correctness cleanup remains around selected-document scoping, response synthesis layering, and truthful runtime metrics.
- Some follow-up work still runs as in-process background tasks instead of durable queued work.
- The runtime is responsive during blocking orchestration now, but it still relies on a worker-pool execution plane rather than true end-to-end async internals.
- Executor lifecycle policy and background execution budgeting still need a cleaner final contract.

## Recommended Execution Order

### Phase 1: Finish The Runtime Contract Cleanly
1. [#120](https://github.com/gtpooniwala/personal-agent/issues/120) Add explicit retry policy for transient orchestrator and provider failures.
2. [#119](https://github.com/gtpooniwala/personal-agent/issues/119) Reassess whether any degraded deterministic fallback still needs to exist after retries land.
3. [#122](https://github.com/gtpooniwala/personal-agent/issues/122) Adopt the SSE run stream in the frontend while preserving fallback behavior.
4. [#121](https://github.com/gtpooniwala/personal-agent/issues/121) Deduplicate overlapping polling and SSE transport logic.
5. [#130](https://github.com/gtpooniwala/personal-agent/issues/130) Add a watchdog for stalled SSE run streams.
6. [#102](https://github.com/gtpooniwala/personal-agent/issues/102) Define executor ownership and graceful shutdown behavior.
7. [#109](https://github.com/gtpooniwala/personal-agent/issues/109) Separate background execution budget from foreground run attempts.

Why this first:
- The main orchestration path is already much cleaner than it was before `#101` and `#106`; the remaining work is mostly contract cleanup.
- Streaming and retry behavior now sit directly on user-visible paths, so drift here is costlier than deeper refactors.
- It turns the post-`#51` runtime from "responsive and mostly correct" into "predictable and easier to debug."

### Phase 2: Fix Product-Correctness Debt On Top Of The New Runtime
1. [#137](https://github.com/gtpooniwala/personal-agent/issues/137) Keep document-search responses scoped to selected documents.
2. [#138](https://github.com/gtpooniwala/personal-agent/issues/138) Reassess whether `response_agent` should synthesize every final answer.
3. [#139](https://github.com/gtpooniwala/personal-agent/issues/139) Make run timing fields and observability metrics truthful.
4. [#134](https://github.com/gtpooniwala/personal-agent/issues/134) Extract non-run app helpers from `CoreOrchestrator`.
5. [#68](https://github.com/gtpooniwala/personal-agent/issues/68) Continue prompt architecture hardening.
6. [#64](https://github.com/gtpooniwala/personal-agent/issues/64) Continue document UX and RAG workflow follow-ups.

Why this second:
- Several of these are now clearer because the runtime and frontend transport foundations are already in place.
- They tighten the product contract without forcing a broad architectural migration first.
- They remove AI-style redundancy and hidden side effects that are now more obvious after the recent UX and runtime work.

### Phase 3: Continue The Deeper Runtime Migration
1. [#105](https://github.com/gtpooniwala/personal-agent/issues/105) Persist summarisation and other follow-up work as queued task types.
2. [#103](https://github.com/gtpooniwala/personal-agent/issues/103) Investigate true async runtime/orchestrator paths.
3. [#135](https://github.com/gtpooniwala/personal-agent/issues/135) Revisit whether remaining shared orchestrator dependencies should become fully injected/stateless.

Why this third:
- These are important, but they are less urgent than the contract and product-correctness cleanup above.
- They are more valuable once the current runtime behavior is smaller, cleaner, and easier to trust.

## Cloud Deployment Track
This remains a real goal, but it should build on the runtime order above rather than compete with it.

Key decisions finalized: Vercel for frontend hosting (free hobby tier, zero code changes), bearer token auth (not IAP; simpler for Vercel-hosted frontend), `min-instances=0` with Cloud Scheduler driving polling triggers via HTTP. See `docs/DEPLOYMENT.md`.

Already done:
- [#81](https://github.com/gtpooniwala/personal-agent/issues/81) GCP deployment architecture decisions finalized.

Recommended order:
1. [#80](https://github.com/gtpooniwala/personal-agent/issues/80) Cloud SQL production baseline.
2. [#82](https://github.com/gtpooniwala/personal-agent/issues/82) Secret Manager integration (includes `AGENT_API_KEY` for bearer token).
3. [#83](https://github.com/gtpooniwala/personal-agent/issues/83) Bearer-token auth middleware for the FastAPI backend (must land before backend deploy).
4. [#127](https://github.com/gtpooniwala/personal-agent/issues/127) Deploy the Next.js frontend to Vercel.
5. [#132](https://github.com/gtpooniwala/personal-agent/issues/132) Add a Next.js API proxy route for server-side bearer token injection.
6. [#85](https://github.com/gtpooniwala/personal-agent/issues/85) Cloud Run service definition for the backend (deploy with auth already in image).
7. [#86](https://github.com/gtpooniwala/personal-agent/issues/86) CI/CD deployment pipeline.
8. [#129](https://github.com/gtpooniwala/personal-agent/issues/129) Update Gmail OAuth redirect URIs for production domains.
9. [#88](https://github.com/gtpooniwala/personal-agent/issues/88) Event trigger framework + Cloud Scheduler provisioning (required for scale-to-zero polling).
10. [#79](https://github.com/gtpooniwala/personal-agent/issues/79) GCS-backed document storage (deferred; not a blocker for initial deploy).
11. [#87](https://github.com/gtpooniwala/personal-agent/issues/87) Cold-start and min-instances tuning (optional; `min-instances=0` is final).

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
- `#101`, `#104`, `#106`: model-owned normal tool selection, backend SSE run streaming, and request-scoped foreground orchestration.
- `#140`: conversation list reads are now side-effect-free.
- `#78`: deployment and trigger planning docs.
