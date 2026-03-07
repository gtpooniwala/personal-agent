# Event-Driven Triggers

Last updated: March 7, 2026

This document covers the design for event-driven task execution and mobile integration: the trigger framework, individual trigger types, and mobile notification/command channels.

---

## Overview

The goal is to move beyond manually initiated chat sessions toward autonomous, event-driven agent runs. An external event (incoming email, scheduled time, Telegram message, completion of another run) causes the agent to start a new run and optionally notify the user of the result.

---

## Mobile Integration

### Platform Strategy

Build an abstract interface (`NotificationChannel` / `BotPlatform`) so multiple platforms can be plugged in without rearchitecting the core.

**Telegram first:**
- Bot API is free, no business approval required
- Webhook-based: GCP can receive messages directly
- Simpler to set up and iterate on

**WhatsApp later:**
- Requires WhatsApp Business API approval
- More complex setup and compliance requirements
- Suitable once Telegram integration is stable and proven

**Capabilities:**
- **Push** — send task status and results TO the user (e.g. "Run #42 completed: here's the summary")
- **Pull** — receive commands FROM the user (e.g. "summarize my emails from today")

---

## Event Trigger Framework

### Concept

A unified trigger registry sits between external events and the agent runtime. Each trigger has:
- A **type** (webhook, email, schedule, task-chain)
- A **condition** (e.g. sender matches pattern, cron expression, run ID completed)
- An **action** (create a new agent run with a given prompt/context)

A **dispatcher** service listens for trigger events and calls `POST /runs` to start the corresponding agent run.

### Trigger Types

| Type | Source | Mechanism |
|------|--------|-----------|
| `schedule` | Time-based | Cron expression; extends scheduler/heartbeat (#18) |
| `email` | Gmail inbox | Poll for emails matching criteria |
| `task_chain` | Agent run completion | `trigger_run` tool called from within a run |
| `webhook` | External HTTP | POST to a trigger endpoint; extensible |
| `telegram` | Telegram Bot API | Webhook receives messages, creates runs |

---

## Individual Trigger Types

### 1. Task-to-Task Chaining

A new `trigger_run(prompt, context)` tool in the agent toolkit. When called by the agent, it posts to `/runs` internally to start a new run.

**Why:** Enables multi-step workflows where one run spawns follow-up runs (e.g. "summarize this document, then file the key points into the task manager").

**Lift:** Small — reuses the existing `/runs` endpoint. No new infrastructure required.

---

### 2. Scheduled Task Runner

Extend the scheduler/heartbeat (#18) to support user-defined cron-like tasks stored in the database.

Schema addition (approximate):
```
scheduled_tasks:
  id, cron_expression, prompt, enabled, last_run_at, next_run_at
```

The scheduler polls `scheduled_tasks`, fires runs when `next_run_at` is due, and updates `last_run_at`.

**Lift:** Medium — builds on #18 which is already in progress.

---

### 3. Email-Triggered Tasks

Poll Gmail for emails matching user-defined criteria (sender, subject pattern, label). On match, dispatch a new run with the email content as context.

**Implementation notes:**
- Reuse existing Gmail tool/auth infrastructure
- Add a polling loop (or Gmail push notifications via Pub/Sub on GCP)
- Deduplicate: track processed message IDs to avoid re-triggering

**Lift:** Medium — Gmail auth already exists; main work is the polling loop and dedup logic.

---

### 4. Telegram Bot

A Telegram bot receives messages via webhook, creates agent runs, and sends results back to the user.

**Flow:**
1. User sends message to Telegram bot
2. Telegram posts webhook to `/triggers/telegram`
3. Dispatcher creates a new run via `POST /runs`
4. Run completes; result POSTed back to Telegram chat via Bot API

**Setup:**
- Register bot with BotFather (free, instant)
- Configure webhook URL to point at the Cloud Run backend (or a dedicated trigger service)
- Store `TELEGRAM_BOT_TOKEN` in Secret Manager

**Lift:** Medium-large — new endpoint, polling/push result delivery, Telegram SDK integration.

---

## Implementation Order

1. **Event trigger framework** — prerequisite for all trigger types; unified dispatcher and trigger registry
2. **Scheduled tasks** — extends #18 (already in progress); highest leverage for autonomous workflows
3. **Task-to-task chaining** — smallest lift; reuses `/runs` endpoint
4. **Telegram bot** — mobile command and notification channel
5. **Email triggers** — reuses Gmail infrastructure; add polling loop and dedup

---

## Sub-issues

| Issue | Title |
|-------|-------|
| #88 | feat: event trigger framework — unified infrastructure for external triggers |
| #89 | feat: task-to-task chaining — trigger_run tool for agent-spawned runs |
| #90 | feat: scheduled task runner — cron-like recurring agent runs |
| #91 | feat: email-triggered task execution |
| #92 | feat: Telegram bot integration for mobile task monitoring and triggering |
