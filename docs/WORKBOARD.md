# Workboard

Last updated: March 9, 2026

## How To Use This File
This is the execution board an agent should follow.

Default loop:
1. Start with the first unchecked item in `Recommended Order`.
2. Land the smallest stable change that moves that item forward.
3. Run repo checks and any relevant evals.
4. Update the linked issue plus this file and [`ROADMAP.md`](ROADMAP.md).

Important rule:
- This board tracks merged `main` behavior, not unmerged branches or stale issue state.

## Current Status
- Core async runtime is in place: durable `runs`, `run_events`, and `leases`; async `POST /chat` and `POST /runs`; polling via `GET /runs/{id}/status` and `GET /runs/{id}/events`.
- Blocking orchestration work has already been moved off the FastAPI event loop into a bounded worker pool as the `#51` migration step.
- Foreground orchestration now builds explicit request-scoped execution context, so per-run state no longer lives implicitly on the long-lived orchestrator instance.
- Runtime support services are in place: orphan recovery heartbeat, scheduled task loop, scheduled task CRUD/API, and runtime shutdown wiring.
- Frontend migration, Gmail Docker readiness, conversation naming, config validation, and runtime eval harness work are already landed.
- The architecture still has important follow-up debt: mixed LLM plus rule-based tool routing, in-process follow-up tasks, no final lifecycle policy for in-flight/background work, no SSE stream, and true end-to-end async execution is still future work.

## Recommended Order

### Core Runtime And Orchestrator
- [ ] `todo` Let the orchestrator LLM own normal tool selection and reduce rule-based routing ([#101](https://github.com/gtpooniwala/personal-agent/issues/101))
- [ ] `todo` Define the long-term lifecycle contract for the execution plane, shutdown behavior, and in-flight run handling ([#102](https://github.com/gtpooniwala/personal-agent/issues/102))
- [ ] `todo` Separate background follow-up budget from foreground run attempts ([#109](https://github.com/gtpooniwala/personal-agent/issues/109))
- [ ] `todo` Persist follow-up work such as summarisation as queued task types instead of `asyncio.create_task(...)` ([#105](https://github.com/gtpooniwala/personal-agent/issues/105))
- [ ] `todo` Investigate true async orchestration/runtime paths instead of thread or sync islands ([#103](https://github.com/gtpooniwala/personal-agent/issues/103))
- [ ] `todo` Add SSE streaming on top of the existing run/event store ([#104](https://github.com/gtpooniwala/personal-agent/issues/104))

### Product And Prompting Follow-Ups
- [ ] `todo` Strengthen prompt architecture and prompting contracts ([#68](https://github.com/gtpooniwala/personal-agent/issues/68))
- [ ] `todo` Improve document UX and RAG workflow clarity in the frontend ([#64](https://github.com/gtpooniwala/personal-agent/issues/64))

## Deployment Track
Work this track after the core runtime/orchestrator plan above is stable enough.

- [ ] `todo` Keep the GCP ADR current and finalize remaining deployment decisions ([#81](https://github.com/gtpooniwala/personal-agent/issues/81))
- [ ] `todo` Cloud SQL production database setup ([#80](https://github.com/gtpooniwala/personal-agent/issues/80))
- [ ] `todo` Secret Manager integration for production secrets ([#82](https://github.com/gtpooniwala/personal-agent/issues/82))
- [ ] `todo` Migrate document storage from local filesystem to GCS ([#79](https://github.com/gtpooniwala/personal-agent/issues/79))
- [ ] `todo` Cloud Run service definitions for backend and frontend ([#85](https://github.com/gtpooniwala/personal-agent/issues/85))
- [ ] `todo` IAP setup for personal cloud authentication ([#83](https://github.com/gtpooniwala/personal-agent/issues/83))
- [ ] `todo` GitHub Actions CI/CD pipeline for Cloud Run deployment ([#86](https://github.com/gtpooniwala/personal-agent/issues/86))
- [ ] `todo` Cold-start and min-instances tuning once the cloud baseline exists ([#87](https://github.com/gtpooniwala/personal-agent/issues/87))

## Trigger And Automation Track
Current scheduler primitives already exist. The remaining work is the external trigger layer.

- [x] `done` Scheduled task runner and scheduler-backed recurring runs ([#89](https://github.com/gtpooniwala/personal-agent/issues/89))
- [ ] `todo` Event trigger framework for external trigger types ([#88](https://github.com/gtpooniwala/personal-agent/issues/88))
- [ ] `todo` Add `trigger_run` for agent-spawned runs ([#90](https://github.com/gtpooniwala/personal-agent/issues/90))
- [ ] `todo` Email-triggered task execution ([#91](https://github.com/gtpooniwala/personal-agent/issues/91))
- [ ] `todo` Telegram bot integration for mobile task monitoring and triggering ([#92](https://github.com/gtpooniwala/personal-agent/issues/92))

## Completed Context
Keep this compressed. Use Git history and GitHub issues for detail.

- [x] `done` Foundation hardening and local workflow reliability: `#7` to `#13`, `#20`, `#40`
- [x] `done` Async runtime baseline: `#14` to `#19`
- [x] `done` Event-loop responsiveness migration step with worker-pool orchestration offload: `#51`
- [x] `done` Per-run orchestrator isolation and runtime correctness follow-ups: `#50`, `#72`, `#73`, `#74`
- [x] `done` Foreground request-scoped orchestrator execution to remove implicit per-run instance state: `#106`
- [x] `done` Scheduler-backed recurring task baseline: `#18`, `#89`
- [x] `done` Planning docs for cloud deployment and event-driven triggers: `#78`

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
