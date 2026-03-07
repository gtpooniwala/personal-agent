# Prompt Architecture

Last updated: March 7, 2026

## Overview

The runtime has one primary decision-making agent and several LLM-backed helper components. Prompting for these components is centralized in [`backend/orchestrator/prompts.py`](../backend/orchestrator/prompts.py) so behavior changes are easier to review, test, and evolve.

## Active LLM Call Surfaces

### 1. Orchestrator system prompt
- Owner: `CoreOrchestrator`
- File: `backend/orchestrator/core.py`
- Prompt builder: `build_orchestrator_system_prompt`
- Purpose: tool routing, memory/tool policy, and high-level assistant behavior

### 2. Direct fallback response prompt
- Owner: `CoreOrchestrator`
- File: `backend/orchestrator/core.py`
- Prompt builder: `build_direct_response_prompt`
- Purpose: honest direct response when graph execution fails and no deterministic fallback route applies

### 3. Final response synthesis prompt
- Owner: `ResponseAgentTool`
- File: `backend/orchestrator/tools/response_agent.py`
- Prompt builder: `build_response_agent_prompt`
- Purpose: convert tool outputs and context into the final user-facing answer

### 4. Conversation summarisation prompt
- Owner: `SummarisationAgent`
- File: `backend/orchestrator/tools/summarisation_agent.py`
- Prompt builder: `build_summarisation_prompt`
- Purpose: preserve high-signal context for long conversations

### 5. User profile update prompt
- Owner: `UserProfileTool`
- File: `backend/orchestrator/tools/user_profile.py`
- Prompt builder: `build_user_profile_prompt`
- Purpose: durable memory updates for user facts and preferences

### 6. Conversation title prompt
- Owner: `CoreOrchestrator`
- File: `backend/orchestrator/core.py`
- Prompt builder: `build_title_prompt`
- Purpose: concise auto-generated conversation titles

### 7. Document summary prompt
- Owner: `DocumentProcessor`
- File: `backend/services/document_service.py`
- Prompt builder: `build_document_summary_prompt`
- Purpose: one-line metadata summary for uploaded documents

## Non-LLM Tools

These do not have their own prompt surface today:

- `internet_search`
- `search_documents`
- `calculator`
- `current_time`
- `gmail_read`
- `scratchpad`

They are still influenced indirectly by the orchestrator and response prompts because those components decide when to use the tools and how to present their outputs.

## Current Design Intent

- The orchestrator prompt owns routing and tool-usage policy.
- The response prompt owns user-facing wording and grounded synthesis.
- Summarisation and profile prompts own memory quality.
- Fallback prompting must be explicit about its limits and must not pretend that tool work happened when it did not.

## Testing

- Prompt contract tests: `tests/test_prompt_contracts.py`
- Orchestrator fallback prompt coverage: `tests/test_core_orchestrator.py`
- Workflow/eval harness: `tests/run_llm_evals.py`

When prompt behavior changes materially, run the deterministic eval harness and the relevant unit tests, then run live LLM evals when the change affects real routing or response behavior.
