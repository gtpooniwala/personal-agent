# Personal Agent Documentation

## Source Of Truth
Use these first when you want the current state of the repo.

- [`../README.md`](../README.md): top-level product overview, quick start, current limitations, and doc map
- [`WORKBOARD.md`](WORKBOARD.md): agent execution order and current status
- [`ROADMAP.md`](ROADMAP.md): sequencing rationale and medium-term plan
- [`ARCHITECTURE.md`](ARCHITECTURE.md): architecture today plus target direction
- [`API.md`](API.md): current API contract
- [`SETUP.md`](SETUP.md): local setup paths
- [`TESTING.md`](TESTING.md): validation commands and expectations
- [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md): worktree, branch, and PR policy
- [`WORKTREE_SLOTS.md`](WORKTREE_SLOTS.md): managed slot workflow for shared-root / CLI launches, plus the Codex Desktop worktree exception
- [`ISSUE_MANAGEMENT.md`](ISSUE_MANAGEMENT.md): issue taxonomy, labels, and execution contract
- [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md): prompt surfaces and ownership

## Supporting Architecture Context
These are still useful, but they are supporting references rather than the primary execution board.

- [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md): why the async runtime exists and which hardening steps remain
- [`SYSTEM_FLOW.md`](SYSTEM_FLOW.md): end-to-end flow diagrams for runtime, scheduler, and follow-up work
- [`FEATURES_OVERVIEW.md`](FEATURES_OVERVIEW.md): capability inventory by maturity
- [`DEPLOYMENT.md`](DEPLOYMENT.md): GCP deployment ADR and rollout order
- [`vercel-setup.md`](vercel-setup.md): Vercel frontend deployment runbook
- [`EVENT_TRIGGERS.md`](EVENT_TRIGGERS.md): trigger framework and mobile automation design
- [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md): contributor workflow on top of the engineering policy

## Reference And Historical Context
These docs remain in the repo because they are still useful to a reader or agent, but they should not be treated as the primary status source.

- [`FEATURE_AUDIT.md`](FEATURE_AUDIT.md): capability and coverage audit notes
- [`TEST_RESULTS_SUMMARY.md`](TEST_RESULTS_SUMMARY.md): validation snapshot guidance and refresh checklist
- [`LANGGRAPH_UPGRADE_SUMMARY.md`](LANGGRAPH_UPGRADE_SUMMARY.md): historical background on the LangGraph migration
- [`PORTFOLIO_PREPARATION.md`](PORTFOLIO_PREPARATION.md): packaging ideas if the repo is presented externally
- [`FEATURE_TEMPLATE.md`](FEATURE_TEMPLATE.md): template for future feature docs
- [`debugging/`](debugging/): debugging notes and captured sessions

## Feature Docs
- [`features/CONVERSATION_SUMMARISATION.md`](features/CONVERSATION_SUMMARISATION.md)
- [`features/DOCUMENT_UPLOAD_SYSTEM.md`](features/DOCUMENT_UPLOAD_SYSTEM.md)
- [`features/GMAIL_TOOL.md`](features/GMAIL_TOOL.md)
- [`features/INTERNET_SEARCH_TOOL.md`](features/INTERNET_SEARCH_TOOL.md)
- [`features/RESPONSE_AGENT_SYSTEM.md`](features/RESPONSE_AGENT_SYSTEM.md)
- [`features/SELECTIVE_RAG_VALIDATION.md`](features/SELECTIVE_RAG_VALIDATION.md)
- [`features/TIME_FORMATTING_IMPROVEMENT.md`](features/TIME_FORMATTING_IMPROVEMENT.md)
- [`features/TITLE_GENERATION_SYSTEM.md`](features/TITLE_GENERATION_SYSTEM.md)
- [`features/USER_PROFILE_SYSTEM.md`](features/USER_PROFILE_SYSTEM.md)

## Usage Guidance
- If you are implementing work, start with [`WORKBOARD.md`](WORKBOARD.md) and [`ROADMAP.md`](ROADMAP.md).
- If you are changing runtime behavior, also read [`ARCHITECTURE.md`](ARCHITECTURE.md), [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md), and [`SYSTEM_FLOW.md`](SYSTEM_FLOW.md).
- If you are changing prompts, read [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md) and run the relevant checks in [`TESTING.md`](TESTING.md).
- If you are changing deployment or triggers, keep [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`EVENT_TRIGGERS.md`](EVENT_TRIGGERS.md) aligned with the linked issues.
