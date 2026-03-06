# Project Status

Last updated: March 6, 2026

## Purpose
Single source of truth for current implementation status, known risks, and execution confidence.

## Current State Snapshot
- Branch health: `main` tracking `origin/main`
- Deterministic repository checks: `tests/run_repo_checks.py` passing (`12/12` on March 5, 2026)
- Unit test suite: runnable via `scripts/run_local_checks.sh` with guarded unittest execution (`tests/run_unit_tests.py`)
- Issue `#10` status: complete (standard local test workflow + skip-only non-pass signal implemented)
- Runtime profile: local-first FastAPI + LangGraph + SQLite + Next.js frontend
- Foundation P0 baseline status: `#7`, `#8`, `#9`, and `#10` are closed; remaining foundation work is `#11`-`#13`.
- Migration status: architecture contract (`#14`) and prerequisite upgrades/eval harness (`#22`, `#23`) are closed; core runtime implementation (`#15`-`#19`) remains open.
- Active tracking: milestone-backed issues plus migration/frontend follow-ups (`#28`, `#29`, `#30`, `#31`).

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
- Async run lifecycle is not yet implemented (`#15`, `#16`, `#17`).
- Runtime observability baseline is not in place yet (`#11`).
- Frontend send-path race across conversations remains open (`#31`).
- Behavioral eval coverage is still limited; current repository checks are mostly static invariants.

## Immediate Priorities
1. Complete remaining Foundation Hardening issues (`#11`, `#12`, `#13`).
2. Land core migration implementation in documented order (`#15` + `#17`, then `#16`).
3. Address migration follow-up runtime fixes (`#28`, `#29`) before scheduler work.
4. Expand runtime evals and lifecycle validation (`#19`) before autonomous workflows (`#18`).
5. Resolve frontend send-path correctness and IME behavior (`#31`, `#30`).

## Where Active Work Is Tracked
- Execution board: [`WORKBOARD.md`](WORKBOARD.md)
- Sequenced roadmap: [`ROADMAP.md`](ROADMAP.md)
- Atomic tasks: GitHub Issues
- Suggested changes index: [`SUGGESTED_CHANGES.md`](SUGGESTED_CHANGES.md)
