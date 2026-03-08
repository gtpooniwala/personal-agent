# System Flow

This file describes how the current system behaves on `main`. It is meant to help a reader or agent understand the operational flow quickly, not restate every implementation detail.

## Runtime Submission And Polling

```mermaid
flowchart TB
    A["Frontend submits message"] --> B["POST /chat or POST /runs"]
    B --> C["RuntimeService creates run row"]
    C --> D["Append queued event"]
    D --> E["Background runtime coordination starts"]
    E --> F["Acquire conversation lease"]
    F --> G["Execution plane runs orchestrator attempt in worker pool"]
    G --> H["Persist assistant message + tool actions"]
    H --> I["Update run row"]
    I --> J["Append succeeded or failed event"]

    K["Frontend polls"] --> L["GET /runs/{id}/status"]
    K --> M["GET /runs/{id}/events"]
    L --> N["Latest lifecycle snapshot"]
    M --> O["Ordered event stream"]
```

## Current Orchestrator Flow

```mermaid
flowchart TB
    A["Load condensed conversation history"] --> B["Clone ToolRegistry for selected documents"]
    B --> C["Build fresh LangGraph agent"]
    C --> D{"Unselected document request?"}
    D -->|Yes| E["Short-circuit with explicit document-selection message"]
    D -->|No| F["Invoke LangGraph agent"]
    F --> G{"LangGraph succeeded?"}
    G -->|Yes| H["Extract tool actions"]
    G -->|No| I["Rule-based fallback or direct response"]
    H --> J["ResponseAgent synthesizes final answer"]
    I --> J
    J --> K["Save assistant message"]
    K --> L["Trigger background summarisation task"]
```

Important current nuance:
- normal tool use should come from the LangGraph agent,
- but the orchestrator still contains some deterministic routing and fallback logic,
- which is why `#101` is the highest-value cleanup item.

## Scheduled Task Flow

```mermaid
flowchart TB
    A["SchedulerService tick"] --> B["Load due scheduled tasks"]
    B --> C["Acquire scheduled-task dispatch lease"]
    C --> D["Submit runtime run with stored message"]
    D --> E["Advance last_run_at and next_run_at"]
    E --> F["Release dispatch lease"]
```

## Follow-Up Work Today

```mermaid
flowchart LR
    A["Successful run"] --> B["Background title generation"]
    C["Assistant response saved"] --> D["Background summarisation"]
```

This part is intentionally simple because it is still transitional:
- title generation and summarisation are in-process async tasks,
- blocking follow-up orchestration can now also use the worker-pool execution plane,
- they are not yet stored as durable queued task types,
- budgeting and shutdown behavior for these follow-ups still need cleanup.

## Error And Recovery Model
- Run submission always creates a durable run row first.
- Lease acquisition failures fail the run with a user-visible message for that conversation.
- Execution attempts can retry up to the current configured limit.
- Unexpected runtime failures are written back into the run ledger as terminal failures.
- Heartbeat sweeps can fail orphaned runs if a worker disappears mid-flight.

## Related Docs
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md)
- [`ROADMAP.md`](ROADMAP.md)
