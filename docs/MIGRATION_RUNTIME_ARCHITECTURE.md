# Runtime Migration Architecture

This document started as the design reference for issue `#14`. The baseline migration is now landed, so this file is primarily useful for two things:

1. understanding why the runtime is shaped around durable runs and events,
2. understanding which hardening steps still remain after the initial migration.

## Why The Migration Happened
The old synchronous chat path forced all work into one HTTP request window. That made long-running or failure-prone orchestration hard to recover, hard to inspect, and hard to extend into automation.

The runtime migration introduced a run ledger so the system could:
- accept work quickly,
- persist lifecycle state,
- expose observable progress,
- serialize work per conversation,
- recover more safely from partial failures.

## What Is Already Implemented

### API Contract
- `POST /chat` and `POST /runs` submit asynchronous work and return a `run_id`.
- `GET /runs/{run_id}/status` returns the latest lifecycle snapshot.
- `GET /runs/{run_id}/events` returns ordered run events with cursor-based pagination.

### Durable Runtime State
- `runs` stores the latest run status and result/error fields.
- `run_events` is the append-only event stream used by polling clients.
- `leases` provides per-conversation serialization and scheduler dispatch locking.

### Runtime Services
- `RuntimeService` handles submission, retries, terminal status updates, and tool-result event emission.
- `OrchestrationExecutionPlane` keeps blocking orchestration attempts off the FastAPI event loop via a bounded worker pool.
- `CoreOrchestrator` now assembles explicit request-scoped execution context for each foreground run, so run-specific tool and model state is not stored implicitly on the shared orchestrator object.
- `HeartbeatService` sweeps orphaned runs.
- `SchedulerService` dispatches due scheduled tasks into the same runtime path.

## What Is Not Finished
The migration delivered the durable runtime baseline, but not the full architectural cleanup.

Open follow-ups:
- [#101](https://github.com/gtpooniwala/personal-agent/issues/101): remove mixed tool-selection ownership
- [#102](https://github.com/gtpooniwala/personal-agent/issues/102): define executor lifecycle and shutdown behavior
- [#109](https://github.com/gtpooniwala/personal-agent/issues/109): budget follow-up work separately from foreground attempts
- [#105](https://github.com/gtpooniwala/personal-agent/issues/105): persist follow-up work as queued task types
- [#103](https://github.com/gtpooniwala/personal-agent/issues/103): investigate true async internals
- [#104](https://github.com/gtpooniwala/personal-agent/issues/104): add SSE streaming on top of the same event store

## Canonical Runtime Semantics
- Primary lifecycle: `queued -> running -> succeeded`
- Retry lifecycle: `queued -> running -> retrying -> succeeded`
- Failure lifecycle: `queued|running|retrying -> failed`
- The first pass keeps one active run per conversation/session for ordering guarantees.
- `run_events` is the durable source of truth for user-visible progress.

## Practical Interpretation
The migration should be thought of as complete for the baseline contract, but incomplete for the final runtime shape.

In other words:
- the repo already has a usable async runtime,
- the `#51` step already delivered event-loop responsiveness by offloading blocking orchestration to a worker pool,
- the next work is about ownership, durability of follow-up work, and operational clarity,
- the next client and trigger features should build on the existing run/event store rather than bypass it.

## Related Docs
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`SYSTEM_FLOW.md`](SYSTEM_FLOW.md)
- [`WORKBOARD.md`](WORKBOARD.md)
