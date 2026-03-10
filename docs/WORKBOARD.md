# Workboard

Last updated: March 10, 2026

## How To Use This File
This is the execution board an agent should follow.

Default loop:
1. Start with the first unchecked item in `Recommended Order`.
2. Land the smallest stable change that moves that item forward.
3. Run repo checks and any relevant evals.
4. Update the linked issue plus this file and [`ROADMAP.md`](ROADMAP.md).

Important rule:
- This board tracks merged `main` behavior, not unmerged branches or stale issue state.
- When updating it in a PR, write the content to match the state that will be true once that PR is merged to `main`.

## Current Status
- Core async runtime is in place: durable `runs`, `run_events`, and `leases`; async `POST /chat` and `POST /runs`; polling via `GET /runs/{id}/status` and `GET /runs/{id}/events`.
- Blocking orchestration work has already been moved off the FastAPI event loop into a bounded worker pool as the `#51` migration step.
- Foreground orchestration now builds explicit request-scoped execution context, so per-run state no longer lives implicitly on the long-lived orchestrator instance.
- Runtime support services are in place: orphan recovery heartbeat, scheduled task loop, scheduled task CRUD/API, and runtime shutdown wiring.
- Normal-path tool selection is model-owned, the backend SSE stream exists, foreground orchestration is request-scoped, and the frontend now adopts the SSE stream with polling fallback after the recent `#101`, `#104`, `#106`, and `#122` work.
- External trigger framework is now landed (#88): `ExternalTrigger` registry, `TriggerEvent` deduplication, `TriggerDispatcher` service, webhook receiver stubs, and trigger CRUD routes.
- Frontend migration, document workflow clarity, Gmail Docker readiness, conversation naming, config validation, and runtime eval harness work are already landed.
- The remaining follow-up debt is narrower now: retry/fallback cleanup, transport deduplication, product-correctness cleanup, durable follow-up work, and true end-to-end async execution.

## Recommended Order

### Core Runtime And Orchestrator
- [ ] `todo` Add retry policy for transient orchestrator and LLM execution failures ([#120](https://github.com/gtpooniwala/personal-agent/issues/120))
- [ ] `todo` Revisit and potentially remove degraded fallback behavior after retry policy lands ([#119](https://github.com/gtpooniwala/personal-agent/issues/119))
- [ ] `todo` Define the long-term lifecycle contract for the execution plane, shutdown behavior, and in-flight run handling ([#102](https://github.com/gtpooniwala/personal-agent/issues/102))
- [ ] `todo` Separate background follow-up budget from foreground run attempts ([#109](https://github.com/gtpooniwala/personal-agent/issues/109))
- [ ] `todo` Persist follow-up work such as summarisation as queued task types instead of `asyncio.create_task(...)` ([#105](https://github.com/gtpooniwala/personal-agent/issues/105))
- [ ] `todo` Investigate true async orchestration/runtime paths instead of thread or sync islands ([#103](https://github.com/gtpooniwala/personal-agent/issues/103))

### Product, Transport, And Prompting Follow-Ups
- [x] `done` Adopt the SSE run stream in the frontend while keeping fallback behavior ([#122](https://github.com/gtpooniwala/personal-agent/issues/122))
- [ ] `todo` Deduplicate overlapping polling and SSE run-progress transport logic ([#121](https://github.com/gtpooniwala/personal-agent/issues/121))
- [ ] `todo` Add timeout/watchdog handling for stalled SSE run streams ([#130](https://github.com/gtpooniwala/personal-agent/issues/130))
- [x] `done` Stop conversation list reads from scheduling maintenance work ([#140](https://github.com/gtpooniwala/personal-agent/issues/140))
- [ ] `todo` Keep document-search responses scoped to selected documents ([#137](https://github.com/gtpooniwala/personal-agent/issues/137))
- [ ] `todo` Reassess whether `response_agent` should synthesize every final answer ([#138](https://github.com/gtpooniwala/personal-agent/issues/138))
- [ ] `todo` Make run timing fields and observability metrics truthful ([#139](https://github.com/gtpooniwala/personal-agent/issues/139))
- [ ] `todo` Extract non-run app helpers from `CoreOrchestrator` ([#134](https://github.com/gtpooniwala/personal-agent/issues/134))
- [ ] `todo` Strengthen prompt architecture and prompting contracts ([#68](https://github.com/gtpooniwala/personal-agent/issues/68))
- [ ] `todo` Improve document UX and RAG workflow clarity in the frontend ([#64](https://github.com/gtpooniwala/personal-agent/issues/64))

## Long-Running Agent Evolution Track

Decisions from OpenClaw comparison ([#153](https://github.com/gtpooniwala/personal-agent/issues/153)). See [`OPENCLAW_COMPARISON.md`](OPENCLAW_COMPARISON.md) for the full rationale.

Work this track after Phase 2 (product-correctness debt) is stable.

- [x] `done` OpenClaw architecture comparison and decisions ([#153](https://github.com/gtpooniwala/personal-agent/issues/153))
- [ ] `todo` GCS infrastructure — SDK, bucket, credential wiring; prerequisite for #154/#156 ([#79](https://github.com/gtpooniwala/personal-agent/issues/79))
- [ ] `todo` GCS-backed Markdown memory workspace — replaces scratchpad tool ([#154](https://github.com/gtpooniwala/personal-agent/issues/154))
- [ ] `todo` User-editable agent context files (AGENTS.md / USER.md, GCS-backed) ([#156](https://github.com/gtpooniwala/personal-agent/issues/156))
- [ ] `todo` Per-run tool assembly and dynamic tool policy layer ([#159](https://github.com/gtpooniwala/personal-agent/issues/159))
- [ ] `todo` Workflow isolation model — decouple run context from conversation_id; design during #105 ([#157](https://github.com/gtpooniwala/personal-agent/issues/157))
- [ ] `todo` MCP client integration for external tool extensibility ([#155](https://github.com/gtpooniwala/personal-agent/issues/155))

Note: LangGraph/LangChain migration (#103) is tracked in Core Runtime above; it is the long-term vehicle for true async orchestration and is low priority.

## Deployment Track
Work this track after the core runtime/orchestrator plan above is stable enough.

- [x] `done` GCP deployment architecture decisions finalized ([#81](https://github.com/gtpooniwala/personal-agent/issues/81))
- [ ] `todo` Cloud SQL production database setup ([#80](https://github.com/gtpooniwala/personal-agent/issues/80))
- [ ] `todo` Secret Manager integration for production secrets ([#82](https://github.com/gtpooniwala/personal-agent/issues/82))
- [x] `done` Bearer-token auth middleware for the FastAPI backend ([#83](https://github.com/gtpooniwala/personal-agent/issues/83))
- [ ] `todo` Deploy the Next.js frontend to Vercel ([#127](https://github.com/gtpooniwala/personal-agent/issues/127))
- [ ] `todo` Add a Next.js API proxy route for server-side bearer token injection ([#132](https://github.com/gtpooniwala/personal-agent/issues/132))
- [ ] `todo` Cloud Run service definition for the backend — deploy with auth already in image ([#85](https://github.com/gtpooniwala/personal-agent/issues/85))
- [ ] `todo` GitHub Actions CI/CD pipeline for Cloud Run deployment ([#86](https://github.com/gtpooniwala/personal-agent/issues/86))
- [ ] `todo` Update Gmail OAuth redirect URIs for production domains ([#129](https://github.com/gtpooniwala/personal-agent/issues/129))
- [ ] `todo` Migrate document storage from local filesystem to GCS — deferred; not a blocker for initial deploy ([#79](https://github.com/gtpooniwala/personal-agent/issues/79))
- [ ] `todo` Cold-start and min-instances tuning once the cloud baseline exists ([#87](https://github.com/gtpooniwala/personal-agent/issues/87))

## Trigger And Automation Track
Current scheduler primitives already exist. The remaining work is the external trigger layer.

- [x] `done` Scheduled task runner and scheduler-backed recurring runs ([#89](https://github.com/gtpooniwala/personal-agent/issues/89))
- [x] `done` External trigger framework: models, dispatcher, webhook stubs, CRUD routes ([#88](https://github.com/gtpooniwala/personal-agent/issues/88)) — Cloud Scheduler GCP job provisioning is still manual; no config checked in yet
- [ ] `todo` Add `trigger_run` for agent-spawned runs ([#90](https://github.com/gtpooniwala/personal-agent/issues/90))
- [ ] `todo` Email-triggered task execution ([#91](https://github.com/gtpooniwala/personal-agent/issues/91))
- [ ] `todo` Telegram bot integration for mobile task monitoring and triggering ([#92](https://github.com/gtpooniwala/personal-agent/issues/92))

## Completed Context
Keep this compressed. Use Git history and GitHub issues for detail.

- [x] `done` Foundation hardening and local workflow reliability: `#7` to `#13`, `#20`, `#40`
- [x] `done` Async runtime baseline: `#14` to `#19`
- [x] `done` Event-loop responsiveness migration step with worker-pool orchestration offload: `#51`
- [x] `done` Per-run orchestrator isolation, model-owned tool selection, backend SSE stream, and request-scoped orchestration: `#50`, `#72`, `#73`, `#74`, `#101`, `#104`, `#106`
- [x] `done` Scheduler-backed recurring task baseline: `#18`, `#89`
- [x] `done` Conversation list reads are now side-effect-free: `#140`
- [x] `done` Runtime lifecycle observability fields made truthful: `#139`
- [x] `done` Planning docs for cloud deployment and event-driven triggers: `#78`
- [x] `done` Managed worktree slot workflow: `#125` — PR #125 (`8cc7e41`)
- [x] `done` Frontend SSE run-progress client with polling fallback: `#122`

## Backlog
- [ ] `todo` Chat naming polish ([#1](https://github.com/gtpooniwala/personal-agent/issues/1))
- [ ] `todo` Internet search expansion ([#2](https://github.com/gtpooniwala/personal-agent/issues/2))
- [ ] `todo` Email integration beyond current Gmail read support ([#3](https://github.com/gtpooniwala/personal-agent/issues/3))
- [ ] `todo` Calendar integration ([#4](https://github.com/gtpooniwala/personal-agent/issues/4))
- [ ] `todo` Task manager integration ([#5](https://github.com/gtpooniwala/personal-agent/issues/5))
- [ ] `todo` Memory feature expansion ([#6](https://github.com/gtpooniwala/personal-agent/issues/6))

## Notes
- Keep items small enough to land in one commit when possible.
- Prefer one GitHub issue per item, linked directly above.
- Status source of truth for execution tracking is this file plus [`ROADMAP.md`](ROADMAP.md).
- Issue taxonomy and issue-creation rules live in [`ISSUE_MANAGEMENT.md`](ISSUE_MANAGEMENT.md).
- Follow the branch/worktree/PR rules in [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md).
- Use [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md) for implementation detail.
