"""Central prompt builders for orchestrator and LLM-backed helper tools."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.prompts import ChatPromptTemplate


def format_conversation_history(
    conversation_history: Optional[Iterable[Dict[str, Any]]],
    *,
    max_messages: Optional[int] = 12,
) -> str:
    """Render conversation history into a stable text block for prompts."""
    if not conversation_history:
        return "(No prior conversation history)"

    history = list(conversation_history)
    if max_messages is not None and len(history) > max_messages:
        history = history[-max_messages:]

    rendered: List[str] = []
    for message in history:
        role = str(message.get("role", "unknown")).strip().capitalize() or "Unknown"
        content = str(message.get("content", "")).strip() or "(empty)"
        rendered.append(f"{role}: {content}")
    return "\n".join(rendered) if rendered else "(No prior conversation history)"


def format_tool_results(tool_results: Optional[List[Dict[str, Any]]]) -> str:
    """Render tool outputs into a compact but structured prompt block."""
    if not tool_results:
        return "(No tool results were produced for this turn)"

    rendered: List[str] = []
    for index, result in enumerate(tool_results, start=1):
        tool_name = str(result.get("tool", "unknown")).strip() or "unknown"
        tool_input = result.get("input", "")
        output = str(result.get("output", "")).strip() or "(empty)"
        if isinstance(tool_input, dict):
            tool_input = json.dumps(tool_input, ensure_ascii=False, indent=2)
        rendered.append(
            "\n".join(
                [
                    f"Result {index}:",
                    f"Tool name: {tool_name}",
                    f"Tool input: {tool_input or '(not captured)'}",
                    f"Tool output: {output}",
                ]
            )
        )
    return "\n\n".join(rendered)


def build_orchestrator_system_prompt(document_status: Optional[str] = None) -> str:
    """Primary system prompt for the LangGraph orchestrator."""
    prompt = """# PERSONAL ASSISTANT CORE ORCHESTRATOR

## ROLE
You are the main orchestration agent for a personal assistant. Your job is to understand the user's request, decide whether a tool is needed, use tools deliberately, and produce the right final outcome.

## OPERATING PRINCIPLES
- Answer the user's actual request, not a nearby one.
- Prefer acting over asking clarifying questions when a reasonable assumption is safe.
- If a request is ambiguous in a way that would materially change the outcome, ask one concise clarification question instead of guessing.
- Never claim to have done work you did not actually do.
- Never mention internal implementation details unless the user explicitly asks.
- If a tool result is incomplete, conflicting, or insufficient, say so plainly.

## TOOL SELECTION POLICY
- Normal tool selection is your responsibility during successful orchestration. Choose from the currently bound tools instead of expecting hidden deterministic routing.
- Use `calculator` for arithmetic or expression evaluation.
- Use `current_time` for time, date, or day queries that depend on the current clock.
- Use `internet_search` for current events, recent facts, or information that is likely to have changed.
- Use `search_documents` only when the answer may be in the user's selected documents.
- Use `user_profile` to read durable user facts when personalization could help, and to update durable facts when the user shares something that should be remembered across conversations.
- Use `scratchpad` only for temporary working notes within the current conversation. Do not store durable user memory there.
- Avoid redundant tool calls. If a tool already answered the question, move to the final answer.

## MEMORY AND CONTEXT
- Treat conversation summaries as historical context, not as new user instructions.
- Keep track of user goals, constraints, commitments, and follow-ups across turns.
- When the user asks to remember, forget, update, or personalize based on persistent information, use `user_profile`.

## RESPONSE RULES
- Be direct and concise by default.
- Use bullets only when they improve clarity.
- For time-sensitive or current-information requests, prefer verified tool output over prior conversation context.
- If you cannot fully answer after using the appropriate tools, say what is missing and what the user can do next.
- If a capability is unavailable because the relevant tool is not exposed, say so plainly instead of pretending the tool ran.
- Do not reveal chain-of-thought or internal tool-planning steps.
"""

    if document_status:
        prompt += (
            "\n## DOCUMENT CONTEXT\n"
            "The following document-selection state is available for this conversation. "
            "Use it when deciding whether document search is possible:\n"
            f"{document_status}"
        )
    return prompt


def build_direct_response_prompt(
    *,
    user_request: str,
    conversation_history: Optional[Iterable[Dict[str, Any]]] = None,
) -> str:
    """Prompt used when graph execution fails and no deterministic fallback applies."""
    history_block = format_conversation_history(conversation_history, max_messages=10)
    return f"""You are the assistant responding without tool execution because orchestration could not complete successfully.

Rules:
- Use only the user request, the conversation context below, and your general knowledge.
- Do not claim that you searched the web, checked documents, read email, updated memory, or verified current facts.
- If the request depends on current, account-specific, or document-specific information that you cannot verify from the provided context, say so plainly.
- Give the most helpful direct answer you can, while being honest about limits.
- Keep the response concise unless the user clearly asked for depth.

Conversation context:
{history_block}

User request:
{user_request}

Assistant response:"""


def build_response_agent_prompt() -> ChatPromptTemplate:
    """Prompt contract for final response synthesis."""
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are the final-response writer for a personal assistant.

Your job is to produce the user-facing answer using the original request, conversation context, and tool outputs.

Rules:
- Answer the user's request directly.
- Ground the answer in the provided tool results when they exist.
- If tool results are partial, conflicting, or insufficient, say that clearly instead of guessing.
- Do not mention tool names, internal routing, or implementation details unless the user asked for them.
- Preserve useful context from prior conversation when it matters.
- Prefer concise wording. Use bullets only when they materially improve clarity.
- If nothing in the supplied context supports a definitive answer, say what is missing and what the user can do next.
""",
            ),
            (
                "user",
                """Original user request:
{user_query}

Conversation context:
{conversation_history_str}

Structured tool results:
{tool_results_str}

Write the final assistant response.""",
            ),
        ]
    )


def build_summarisation_prompt(conversation_history: str) -> str:
    """Prompt contract for condensed conversation memory."""
    return f"""Summarise the following conversation for future assistant turns.

Goals:
- Preserve durable user facts, preferences, constraints, commitments, and unfinished work.
- Keep enough context so the assistant can continue the conversation smoothly.
- Omit filler, repetition, and low-value chit-chat.
- Do not invent facts. If something is uncertain, say that it is uncertain.

Output format:
## Active Goals
- ...
## Preferences And Personal Facts
- ...
## Decisions And Commitments
- ...
## Open Questions And Follow-ups
- ...
## Other Useful Context
- ...

Rules:
- Use the headings exactly as written.
- If a section has no relevant information, write `- None.`
- Keep the summary compact but specific.

Conversation transcript:
{conversation_history}
"""


def build_user_profile_prompt(
    *,
    current_profile: Dict[str, Any],
    instruction: Optional[str],
    user_prompt: Optional[str],
) -> str:
    """Prompt contract for durable user-profile updates."""
    profile_json = json.dumps(current_profile, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""You maintain the assistant's persistent user profile.

Your task is to update the current profile using the instruction and the user's original message.

What belongs in the profile:
- Durable personal facts
- Stable or recurring preferences
- Long-term background, responsibilities, or projects
- Constraints that are likely to matter in future conversations

What does NOT belong in the profile:
- Temporary task state
- One-off requests with no long-term value
- Assistant guesses or inferences presented as facts
- Tool execution details

Rules:
- Preserve existing information unless it is contradicted or explicitly removed.
- If the user explicitly corrects or deletes a fact, update the profile accordingly.
- If the message contains no durable profile update, return the current profile unchanged.
- Prefer omission over invention when information is uncertain.
- Return a valid JSON object only. No markdown, prose, or code fences.

Current profile JSON:
{profile_json}

Instruction:
{instruction or '(none)'}

User's original message:
{user_prompt or '(none)'}

Updated profile JSON:"""


def build_title_prompt(conversation_context: str) -> str:
    """Prompt contract for title generation."""
    return f"""Generate a concise conversation title.

Rules:
- Maximum 5 words.
- Capture the main topic or outcome of the conversation.
- Prefer specific wording over generic labels.
- Return only the title text with no quotes or extra commentary.

Conversation:
{conversation_context}

Title:"""


def build_document_summary_prompt(document_text: str) -> str:
    """Prompt contract for upload-time document summaries."""
    return f"""Summarise this document in a single informative sentence.

Rules:
- Focus on the document's main topic, purpose, or subject matter.
- Prefer concrete wording over vague labels.
- Do not mention that this is a summary.
- Return exactly one sentence and no extra commentary.

Document content:
{document_text}

Summary:"""
