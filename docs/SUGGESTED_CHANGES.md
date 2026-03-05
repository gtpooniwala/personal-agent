# Suggested Changes Tracker

Last updated: March 5, 2026

This file tracks the planned work with live GitHub issue links.
Status values: `todo`, `in_progress`, `done`, `blocked`.

## Milestones
- [01 Foundation Hardening](https://github.com/gtpooniwala/personal-agent/milestone/1)
- [02 Runtime Migration Core](https://github.com/gtpooniwala/personal-agent/milestone/2)
- [03 Workflow Automation](https://github.com/gtpooniwala/personal-agent/milestone/3)
- [Backlog / Future](https://github.com/gtpooniwala/personal-agent/milestone/4)

## Foundation (Pre-Migration)
| Priority | Status | Change | Issue |
|---|---|---|---|
| P0 | todo | Replace calculator `eval(...)` with safe expression evaluator | [#7](https://github.com/gtpooniwala/personal-agent/issues/7) |
| P0 | todo | Remove XSS-prone dynamic `innerHTML` rendering in frontend | [#8](https://github.com/gtpooniwala/personal-agent/issues/8) |
| P0 | todo | Fix upload failure path with uninitialized `document_id` | [#9](https://github.com/gtpooniwala/personal-agent/issues/9) |
| P1 | todo | Make local test workflow runnable; reduce skip-only green runs | [#10](https://github.com/gtpooniwala/personal-agent/issues/10) |
| P1 | todo | Add baseline observability (structured logs + runtime counters) | [#11](https://github.com/gtpooniwala/personal-agent/issues/11) |
| P1 | todo | Gate Gmail tool by dependency/config readiness | [#12](https://github.com/gtpooniwala/personal-agent/issues/12) |
| P2 | todo | Cleanup frontend rough edges and duplicate utility paths | [#13](https://github.com/gtpooniwala/personal-agent/issues/13) |

## Long-Running Runtime Migration (OpenClaw-lite Direction)
| Priority | Status | Change | Issue |
|---|---|---|---|
| P0 | todo | Architecture design doc for long-running runtime | [#14](https://github.com/gtpooniwala/personal-agent/issues/14) |
| P0 | todo | Add run lifecycle schema (`runs`, `run_events`, `leases`) | [#15](https://github.com/gtpooniwala/personal-agent/issues/15) |
| P0 | todo | Implement runtime worker queue with per-session serialization | [#16](https://github.com/gtpooniwala/personal-agent/issues/16) |
| P0 | todo | Convert chat API to submit-run + status/events model | [#17](https://github.com/gtpooniwala/personal-agent/issues/17) |
| P1 | todo | Add scheduler/heartbeat for autonomous workflows | [#18](https://github.com/gtpooniwala/personal-agent/issues/18) |
| P1 | todo | Add runtime evals for lifecycle/retry/session isolation | [#19](https://github.com/gtpooniwala/personal-agent/issues/19) |

## Future Backlog (Existing Product Ideas)
| Priority | Status | Idea | Issue |
|---|---|---|---|
| P3 | todo | Chat naming polish | [#1](https://github.com/gtpooniwala/personal-agent/issues/1) |
| P3 | todo | Internet search integration expansion | [#2](https://github.com/gtpooniwala/personal-agent/issues/2) |
| P3 | todo | Email integration | [#3](https://github.com/gtpooniwala/personal-agent/issues/3) |
| P3 | todo | Calendar integration | [#4](https://github.com/gtpooniwala/personal-agent/issues/4) |
| P3 | todo | Task manager integration | [#5](https://github.com/gtpooniwala/personal-agent/issues/5) |
| P3 | todo | Memory feature expansion | [#6](https://github.com/gtpooniwala/personal-agent/issues/6) |

## Notes
- This file is now synced to live issue tracking.
- If GitHub Project board access is added later, these issues can be batch-imported to that board.
- Implementation process is enforced via:
  - [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md)
  - CI checks in `.github/workflows/`
  - PR template requiring issue-closing keywords
