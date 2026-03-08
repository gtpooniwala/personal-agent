# Event-Driven Triggers

Last updated: March 8, 2026

This document covers the path from the current runtime to externally triggered and mobile-facing agent runs.

## Current Baseline
- The repo already has the runtime primitives needed for automation: durable runs, events, leases, heartbeat recovery, and scheduled recurring tasks.
- Scheduled tasks are no longer just planned work; the scheduler-backed recurring task baseline is already landed through `#89`.
- What remains is the external trigger layer: trigger registration, dispatch, webhook entrypoints, and mobile delivery channels.

## Goal
Move from "user manually starts a run" to "external events can create the same kind of run against the same runtime ledger."

The key design rule is simple:
- triggers should create normal runs,
- they should not invent a second execution path outside the existing runtime model.

## Trigger Framework Concept
The long-term shape is a unified trigger registry plus dispatcher.

Each trigger should define:
- a type such as `webhook`, `email`, `task_chain`, or `telegram`,
- a condition such as a cron schedule, sender filter, or inbound webhook event,
- an action that submits a normal runtime run with a prompt and optional context.

## Architectural Constraint: Hosting Model
This design is coupled to deployment choices, especially `min-instances` and how much polling the system should do itself.

### If Cloud Run scales to zero
- webhook and push-driven triggers work well,
- internal polling loops do not run while the service is idle,
- external schedulers or Pub/Sub style delivery become more attractive.

### If the backend stays warm
- internal polling is simpler,
- scheduled and email polling flows can stay inside the service,
- monthly cost is higher.

That is why `#88` and the cloud cold-start decision in `#87` should stay aligned.

## Trigger Types

### Scheduled Recurring Tasks
Status:
- implemented baseline via scheduler service and scheduled task CRUD/API

What remains:
- decide how scheduled tasks should behave once deployed to Cloud Run,
- decide whether cloud scheduling stays internal or becomes externally driven.

### Task-To-Task Chaining
Issue:
- [#90](https://github.com/gtpooniwala/personal-agent/issues/90)

Concept:
- add a `trigger_run` tool so one run can spawn a follow-up run intentionally.

Why it matters:
- it is the smallest new automation capability,
- it proves that the run ledger can support composed workflows.

### Email-Triggered Execution
Issue:
- [#91](https://github.com/gtpooniwala/personal-agent/issues/91)

Concept:
- watch for matching Gmail events or polls,
- dispatch normal agent runs with the matched email as context,
- keep deduplication explicit.

### Telegram Bot
Issue:
- [#92](https://github.com/gtpooniwala/personal-agent/issues/92)

Concept:
- Telegram webhook receives a message,
- dispatcher creates a normal run,
- result is delivered back to the same chat.

Telegram remains the best first mobile channel because it is webhook-friendly and lightweight to set up.

## Recommended Order
1. [#88](https://github.com/gtpooniwala/personal-agent/issues/88) Trigger framework and dispatcher
2. [#90](https://github.com/gtpooniwala/personal-agent/issues/90) `trigger_run`
3. [#91](https://github.com/gtpooniwala/personal-agent/issues/91) Email-triggered execution
4. [#92](https://github.com/gtpooniwala/personal-agent/issues/92) Telegram bot integration

## Practical Guidance
- Reuse `POST /runs` instead of creating custom execution paths.
- Keep trigger state and deduplication observable in the database.
- Keep polling-versus-push decisions aligned with the actual deployment model.
- Treat scheduled tasks as the first shipped slice of the broader trigger story, not a separate architecture.
