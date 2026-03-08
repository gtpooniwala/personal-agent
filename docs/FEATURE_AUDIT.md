# Feature Audit

This is a supporting audit doc, not the source of truth for planning or status. Use it when you want a quick "what should I double-check?" view across the repo.

## Areas That Look Strong
- Durable async runtime contract with run/event/lease storage
- LangGraph orchestration with a fresh per-attempt orchestrator path
- Core tool set for calculator, time, search, scratchpad, profile, and document workflows
- Scheduler-backed recurring task baseline
- Strong documentation coverage for architecture, setup, testing, deployment, and triggers

## Areas That Still Deserve Attention
- Mixed tool-selection ownership in `CoreOrchestrator`
- In-process background follow-up work such as summarisation
- Conditional integrations with setup-sensitive behavior, especially Gmail
- Placeholder integrations that exist structurally but are not active product features
- Frontend UX and clarity around document selection and runtime progress

## Useful Audit Questions

### Runtime
- Does the change preserve the durable run/event contract?
- Does it keep polling responsive while orchestration is busy?
- Does it introduce any new background work that should really be a durable task type?

### Orchestration
- Is tool choice owned by prompt and tool contracts, or by new ad hoc routing branches?
- Are document guardrails still explicit and truthful?
- Did response synthesis and tool traces stay aligned?

### Integrations
- Is the feature always available, conditional, or placeholder?
- Is setup documented clearly enough that an agent can tell why a tool is unavailable?

### Documentation
- Did the change update the right current-source-of-truth docs?
- Is this feature represented accurately in [`FEATURES_OVERVIEW.md`](FEATURES_OVERVIEW.md) and [`README.md`](../README.md)?

## Recommended References
- Current execution state: [`WORKBOARD.md`](WORKBOARD.md)
- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Runtime sequencing: [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md)
- Feature inventory: [`FEATURES_OVERVIEW.md`](FEATURES_OVERVIEW.md)
- Testing expectations: [`TESTING.md`](TESTING.md)
