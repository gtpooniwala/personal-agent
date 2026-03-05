# Workboard

Last updated: March 5, 2026

## How This Is Used
This file is the AI execution board for this repo.

Workflow:
1. Pick the top item from `Now`.
2. Implement in a small, stable change.
3. Run tests/eval relevant to the change.
4. Commit and push.
5. Update GitHub issue and move the item state in this file.

## Status Legend
- `todo`
- `in_progress`
- `blocked`
- `done`

## Now
- [ ] `todo` Replace calculator `eval` with safe parser/evaluator ([#7](https://github.com/gtpooniwala/personal-agent/issues/7))
- [ ] `todo` Fix upload error path referencing uninitialized `document_id` ([#9](https://github.com/gtpooniwala/personal-agent/issues/9))
- [ ] `todo` Remove XSS-prone `innerHTML` rendering in chat/conversation/document UIs ([#8](https://github.com/gtpooniwala/personal-agent/issues/8))
- [ ] `todo` Make local test workflow runnable and reduce skip-only passes ([#10](https://github.com/gtpooniwala/personal-agent/issues/10))

## Next
- [ ] `todo` Add baseline observability and core runtime counters ([#11](https://github.com/gtpooniwala/personal-agent/issues/11))
- [ ] `todo` Make Gmail tool optional in active tool list unless configured ([#12](https://github.com/gtpooniwala/personal-agent/issues/12))
- [ ] `todo` Cleanup frontend rough edges and duplicate utility logic ([#13](https://github.com/gtpooniwala/personal-agent/issues/13))
- [ ] `todo` Write migration architecture design doc ([#14](https://github.com/gtpooniwala/personal-agent/issues/14))

## Migration Track
- [ ] `todo` Add run lifecycle schema (`runs`, `run_events`, `leases`) ([#15](https://github.com/gtpooniwala/personal-agent/issues/15))
- [ ] `todo` Implement runtime worker queue with per-session serialization ([#16](https://github.com/gtpooniwala/personal-agent/issues/16))
- [ ] `todo` Convert chat API to submit-run + status/events endpoints ([#17](https://github.com/gtpooniwala/personal-agent/issues/17))
- [ ] `todo` Add scheduler/heartbeat for autonomous workflows ([#18](https://github.com/gtpooniwala/personal-agent/issues/18))
- [ ] `todo` Add runtime evals for lifecycle/retry/session isolation ([#19](https://github.com/gtpooniwala/personal-agent/issues/19))

## Backlog
- [ ] `todo` Chat naming polish ([#1](https://github.com/gtpooniwala/personal-agent/issues/1))
- [ ] `todo` Internet search integration expansion ([#2](https://github.com/gtpooniwala/personal-agent/issues/2))
- [ ] `todo` Email integration ([#3](https://github.com/gtpooniwala/personal-agent/issues/3))
- [ ] `todo` Calendar integration ([#4](https://github.com/gtpooniwala/personal-agent/issues/4))
- [ ] `todo` Task manager integration ([#5](https://github.com/gtpooniwala/personal-agent/issues/5))
- [ ] `todo` Memory feature expansion ([#6](https://github.com/gtpooniwala/personal-agent/issues/6))

## Done
- [x] `done` Legacy module cleanup + import hygiene baseline eval
- [x] `done` README architecture/setup refresh

## Notes
- Keep items small enough to land in one commit when possible.
- Prefer one GitHub issue per item, linked directly above.
- Milestone alignment:
- `01 Foundation Hardening`: #7-#13
- `02 Runtime Migration Core`: #14-#17
- `03 Workflow Automation`: #18-#19
- `Backlog / Future`: #1-#6
- Follow branch/worktree/PR policy in [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md).
