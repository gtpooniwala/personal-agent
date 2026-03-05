# Suggested Changes Tracker

Last updated: March 5, 2026

This file tracks suggested implementation work before issue creation.
Status values: `todo`, `in_progress`, `done`, `blocked`.

## High Priority (Stability + Safety)
| Priority | Status | Change | Why it matters |
|---|---|---|---|
| P0 | todo | Replace calculator `eval(...)` with safe expression evaluator | Removes unsafe execution pattern in a user-facing path |
| P0 | todo | Remove XSS-prone dynamic `innerHTML` rendering in frontend | Prevents script injection from user/server-provided content |
| P0 | todo | Fix upload failure path that can reference uninitialized `document_id` | Prevents runtime failure in document processing error flow |
| P1 | todo | Isolate orchestrator state per request/session | Reduces cross-request state leakage and race conditions |

## Medium Priority (Quality + Reliability)
| Priority | Status | Change | Why it matters |
|---|---|---|---|
| P1 | todo | Gate Gmail tool availability by configuration/dependency readiness | Avoids noisy tool failures in default local setups |
| P1 | todo | Improve local test setup to avoid skip-only green runs | Increases confidence that changes are truly validated |
| P1 | todo | Add behavioral evals (tool selection + RAG regressions) | Captures real quality regressions beyond static checks |
| P2 | todo | Clean frontend rough edges (duplicate utility logic, placeholders) | Improves readability and lowers maintenance friction |

## Strategic Improvements
| Priority | Status | Change | Why it matters |
|---|---|---|---|
| P2 | todo | Add authentication and user isolation end-to-end | Removes single-user default architecture constraint |
| P2 | todo | Add operational observability (latency/token/tool metrics) | Improves debugging and production readiness |
| P2 | todo | Move retrieval layer toward scalable vector storage options | Improves RAG performance and growth path |

## Potential New Features
| Priority | Status | Feature idea | Value |
|---|---|---|---|
| P3 | todo | Production-grade calendar/task integrations | Expands assistant utility beyond chat + docs |
| P3 | todo | User memory controls (view/edit/delete profile facts) | Improves trust and personalization control |
| P3 | todo | Source-grounded RAG with stronger citation controls | Better response trustworthiness |
| P3 | todo | Voice and multimodal inputs | Broadens UX and accessibility |

## Notes
- This is a pre-issue planning tracker.
- Once overall vision is finalized, convert each row into a GitHub issue and add issue IDs.
