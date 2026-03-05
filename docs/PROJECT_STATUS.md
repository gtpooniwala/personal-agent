# Project Status

Last updated: March 5, 2026

## Purpose
Single source of truth for current implementation status, known risks, and execution confidence.

## Current State Snapshot
- Branch health: `main` tracking `origin/main`
- Static eval: `tests/run_eval.py` passing (`12/12` on March 5, 2026)
- Unit test suite: present, but local run currently dependency-gated in bare environments
- Runtime profile: local-first FastAPI + LangGraph + SQLite + vanilla JS frontend

## Implemented Features
| Area | Feature | Status | Confidence |
|---|---|---|---|
| API | Chat + conversation endpoints | Implemented | Medium |
| Orchestration | LangGraph ReAct with tool registry | Implemented | Medium |
| Tools | Calculator, time, internet search | Implemented | Medium |
| Memory | Scratchpad + user profile memory | Implemented | Medium |
| Docs | PDF upload + retrieval (RAG) | Implemented | Medium |
| UX | Conversation/document management frontend | Implemented | Medium |
| Integrations | Gmail read | Conditional setup | Low |

Confidence rubric:
- `High`: covered by runnable tests/evals and simple operational path
- `Medium`: implemented end-to-end, partial test confidence
- `Low`: setup-fragile, weakly tested, or known edge-case risk

## Known Gaps / Risks
- Single-user default paths (`user_id="default"`) across most flows.
- Shared mutable orchestrator instance at API module scope.
- Frontend inserts server/user content via `innerHTML` (XSS risk).
- Calculator uses `eval(...)` despite input validation.
- Upload failure path can reference `document_id` before assignment.
- Behavioral eval coverage is still limited; current eval is mostly static invariants.

## Immediate Priorities
1. Security and correctness fixes (`eval`, XSS, upload failure path).
2. Request-isolated orchestration state.
3. Better test/eval signal (reduced skip reliance, behavioral checks).
4. Auth + multi-user isolation groundwork.

## Where Active Work Is Tracked
- Execution board: [`WORKBOARD.md`](WORKBOARD.md)
- Sequenced roadmap: [`ROADMAP.md`](ROADMAP.md)
- Atomic tasks: GitHub Issues
