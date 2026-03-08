# LangGraph Upgrade Summary

This is historical context for a major earlier migration. It stays in the repo because it explains why the orchestrator is built around LangGraph today.

## What Changed
The project moved from older LangChain agent wiring to LangGraph `create_react_agent()` with tool binding and checkpoint-backed memory helpers.

That change mattered because it:
- removed manual tool-description assembly,
- made tool binding more declarative,
- gave the repo a cleaner base for multi-step tool use,
- set up the current prompt and orchestrator structure.

## Why It Still Matters
Several current docs assume this foundation:
- the orchestrator is a LangGraph ReAct agent,
- tool exposure is centralized through the registry,
- conversation history is adapted into LangChain message objects before graph invocation.

## What Changed Since Then
The repo has moved beyond just the LangGraph migration:
- the runtime is now async-submitted and durable,
- worker-pool offloading keeps blocking orchestration off the FastAPI event loop,
- the current follow-up work is about routing ownership, background durability, and trigger/deployment expansion.

So this file is useful as history, but current architecture and sequencing now live in:
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md)
- [`ROADMAP.md`](ROADMAP.md)
