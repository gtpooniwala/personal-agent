# Project Status

Last updated: March 5, 2026

## Purpose
Single source of truth for current implementation status, known risks, and execution confidence.

## Current State Snapshot
- Branch health: `main` tracking `origin/main`
- Deterministic repository checks: `tests/run_repo_checks.py` passing (`12/12` on March 5, 2026)
- Unit test suite: present, but local run currently dependency-gated in bare environments
- Runtime profile: local-first FastAPI + LangGraph + SQLite + vanilla JS frontend
- Tracking system: GitHub labels + milestones + prioritized issue backlog established (`#7`-`#19` plus existing `#1`-`#6`)
- Migration architecture status: issue #14 documents the async runtime contract and PR decomposition for #15-#19.

## Implemented Features
| Area | Feature | Status | Confidence |
|---|---|---|---|
| API | Chat + conversation endpoints | Implemented | Medium |
| Runtime API | Run submission (`/runs`) + status/events | Design-doc only | Medium |
| Orchestration | LangGraph ReAct with tool registry | Implemented | Medium |
| Tools | Calculator, time, internet search | Implemented | Medium |
| Memory | Scratchpad + user profile memory | Implemented | Medium |
| Docs | PDF upload + retrieval (RAG) | Implemented | Medium |
| UX | Conversation/document management frontend | Implemented | Medium |
| Integrations | Gmail read | Conditional setup | Low |

Confidence rubric:
- `High`: covered by runnable tests/repo-checks and simple operational path
- `Medium`: implemented end-to-end, partial test confidence
- `Low`: setup-fragile, weakly tested, or known edge-case risk

## Known Gaps / Risks
- Single-user default paths (`user_id="default"`) across most flows.
- Shared mutable orchestrator instance at API module scope.
- Frontend inserts server/user content via `innerHTML` (XSS risk).
- Calculator uses `eval(...)` despite input validation.
- Upload failure path can reference `document_id` before assignment.
- Behavioral eval coverage is still limited; current repository checks are mostly static invariants.

## Immediate Priorities
1. Security and correctness fixes (`eval`, XSS, upload failure path).
2. Request-isolated orchestration state.
3. Publish and align migration documentation for async runtime.
4. Better test/eval signal (reduced skip reliance, behavioral checks).
5. Auth + multi-user isolation groundwork.

## Where Active Work Is Tracked
- Execution board: [`WORKBOARD.md`](WORKBOARD.md)
- Sequenced roadmap: [`ROADMAP.md`](ROADMAP.md)
- Atomic tasks: GitHub Issues
- Suggested changes index: [`SUGGESTED_CHANGES.md`](SUGGESTED_CHANGES.md)
