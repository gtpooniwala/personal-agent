# Roadmap

Last updated: March 5, 2026

## Objective
Move from strong prototype to production-ready personal AI agent with reliable behavior, safer defaults, and measurable quality.

Current high-priority design objective: ship and document the long-running runtime architecture (#14) so async run execution, status visibility, and compatibility migration are explicit before broad implementation.

## Now (Stabilize Core)
- Publish migration architecture docs and canonical run API contract before implementation lands.
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

## Execution Mapping (GitHub)
- Foundation hardening milestone: [01 Foundation Hardening](https://github.com/gtpooniwala/personal-agent/milestone/1)
- Runtime migration core milestone: [02 Runtime Migration Core](https://github.com/gtpooniwala/personal-agent/milestone/2)
- Workflow automation milestone: [03 Workflow Automation](https://github.com/gtpooniwala/personal-agent/milestone/3)
- Future backlog milestone: [Backlog / Future](https://github.com/gtpooniwala/personal-agent/milestone/4)
- Core migration design and implementation set: [#14](https://github.com/gtpooniwala/personal-agent/issues/14) (design + PR decomposition), [#15](https://github.com/gtpooniwala/personal-agent/issues/15), [#16](https://github.com/gtpooniwala/personal-agent/issues/16), [#17](https://github.com/gtpooniwala/personal-agent/issues/17), [#18](https://github.com/gtpooniwala/personal-agent/issues/18), [#19](https://github.com/gtpooniwala/personal-agent/issues/19)
