# Workboard

Last updated: March 8, 2026

## How This Is Used
This file is the AI execution board for this repo.

Workflow:
1. Pick the top item from `Now`.
2. Implement in a small, stable change.
3. Run tests/repo-checks and any relevant local LLM/workflow evals.
4. Commit and push.
5. Update GitHub issue and move the item state in this file.

## Status Legend
- `todo`
- `in_progress`
- `blocked`
- `done`

## Now (Parallel Tracks)

### Test Coverage
- [x] `done` Add schema validation tests for agent_config.yaml ([#73](https://github.com/gtpooniwala/personal-agent/issues/73))
- [x] `done` Unit tests for check_conversation_maintenance and async_generate_title retry ([#74](https://github.com/gtpooniwala/personal-agent/issues/74))

### Orchestrator Hardening
- [ ] `todo` Isolate orchestrator state per async run ([#50](https://github.com/gtpooniwala/personal-agent/issues/50))
- [ ] `todo` Move blocking orchestration work off event loop ([#51](https://github.com/gtpooniwala/personal-agent/issues/51))

## Next

## Migration Track
- [x] `done` Publish migration architecture contract + PR decomposition for long-running runtime ([#14](https://github.com/gtpooniwala/personal-agent/issues/14))
- [x] `done` Add run lifecycle schema (`runs`, `run_events`, `leases`) ([#15](https://github.com/gtpooniwala/personal-agent/issues/15))
- [x] `done` Deliver async submission contracts for `/chat` and `/runs` plus status/events endpoints ([#17](https://github.com/gtpooniwala/personal-agent/issues/17))
- [x] `done` Implement runtime worker queue with per-session serialization ([#16](https://github.com/gtpooniwala/personal-agent/issues/16))
- [x] `done` Add scheduler/heartbeat for autonomous workflows ([#18](https://github.com/gtpooniwala/personal-agent/issues/18))
- [x] `done` Add runtime evals for lifecycle/retry/session isolation ([#19](https://github.com/gtpooniwala/personal-agent/issues/19))
- [ ] `todo` Make summarisation tool non-blocking in async path ([#28](https://github.com/gtpooniwala/personal-agent/issues/28))
- [ ] `todo` Remove import-time global warning filter side effect ([#29](https://github.com/gtpooniwala/personal-agent/issues/29))
- [x] `done` Build real LLM/workflow evaluation harness (separate from deterministic repo checks) ([#23](https://github.com/gtpooniwala/personal-agent/issues/23))
- [x] `done` Upgrade to latest LangChain/LangGraph stack (deferred major migration) ([#22](https://github.com/gtpooniwala/personal-agent/issues/22))

## Backlog

### Cloud Deployment (GCP)
- [ ] `todo` Migrate document storage from local filesystem to GCS ([#79](https://github.com/gtpooniwala/personal-agent/issues/79))
- [ ] `todo` Cloud SQL setup and production database configuration ([#80](https://github.com/gtpooniwala/personal-agent/issues/80))
- [ ] `todo` GCP deployment architecture decision record ([#81](https://github.com/gtpooniwala/personal-agent/issues/81))
- [ ] `todo` Secret Manager integration for production API keys ([#82](https://github.com/gtpooniwala/personal-agent/issues/82))
- [ ] `todo` IAP setup for personal cloud authentication ([#83](https://github.com/gtpooniwala/personal-agent/issues/83))
- [ ] `todo` Cloud Run service definitions for backend and frontend ([#85](https://github.com/gtpooniwala/personal-agent/issues/85))
- [ ] `todo` GitHub Actions CI/CD pipeline for Cloud Run deployment ([#86](https://github.com/gtpooniwala/personal-agent/issues/86))
- [ ] `todo` Cold start optimization and min-instances strategy ([#87](https://github.com/gtpooniwala/personal-agent/issues/87))

### Event-Driven Triggers + Mobile
- [ ] `todo` Event trigger framework — unified infrastructure for external triggers ([#88](https://github.com/gtpooniwala/personal-agent/issues/88))
- [ ] `todo` Scheduled task runner — cron-like recurring agent runs ([#89](https://github.com/gtpooniwala/personal-agent/issues/89)) — *extends #18*
- [ ] `todo` Task-to-task chaining — trigger_run tool for agent-spawned runs ([#90](https://github.com/gtpooniwala/personal-agent/issues/90))
- [ ] `todo` Email-triggered task execution ([#91](https://github.com/gtpooniwala/personal-agent/issues/91))
- [ ] `todo` Telegram bot integration for mobile task monitoring and triggering ([#92](https://github.com/gtpooniwala/personal-agent/issues/92))

### General Backlog
- [ ] `todo` Chat naming polish ([#1](https://github.com/gtpooniwala/personal-agent/issues/1))
- [ ] `todo` Internet search integration expansion ([#2](https://github.com/gtpooniwala/personal-agent/issues/2))
- [ ] `todo` Email integration ([#3](https://github.com/gtpooniwala/personal-agent/issues/3))
- [ ] `todo` Calendar integration ([#4](https://github.com/gtpooniwala/personal-agent/issues/4))
- [ ] `todo` Task manager integration ([#5](https://github.com/gtpooniwala/personal-agent/issues/5))
- [ ] `todo` Memory feature expansion ([#6](https://github.com/gtpooniwala/personal-agent/issues/6))

## Done
- [x] `done` Replace calculator `eval` with safe parser/evaluator ([#7](https://github.com/gtpooniwala/personal-agent/issues/7))
- [x] `done` Remove XSS-prone `innerHTML` rendering in chat/conversation/document UIs ([#8](https://github.com/gtpooniwala/personal-agent/issues/8))
- [x] `done` Fix upload error path referencing uninitialized `document_id` ([#9](https://github.com/gtpooniwala/personal-agent/issues/9))
- [x] `done` Make local test workflow runnable and reduce skip-only passes ([#10](https://github.com/gtpooniwala/personal-agent/issues/10))
- [x] `done` Add baseline observability and core runtime counters ([#11](https://github.com/gtpooniwala/personal-agent/issues/11))
- [x] `done` Make Gmail tool optional in active tool list unless configured ([#12](https://github.com/gtpooniwala/personal-agent/issues/12))
- [x] `done` Cleanup frontend rough edges and duplicate utility logic ([#13](https://github.com/gtpooniwala/personal-agent/issues/13))
- [x] `done` Publish migration architecture contract + PR decomposition ([#14](https://github.com/gtpooniwala/personal-agent/issues/14))
- [x] `done` Enforce branch/worktree/PR policy checks ([#20](https://github.com/gtpooniwala/personal-agent/issues/20))
- [x] `done` Upgrade to latest LangChain/LangGraph stack ([#22](https://github.com/gtpooniwala/personal-agent/issues/22))
- [x] `done` Build real LLM/workflow evaluation harness ([#23](https://github.com/gtpooniwala/personal-agent/issues/23))
- [x] `done` Move frontend from static HTML/JS to Next.js ([#24](https://github.com/gtpooniwala/personal-agent/issues/24))
- [x] `done` Legacy module cleanup + import hygiene baseline eval
- [x] `done` README architecture/setup refresh
- [x] `done` Fix Gmail auth flow and dependency packaging ([#40](https://github.com/gtpooniwala/personal-agent/issues/40))
- [x] `done` Guard Enter key send during IME composition ([#30](https://github.com/gtpooniwala/personal-agent/issues/30))
- [x] `done` Prevent cross-conversation message race on send ([#31](https://github.com/gtpooniwala/personal-agent/issues/31))
- [x] `done` Robust async conversation auto-naming ([#72](https://github.com/gtpooniwala/personal-agent/issues/72))
- [x] `done` GCP deployment and event-driven triggers planning docs ([#78](https://github.com/gtpooniwala/personal-agent/issues/78))

## Notes
- Keep items small enough to land in one commit when possible.
- Prefer one GitHub issue per item, linked directly above.
- Status source of truth for execution tracking is this file + [`ROADMAP.md`](ROADMAP.md).
- Deprecated status docs removed: `PROJECT_STATUS.md` and `SUGGESTED_CHANGES.md`.
- Milestone alignment:
- `01 Foundation Hardening`: #7-#13, #40
- `02 Runtime Migration Core`: #14-#17
- `03 Workflow Automation`: #18-#19
- `Backlog / Future`: #1-#6, #78-#83, #85-#92
- Follow branch/worktree/PR policy in [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md).
