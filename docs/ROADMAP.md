# Roadmap

Last updated: March 5, 2026

## Objective
Move from strong prototype to production-ready personal AI agent with reliable behavior, safer defaults, and measurable quality.

## Now (Stabilize Core)
- Eliminate unsafe execution and UI injection risks.
- Fix known runtime correctness bugs.
- Remove global mutable state in request handling.
- Ensure local test/eval workflow is reproducible.

Success criteria:
- No `eval` in calculator path.
- No unsanitized `innerHTML` insertion of user/server content.
- Critical upload path edge cases covered by tests.
- Core tests runnable in one documented command.

## Next (Raise Quality Bar)
- Expand behavioral eval coverage for:
  - tool selection correctness
  - non-tool conversational responses
  - document retrieval relevance and failure modes
- Improve optional integration ergonomics (Gmail capability gating).
- Add stricter CI-grade checks for dependency/config drift.

Success criteria:
- Meaningful behavioral eval suite with pass/fail report.
- Reduced test skips in a standard local environment.
- Clear capability gating in `/tools` and orchestrator behavior.

## Later (Scale And Productize)
- Add authentication and user/tenant isolation.
- Offer PostgreSQL + vector store deployment profile.
- Add tracing/metrics for response time, token usage, and tool activity.
- Introduce deployment hardening (secrets, structured logs, health probes).

Success criteria:
- Multi-user safe architecture.
- Production deployment path documented and validated.
- Runtime observability sufficient for incident debugging.

## Idea Backlog (Potential New Features)
- Calendar and task integrations beyond placeholder level.
- Better long-term memory controls (review/edit/delete profile facts).
- Citation-grade RAG responses with source snippet controls.
- Voice input/output and multimodal document ingestion.
