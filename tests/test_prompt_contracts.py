"""Tests for shared prompt contracts used by LLM-backed components."""

import sys
import os
import unittest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

PROMPT_TESTS_AVAILABLE = True
PROMPT_IMPORT_ERROR = ""

try:
    from backend.orchestrator.prompts import (
        build_direct_response_prompt,
        build_document_summary_prompt,
        build_orchestrator_system_prompt,
        build_response_agent_prompt,
        build_summarisation_prompt,
        build_title_prompt,
        build_user_profile_prompt,
        format_conversation_history,
        format_tool_results,
    )
except Exception as exc:
    PROMPT_TESTS_AVAILABLE = False
    PROMPT_IMPORT_ERROR = str(exc)


@unittest.skipUnless(
    PROMPT_TESTS_AVAILABLE,
    f"Prompt contract test dependencies unavailable: {PROMPT_IMPORT_ERROR}",
)
class TestPromptContracts(unittest.TestCase):
    def test_orchestrator_prompt_includes_tool_policy_and_document_context(self):
        prompt = build_orchestrator_system_prompt("Documents are selected.")
        self.assertIn("TOOL SELECTION POLICY", prompt)
        self.assertIn("Use `internet_search` for current events", prompt)
        self.assertIn("Documents are selected.", prompt)

    def test_direct_response_prompt_enforces_honesty(self):
        prompt = build_direct_response_prompt(
            user_request="What happened today?",
            conversation_history=[{"role": "user", "content": "Earlier"}],
        )
        self.assertIn("without tool execution", prompt)
        self.assertIn("Do not claim that you searched the web", prompt)
        self.assertIn("User: Earlier", prompt)

    def test_response_agent_prompt_mentions_grounding_and_limits(self):
        prompt = build_response_agent_prompt()
        messages = prompt.messages
        system_message = messages[0].prompt.template
        self.assertIn("Ground the answer in the provided tool results", system_message)
        self.assertIn("Do not mention tool names", system_message)
        self.assertIn("say what is missing", system_message)

    def test_summarisation_prompt_uses_structured_sections(self):
        prompt = build_summarisation_prompt("user: hello")
        self.assertIn("## Active Goals", prompt)
        self.assertIn("## Preferences And Personal Facts", prompt)
        self.assertIn("If a section has no relevant information", prompt)

    def test_user_profile_prompt_requires_json_only(self):
        prompt = build_user_profile_prompt(
            current_profile={"preferences": {"timezone": "UTC"}},
            instruction="Remember that I prefer tea.",
            user_prompt="Please remember that I prefer tea over coffee.",
        )
        self.assertIn("Return a valid JSON object only", prompt)
        self.assertIn("Temporary task state", prompt)
        self.assertIn('"timezone": "UTC"', prompt)

    def test_title_prompt_and_document_summary_prompt_are_constrained(self):
        title_prompt = build_title_prompt("User: Plan a trip\nAssistant: Suggested Rome")
        summary_prompt = build_document_summary_prompt("A lease agreement for a London flat.")
        self.assertIn("Maximum 5 words", title_prompt)
        self.assertIn("Return exactly one sentence", summary_prompt)

    def test_prompt_formatters_produce_stable_text(self):
        history = format_conversation_history(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
            max_messages=None,
        )
        tool_results = format_tool_results(
            [{"tool": "calculator", "input": {"expression": "1+1"}, "output": "2"}]
        )
        self.assertEqual(history, "User: Hello\nAssistant: Hi")
        self.assertIn("Tool name: calculator", tool_results)
        self.assertIn('"expression": "1+1"', tool_results)


if __name__ == "__main__":
    unittest.main()
