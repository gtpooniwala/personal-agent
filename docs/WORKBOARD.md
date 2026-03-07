# Workboard

Last updated: March 7, 2026

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

### Frontend Correctness (Sequential)
- [ ] `todo` Fix Gmail auth flow and dependency packaging ([#40](https://github.com/gtpooniwala/personal-agent/issues/40))
- [ ] `todo` Prevent cross-conversation message race on send ([#31](https://github.com/gtpooniwala/personal-agent/issues/31))
- [ ] `todo` Guard Enter key send during IME composition ([#30](https://github.com/gtpooniwala/personal-agent/issues/30))

### Runtime Quality (Parallel)
- [ ] `todo` Add scheduler/heartbeat for autonomous workflows ([#18](https://github.com/gtpooniwala/personal-agent/issues/18)) — *parallel with #19*
- [ ] `todo` Add runtime evals for lifecycle/retry/session isolation ([#19](https://github.com/gtpooniwala/personal-agent/issues/19)) — *parallel with #18*

## Next

## Migration Track
- [x] `done` Publish migration architecture contract + PR decomposition for long-running runtime ([#14](https://github.com/gtpooniwala/personal-agent/issues/14))
- [x] `done` Add run lifecycle schema (`runs`, `run_events`, `leases`) ([#15](https://github.com/gtpooniwala/personal-agent/issues/15))
- [x] `done` Deliver async submission contracts for `/chat` and `/runs` plus status/events endpoints ([#17](https://github.com/gtpooniwala/personal-agent/issues/17))
- [x] `done` Implement runtime worker queue with per-session serialization ([#16](https://github.com/gtpooniwala/personal-agent/issues/16))
- [ ] `todo` Add scheduler/heartbeat for autonomous workflows ([#18](https://github.com/gtpooniwala/personal-agent/issues/18))
- [ ] `todo` Add runtime evals for lifecycle/retry/session isolation ([#19](https://github.com/gtpooniwala/personal-agent/issues/19))
- [ ] `todo` Make summarisation tool non-blocking in async path ([#28](https://github.com/gtpooniwala/personal-agent/issues/28))
- [ ] `todo` Remove import-time global warning filter side effect ([#29](https://github.com/gtpooniwala/personal-agent/issues/29))
- [x] `done` Build real LLM/workflow evaluation harness (separate from deterministic repo checks) ([#23](https://github.com/gtpooniwala/personal-agent/issues/23))
- [x] `done` Upgrade to latest LangChain/LangGraph stack (deferred major migration) ([#22](https://github.com/gtpooniwala/personal-agent/issues/22))

## Backlog
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

## Notes
- Keep items small enough to land in one commit when possible.
- Prefer one GitHub issue per item, linked directly above.
- Status source of truth for execution tracking is this file + [`ROADMAP.md`](ROADMAP.md).
- Deprecated status docs removed: `PROJECT_STATUS.md` and `SUGGESTED_CHANGES.md`.
- Milestone alignment:
- `01 Foundation Hardening`: #7-#13, #40
- `02 Runtime Migration Core`: #14-#17
- `03 Workflow Automation`: #18-#19
- `Backlog / Future`: #1-#6
- Follow branch/worktree/PR policy in [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md).
