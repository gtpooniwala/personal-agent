# Long-Running Runtime Architecture (OpenClaw-lite Direction)

This document is the canonical design reference for the runtime migration in issue #14.

## Why this migration is now
The current synchronous chat path (`POST /api/v1/chat`) makes long or complex workflows fragile because:
- every request must complete in one HTTP response window,
- recovery is impossible if the process crashes mid-run,
- tool execution and background summarization are mixed in the request path,
- there is no durable run ledger for retries, auditing, or status surfacing.

The migration intentionally introduces a run model:
1. decouple request acceptance from execution,
2. persist run state for restart-safe progress,
3. expose status/events for client polling.

Given this is a local single-user project, the design targets operational correctness first, then evolvability.

## Target architecture
### 1) API contract
- `POST /api/v1/runs` -> creates a run and returns `run_id` immediately.
- `GET /api/v1/runs/{run_id}/status` -> returns latest run state and summary metadata.
- `GET /api/v1/runs/{run_id}/events` -> returns ordered progress/error messages for UI streaming or polling display.

### 2) Execution model
- A dedicated worker process consumes a run queue and executes actual orchestration work.
- Workers write deterministic run events/state transitions so progress survives restarts.
- Runs are scoped per conversation/session.

### 3) Transitional API compatibility
- `POST /api/v1/chat` remains temporarily available.
- It is functionally treated as a compatibility shim that submits a run internally and returns a deprecation warning in responses/docs.
- The shim is removed after the frontend + backend migration lands.

## Run lifecycle and semantics
Recommended canonical states (to be implemented in #15/#16/#17):
- `queued` → `running` → `succeeded`
- or `queued` → `running` → `retrying` → `succeeded`
- failure path: `running` → `failed`
- cancel path: `running` → `cancelling` → `cancelled`

Expected semantics:
- State transitions are append-only in `run_events`.
- Only one active worker path per conversation/session for ordering guarantees.
- A failed run preserves partial result context for debugging and user messaging.
- Retry path is bounded and visible via status/events.

## Failure and resilience
- Worker exceptions transition the run to `failed` and emit a terminal event with classification:
  - input validation
  - tool error
  - dependency/provider issue
  - unexpected crash
- Retry policy:
  - only non-permanent failures retry by default,
  - attempts are capped and logged,
  - users can resubmit manually (future enhancement).

## Concurrency boundary
- Per-session serialization is required in first pass.
- Concurrent sessions may run in parallel where worker/process capacity allows.
- This avoids cross-conversation state races without overcomplicating local workflow.

## Operational visibility (Option B)
- Primary path for this migration: HTTP polling via status/events.
- SSE/WebSocket can be added later without changing run schema when useful.

## PR decomposition (from #14)
This design is consumed by these future PRs:
1. #15: run lifecycle schema and durable state tables
2. #17: run submission + status/events API
3. #16: dedicated worker and per-session serialization
4. #19: runtime evals for lifecycle/retry/session isolation
5. #18: scheduler/heartbeat after core run semantics are stable

## Documentation contract
All migration docs must:
- describe the async run contract as primary,
- mark `/api/v1/chat` as transitional and deprecated,
- reuse the same run-state vocabulary,
- include migration notes for client updates.
