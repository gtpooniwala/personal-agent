"""Behavioral tests for core tool modules."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

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

    def test_calculator_handles_division_by_zero(self):
        result = self.tool._run("10 / 0")
        self.assertIn("Division by zero", result)

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


if __name__ == "__main__":
    unittest.main()
