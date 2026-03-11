# Event-Driven Triggers

Last updated: March 10, 2026

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

---

## Architectural Decisions (resolved in #88)

### Trigger Detection Methods

**Telegram:** Webhook is the only viable approach with `min-instances=0` on Cloud Run. Telegram
calls `POST /triggers/telegram` on every new message after a one-time `setWebhook` registration.
Long polling requires a continuously running process and is incompatible with scale-to-zero.

**Email (Gmail):** Initial implementation uses Cloud Scheduler + a polling endpoint
(`POST /triggers/poll`) for simplicity — no additional GCP resources needed. Cloud Scheduler wakes
Cloud Run on a regular cadence; the poll sweep calls the Gmail API to check for new mail. Upgrade
path to Gmail Pub/Sub push notifications is straightforward and tracked as a future improvement.

**Cloud Scheduler as wake-up mechanism:** Cloud Run with `min-instances=0` goes idle between
requests. Cloud Scheduler is configured to call `POST /triggers/poll` on a regular cadence, waking
the service so both the internal `SchedulerService` tick and any polling-based trigger sweeps run.

### conversation_id Binding Strategy

Each `ExternalTrigger` record stores a `conversation_id`. The user designates which conversation a
Telegram channel or email watch injects into. The dispatcher creates runs under that conversation.
This mirrors the `ScheduledTask` pattern and requires no schema changes to the `runs` table and no
dependency on the nullable `conversation_id` proposal (#157).

### Deduplication via TriggerEvent Table

Every received external event is recorded in a `TriggerEvent` row before dispatch. The
`(trigger_id, external_event_id)` pair has a unique index. If a webhook is retried by the sender,
the dispatcher detects the existing row and skips re-dispatch. The `run_id` field is updated after
a successful dispatch so the audit log links event → run.

A distributed lease (`trigger_event:<trigger_id>:<external_event_id>`) prevents race conditions
between concurrent workers processing the same event simultaneously.

### Workflow Matching (_resolve_conversation stub)

`_resolve_conversation()` in `TriggerDispatcher` currently always returns the trigger's default
`conversation_id`, creating a new workflow per event. The stub is intentional — the matching
algorithm (using `reply_to_message_id`, `thread_id`, `correlation_id`, etc.) is tracked as a
follow-up issue and will be implemented in `_resolve_conversation()` without changing the dispatch
contract.

### What Landed in #88

- `ExternalTrigger` model and CRUD (`backend/database/models.py`, `backend/database/operations.py`)
- `TriggerEvent` model with dedup index and operations
- `TriggerDispatcher` service (`backend/runtime/trigger_dispatcher.py`)
- Webhook receiver stubs: `POST /triggers/telegram`, `POST /triggers/email`, `POST /triggers/poll`
- Trigger CRUD routes: `GET/POST /triggers`, `GET/PATCH/DELETE /triggers/{id}`
- Audit log route: `GET /triggers/{id}/events`
