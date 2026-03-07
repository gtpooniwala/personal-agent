# Roadmap

Last updated: March 7, 2026

## Objective
Move from strong prototype to production-ready personal AI agent with reliable behavior, safer defaults, and measurable quality.

Current high-priority execution objective: validate and harden the async run model (`#15`-`#17`, now complete) and address frontend correctness follow-ups (`#31`, `#30`).

## Now (Stabilize Core)
- Async run lifecycle schema + submission/status/event contracts complete (`#15`, `#16`, `#17`).
- Land Gmail reliability follow-up (`#40`).
- Address active frontend send correctness risk (`#31`) and IME Enter handling (`#30`).

Success criteria:
- Core tests runnable in one documented command.
- Request/run lifecycle events and counters are visible in logs/metrics.
- `/runs` + async `/chat` submission and status/events paths are operational.
- Assistant responses stay bound to originating conversation during in-flight requests.

## Next (Raise Quality Bar)
- Add runtime eval coverage for lifecycle transitions, retries, and session isolation (`#19`).
- Add scheduler/heartbeat primitives for autonomous workflows after core runtime stabilizes (`#18`).
- Resolve async-path follow-up correctness/cleanup items (`#28`, `#29`).
- Continue integration ergonomics and cleanup after migration core and Gmail follow-up settle (`#40`, then frontend polish).

Success criteria:
- Machine-readable runtime eval report with CI-friendly pass/fail signals.
- Stable worker behavior under retry and per-session serialization.
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
- Completed migration prerequisites: [#14](https://github.com/gtpooniwala/personal-agent/issues/14) (design + PR decomposition), [#22](https://github.com/gtpooniwala/personal-agent/issues/22), [#23](https://github.com/gtpooniwala/personal-agent/issues/23)
- Completed core migration implementation: [#15](https://github.com/gtpooniwala/personal-agent/issues/15) (run lifecycle schema), [#16](https://github.com/gtpooniwala/personal-agent/issues/16) (worker queue + per-session serialization), [#17](https://github.com/gtpooniwala/personal-agent/issues/17) (async contracts)
- Remaining migration items: [#19](https://github.com/gtpooniwala/personal-agent/issues/19) (runtime evals), [#18](https://github.com/gtpooniwala/personal-agent/issues/18) (scheduler/heartbeat)
- Active migration/frontend follow-ups: [#28](https://github.com/gtpooniwala/personal-agent/issues/28), [#29](https://github.com/gtpooniwala/personal-agent/issues/29), [#31](https://github.com/gtpooniwala/personal-agent/issues/31), [#30](https://github.com/gtpooniwala/personal-agent/issues/30), [#40](https://github.com/gtpooniwala/personal-agent/issues/40)
