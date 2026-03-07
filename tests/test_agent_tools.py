"""Behavioral tests for core tool modules."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

AGENT_TOOL_TESTS_AVAILABLE = True
AGENT_TOOL_IMPORT_ERROR = ""

try:
    from backend.orchestrator.tools.calculator import CalculatorInput, CalculatorTool
    from backend.orchestrator.tools.scratchpad import ScratchpadTool
    from backend.orchestrator.tools.time import CurrentTimeTool
    from backend.orchestrator.tools import web_search_providers
except Exception as exc:
    AGENT_TOOL_TESTS_AVAILABLE = False
    AGENT_TOOL_IMPORT_ERROR = str(exc)


@unittest.skipUnless(
    AGENT_TOOL_TESTS_AVAILABLE,
    f"Agent tool test dependencies unavailable: {AGENT_TOOL_IMPORT_ERROR}"
)
class TestCalculatorTool(unittest.TestCase):
    def setUp(self):
        self.tool = CalculatorTool()

    def test_calculator_returns_result(self):
        result = self.tool._run("2 * (3 + 4)")
        self.assertIn("14", result)

    def test_calculator_supports_exponentiation(self):
        result = self.tool._run("2**8")
        self.assertIn("256", result)

    def test_calculator_preserves_large_integer_precision(self):
        result = self.tool._run("9007199254740993 + 1")
        self.assertIn("9007199254740994", result)

    def test_calculator_handles_division_by_zero(self):
        result = self.tool._run("10 / 0")
        self.assertIn("Division by zero", result)

    def test_calculator_preserves_division_float_output(self):
        result = self.tool._run("6 / 2")
        self.assertIn("3.0", result)

    def test_calculator_rejects_unsupported_operator(self):
        result = self.tool._run("5 // 2")
        self.assertIn("Error calculating", result)

    def test_calculator_rejects_exponent_above_safety_limit(self):
        result = self.tool._run("2**1000")
        self.assertIn("safe limit", result)

    def test_calculator_input_validation_blocks_non_math(self):
        with self.assertRaises(ValueError):
            CalculatorInput(expression="2 + os.system('rm -rf /')")


@unittest.skipUnless(
    AGENT_TOOL_TESTS_AVAILABLE,
    f"Agent tool test dependencies unavailable: {AGENT_TOOL_IMPORT_ERROR}"
)
class TestTimeTool(unittest.TestCase):
    def setUp(self):
        self.tool = CurrentTimeTool()

    def test_time_tool_standard_format(self):
        result = self.tool._run(query="what time is it")
        self.assertTrue(result.startswith("Current date and time: "))
        timestamp = result.replace("Current date and time: ", "")
        datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    def test_time_tool_iso_format(self):
        result = self.tool._run(query="now")
        self.assertIn("Current date and time", result)


@unittest.skipUnless(
    AGENT_TOOL_TESTS_AVAILABLE,
    f"Agent tool test dependencies unavailable: {AGENT_TOOL_IMPORT_ERROR}"
)
class TestScratchpadTool(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tool = ScratchpadTool(user_id="test_user")
        notes_dir = os.path.join(self.temp_dir, "scratchpad")
        os.makedirs(notes_dir, exist_ok=True)
        object.__setattr__(self.tool, "_notes_dir", self.tool._notes_dir.__class__(notes_dir))
        object.__setattr__(self.tool, "_notes_file", self.tool._notes_file.__class__(os.path.join(notes_dir, "notes.json")))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scratchpad_save_and_read(self):
        save_result = self.tool._run(action="save", content="remember this")
        self.assertIn("Note saved", save_result)
        read_result = self.tool._run(action="read")
        self.assertIn("remember this", read_result)

    def test_scratchpad_delete(self):
        self.tool._run(action="save", content="temporary")
        delete_result = self.tool._run(action="delete", note_number=1)
        self.assertIn("Deleted note", delete_result)

    def test_scratchpad_clear(self):
        self.tool._run(action="save", content="a")
        self.tool._run(action="save", content="b")
        clear_result = self.tool._run(action="clear")
        self.assertIn("Cleared all", clear_result)


@unittest.skipUnless(
    AGENT_TOOL_TESTS_AVAILABLE,
    f"Agent tool test dependencies unavailable: {AGENT_TOOL_IMPORT_ERROR}"
)
class TestWebSearchProviders(unittest.TestCase):
    @patch("backend.orchestrator.tools.web_search_providers.requests")
    def test_duckduckgo_search_uses_abstract_text(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = {"AbstractText": "Result summary"}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response
        result = web_search_providers.duckduckgo_search("python")
        self.assertEqual(result, "Result summary")

    @patch("backend.orchestrator.tools.web_search_providers.requests")
    def test_provider_returns_none_on_request_error(self, mock_requests):
        mock_requests.get.side_effect = Exception("network down")
        result = web_search_providers.bing_search("python", "test-key")
        self.assertIsNone(result)


SUMMARISATION_AVAILABLE = True
SUMMARISATION_IMPORT_ERROR = ""
_summarisation_module = None

try:
    from backend.orchestrator.tools.summarisation_agent import SummarisationAgent
    _summarisation_module = sys.modules["backend.orchestrator.tools.summarisation_agent"]
except ImportError as exc:
    SUMMARISATION_AVAILABLE = False
    SUMMARISATION_IMPORT_ERROR = str(exc)


@unittest.skipUnless(
    SUMMARISATION_AVAILABLE,
    f"SummarisationAgent unavailable: {SUMMARISATION_IMPORT_ERROR}",
)
class TestSummarisationAgentSync(unittest.TestCase):
    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    def test_run_returns_summary_text(self, mock_create):
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="Summary text")
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        result = tool._run("User: hello\nAssistant: hi")
        self.assertEqual(result, "Summary text")

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    def test_run_falls_back_to_str_when_no_content_attr(self, mock_create):
        mock_llm = Mock()
        mock_llm.invoke.return_value = "plain string"
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        result = tool._run("history")
        self.assertEqual(result, "plain string")

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    def test_run_includes_conversation_in_prompt(self, mock_create):
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="ok")
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        tool._run("special history content")
        call_args = mock_llm.invoke.call_args[0][0]
        self.assertIn("special history content", call_args)

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    def test_run_respects_max_tokens(self, mock_create):
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="short")
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        tool._run("history", max_tokens=256)

        mock_create.assert_called_once_with(
            "summarisation_agent", temperature=0.2, max_tokens=256
        )


@unittest.skipUnless(
    SUMMARISATION_AVAILABLE,
    f"SummarisationAgent unavailable: {SUMMARISATION_IMPORT_ERROR}",
)
class TestSummarisationAgentAsync(unittest.IsolatedAsyncioTestCase):
    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    async def test_arun_uses_ainvoke(self, mock_create):
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content="Async summary"))
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        result = await tool._arun("User: hello\nAssistant: hi")

        mock_llm.ainvoke.assert_awaited_once()
        mock_llm.invoke.assert_not_called()
        self.assertEqual(result, "Async summary")

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    async def test_arun_passes_conversation_in_prompt(self, mock_create):
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content="ok"))
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        await tool._arun("unique async history")

        prompt = mock_llm.ainvoke.call_args[0][0]
        self.assertIn("unique async history", prompt)

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    async def test_arun_respects_max_tokens(self, mock_create):
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content="short"))
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        await tool._arun("history", max_tokens=256)

        mock_create.assert_called_once_with(
            "summarisation_agent", temperature=0.2, max_tokens=256
        )

    @patch.object(_summarisation_module or object(), "create_chat_model", create=True)
    async def test_arun_does_not_call_sync_run(self, mock_create):
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content="result"))
        mock_create.return_value = mock_llm

        tool = SummarisationAgent()
        original_run = tool._run
        run_called = []
        tool._run = lambda *a, **kw: run_called.append(True) or original_run(*a, **kw)

        await tool._arun("history")
        self.assertEqual(run_called, [], "_run must not be called from _arun")


if __name__ == "__main__":
    unittest.main()
