"""Tool registry tests with stubbed tool classes."""
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

TOOL_REGISTRY_TESTS_AVAILABLE = True
TOOL_REGISTRY_IMPORT_ERROR = ""

try:
    from backend.orchestrator.tool_registry import ToolRegistry
except Exception as exc:
    TOOL_REGISTRY_TESTS_AVAILABLE = False
    TOOL_REGISTRY_IMPORT_ERROR = str(exc)


class DummyTool:
    def __init__(self, name, description="dummy"):
        self.name = name
        self.description = description


@unittest.skipUnless(
    TOOL_REGISTRY_TESTS_AVAILABLE,
    f"Tool registry test dependencies unavailable: {TOOL_REGISTRY_IMPORT_ERROR}"
)
class TestToolRegistry(unittest.TestCase):
    def _build_registry(self, selected_documents=None, gmail_ready=False):
        with patch("backend.orchestrator.tool_registry.CalculatorTool", return_value=DummyTool("calculator")), \
             patch("backend.orchestrator.tool_registry.CurrentTimeTool", return_value=DummyTool("current_time")), \
             patch("backend.orchestrator.tool_registry.ScratchpadTool", return_value=DummyTool("scratchpad")), \
             patch(
                 "backend.orchestrator.tool_registry.get_gmail_readiness",
                 return_value=(gmail_ready, [] if gmail_ready else ["feature_flag_disabled"])
             ), \
             patch("backend.orchestrator.tool_registry.GmailReadTool", return_value=DummyTool("gmail_read")), \
             patch("backend.orchestrator.tool_registry.ResponseAgentTool", return_value=DummyTool("response_agent")), \
             patch("backend.orchestrator.tool_registry.InternetSearchTool", return_value=DummyTool("internet_search")), \
             patch("backend.orchestrator.tool_registry.UserProfileTool", return_value=DummyTool("user_profile")), \
             patch("backend.orchestrator.tool_registry.SummarisationAgent", return_value=DummyTool("summarisation_agent")), \
             patch("backend.orchestrator.tool_registry.SearchDocumentsTool", return_value=DummyTool("search_documents")):
            return ToolRegistry(selected_documents=selected_documents)

    def test_get_available_tools_without_documents(self):
        registry = self._build_registry(selected_documents=[])
        names = [tool.name for tool in registry.get_available_tools()]
        self.assertIn("calculator", names)
        self.assertIn("current_time", names)
        self.assertNotIn("search_documents", names)
        self.assertNotIn("gmail_read", names)

    def test_get_available_tools_with_documents(self):
        registry = self._build_registry(selected_documents=["doc-1"])
        names = [tool.name for tool in registry.get_available_tools()]
        self.assertIn("search_documents", names)
        self.assertNotIn("gmail_read", names)

    def test_get_available_tools_includes_gmail_when_ready(self):
        registry = self._build_registry(selected_documents=[], gmail_ready=True)
        with patch(
            "backend.orchestrator.tool_registry.get_gmail_readiness",
            return_value=(True, []),
        ):
            names = [tool.name for tool in registry.get_available_tools()]
        self.assertIn("gmail_read", names)

    def test_get_available_tools_drops_gmail_when_runtime_refresh_marks_it_unavailable(self):
        registry = self._build_registry(selected_documents=[], gmail_ready=True)
        with patch(
            "backend.orchestrator.tool_registry.get_gmail_readiness",
            return_value=(False, ["account_not_connected"]),
        ):
            registry.refresh_runtime_capabilities(force=True)
            names = [tool.name for tool in registry.get_available_tools()]
        self.assertNotIn("gmail_read", names)

    def test_get_available_tools_adds_gmail_when_runtime_refresh_marks_it_available(self):
        registry = self._build_registry(selected_documents=[], gmail_ready=False)
        with patch(
            "backend.orchestrator.tool_registry.get_gmail_readiness",
            return_value=(True, []),
        ):
            registry.refresh_runtime_capabilities(force=True)
            names = [tool.name for tool in registry.get_available_tools()]
        self.assertIn("gmail_read", names)

    def test_get_available_tools_reuses_recent_runtime_capability_snapshot(self):
        with patch("backend.orchestrator.tool_registry.CalculatorTool", return_value=DummyTool("calculator")), \
             patch("backend.orchestrator.tool_registry.CurrentTimeTool", return_value=DummyTool("current_time")), \
             patch("backend.orchestrator.tool_registry.ScratchpadTool", return_value=DummyTool("scratchpad")), \
             patch(
                 "backend.orchestrator.tool_registry.get_gmail_readiness",
                 return_value=(False, ["account_not_connected"]),
             ) as mock_get_gmail_readiness, \
             patch("backend.orchestrator.tool_registry.GmailReadTool", return_value=DummyTool("gmail_read")), \
             patch("backend.orchestrator.tool_registry.ResponseAgentTool", return_value=DummyTool("response_agent")), \
             patch("backend.orchestrator.tool_registry.InternetSearchTool", return_value=DummyTool("internet_search")), \
             patch("backend.orchestrator.tool_registry.UserProfileTool", return_value=DummyTool("user_profile")), \
             patch("backend.orchestrator.tool_registry.SummarisationAgent", return_value=DummyTool("summarisation_agent")), \
             patch("backend.orchestrator.tool_registry.SearchDocumentsTool", return_value=DummyTool("search_documents")):
            registry = ToolRegistry(selected_documents=[])
            registry.get_available_tools()
            registry.get_available_tools()

        self.assertEqual(mock_get_gmail_readiness.call_count, 1)

    def test_register_and_unregister_tool(self):
        registry = self._build_registry()
        registry.register_tool("custom", DummyTool("custom", "custom tool"))
        self.assertIsNotNone(registry.get_tool("custom"))
        removed = registry.unregister_tool("custom")
        self.assertTrue(removed)
        self.assertIsNone(registry.get_tool("custom"))

    def test_update_selected_documents_enables_document_search(self):
        registry = self._build_registry(selected_documents=[])
        self.assertNotIn("search_documents", [t.name for t in registry.get_available_tools()])
        registry.update_selected_documents(["doc-123"])
        self.assertIn("search_documents", [t.name for t in registry.get_available_tools()])

    def test_clone_with_selected_documents_reuses_static_tools(self):
        registry = self._build_registry(selected_documents=[])
        clone = registry.clone_with_selected_documents(["doc-123"])

        self.assertIsNot(clone, registry)
        self.assertEqual(clone.selected_documents, ["doc-123"])
        self.assertIn("search_documents", [t.name for t in clone.get_available_tools()])
        self.assertIs(clone.get_tool("calculator"), registry.get_tool("calculator"))
        self.assertIs(clone.get_tool("response_agent"), registry.get_tool("response_agent"))
        self.assertIsNone(registry.get_tool("search_documents"))


if __name__ == "__main__":
    unittest.main()
