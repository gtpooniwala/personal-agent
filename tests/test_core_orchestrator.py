"""
Comprehensive tests for the Core Orchestrator functionality.
"""
import sys
import os
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

CORE_ORCHESTRATOR_TESTS_AVAILABLE = True
CORE_ORCHESTRATOR_IMPORT_ERROR = ""

try:
    from backend.orchestrator.core import CoreOrchestrator
    from backend.database.operations import db_ops
    from langchain_core.messages import AIMessage, HumanMessage
except Exception as exc:
    CORE_ORCHESTRATOR_TESTS_AVAILABLE = False
    CORE_ORCHESTRATOR_IMPORT_ERROR = str(exc)


@unittest.skipUnless(
    CORE_ORCHESTRATOR_TESTS_AVAILABLE,
    f"Core orchestrator test dependencies unavailable: {CORE_ORCHESTRATOR_IMPORT_ERROR}"
)
class TestCoreOrchestrator(unittest.TestCase):
    """Test the core orchestration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = CoreOrchestrator()
        self.mock_conversation_history = [
            {"id": "1", "role": "user", "content": "Hello", "timestamp": "2025-01-01T00:00:00"},
            {"id": "2", "role": "assistant", "content": "Hi there!", "timestamp": "2025-01-01T00:01:00"},
            {"id": "3", "role": "user", "content": "How are you?", "timestamp": "2025-01-01T00:02:00"}
        ]
    
    def test_get_condensed_conversation_history_no_summary(self):
        """Test condensed history when no summary exists."""
        with patch.object(db_ops, 'get_conversation_history', return_value=self.mock_conversation_history):
            result = self.orchestrator.get_condensed_conversation_history("test_conv")
            self.assertEqual(result, self.mock_conversation_history)
    
    def test_get_condensed_conversation_history_with_summary(self):
        """Test condensed history with summary present."""
        history_with_summary = [
            {"id": "1", "role": "user", "content": "Message 1", "timestamp": "2025-01-01T00:00:00"},
            {"id": "2", "role": "assistant", "content": "Response 1", "timestamp": "2025-01-01T00:01:00"},
            {"id": "3", "role": "user", "content": "Message 2", "timestamp": "2025-01-01T00:02:00"},
            {"id": "4", "role": "assistant", "content": "Response 2", "timestamp": "2025-01-01T00:03:00"},
            {"id": "5", "role": "system", "content": "[CONVERSATION SUMMARY]\nUser asked questions, assistant responded.", "timestamp": "2025-01-01T00:04:00"},
            {"id": "6", "role": "user", "content": "Latest message", "timestamp": "2025-01-01T00:05:00"}
        ]
        
        with patch.object(db_ops, 'get_conversation_history', return_value=history_with_summary):
            result = self.orchestrator.get_condensed_conversation_history("test_conv")
            
            # Should include: summary + 4 messages before summary + messages after summary
            self.assertGreaterEqual(len(result), 2)  # At least summary + latest message
            self.assertTrue(result[0]["content"].startswith("[CONVERSATION SUMMARY]"))
            self.assertEqual(result[-1]["content"], "Latest message")
    
    def test_create_conversation(self):
        """Test conversation creation."""
        with patch.object(db_ops, 'create_conversation', return_value="conv123"):
            conv_id = self.orchestrator.create_conversation("Test Title")
            self.assertEqual(conv_id, "conv123")
    
    def test_get_conversations(self):
        """Test retrieving conversations."""
        mock_conversations = [{"id": "conv1", "title": "Test"}]
        with patch.object(db_ops, 'get_conversations', return_value=mock_conversations):
            conversations = self.orchestrator.get_conversations()
            self.assertEqual(conversations, mock_conversations)
    
    def test_get_available_tools(self):
        """Test getting available tools."""
        mock_tools = [Mock(name="calculator", description="Math tool")]
        mock_tools[0].name = "calculator"
        mock_tools[0].description = "Math tool"
        
        with patch.object(self.orchestrator.tool_registry, 'get_available_tools', return_value=mock_tools):
            tools = self.orchestrator.get_available_tools()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "calculator")

    def test_build_langgraph_messages_preserves_summary_as_context(self):
        """Conversation summaries should be preserved without replaying SystemMessage objects."""
        condensed_history = [
            {
                "id": "s1",
                "role": "system",
                "content": "[CONVERSATION SUMMARY]\nUser discussed vacation planning and dates.",
                "timestamp": "2025-01-01T00:00:00",
            },
            {
                "id": "u1",
                "role": "user",
                "content": "Can we continue the itinerary?",
                "timestamp": "2025-01-01T00:01:00",
            },
            {
                "id": "a1",
                "role": "assistant",
                "content": "Sure, what destination?",
                "timestamp": "2025-01-01T00:02:00",
            },
        ]

        messages = self.orchestrator._build_langgraph_messages(condensed_history)

        self.assertEqual(len(messages), 3)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIn("Context from earlier conversation summary", messages[0].content)
        self.assertIn("vacation planning and dates", messages[0].content)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(messages[1].content, "Can we continue the itinerary?")
        self.assertIsInstance(messages[2], AIMessage)
        self.assertEqual(messages[2].content, "Sure, what destination?")

    def test_build_langgraph_messages_ignores_non_summary_system_messages(self):
        """Non-summary system messages should not be passed into rolling model history."""
        condensed_history = [
            {
                "id": "sys1",
                "role": "system",
                "content": "internal system note",
                "timestamp": "2025-01-01T00:00:00",
            },
            {
                "id": "u1",
                "role": "user",
                "content": "Hello",
                "timestamp": "2025-01-01T00:01:00",
            },
        ]

        messages = self.orchestrator._build_langgraph_messages(condensed_history)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, "Hello")

    def test_generate_direct_response_uses_structured_fallback_prompt(self):
        """Direct fallback responses should use the shared honesty-first prompt contract."""
        self.orchestrator.llm = Mock()
        conversation_history = [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
        ]

        with patch(
            "backend.orchestrator.core.predict_text",
            new=AsyncMock(return_value="Fallback answer"),
        ) as mock_predict:
            result = asyncio.run(
                self.orchestrator._generate_direct_response(
                    user_request="What should I do next?",
                    conversation_history=conversation_history,
                )
            )

        self.assertEqual(result, "Fallback answer")
        mock_predict.assert_awaited_once()
        prompt = mock_predict.await_args.args[1]
        self.assertIn("without tool execution", prompt)
        self.assertIn("Do not claim that you searched the web", prompt)
        self.assertIn("User: Earlier question", prompt)
        self.assertIn("What should I do next?", prompt)

    def test_short_circuit_unselected_document_request_returns_explicit_guidance(self):
        response = self.orchestrator._maybe_short_circuit_unselected_document_request(
            user_request="What does my uploaded contract say about termination?",
            selected_documents=[],
        )
        self.assertIn("contract", response.lower())
        self.assertIn(
            "No documents are currently selected. Please select one or more documents to enable document search.",
            response,
        )

    def test_short_circuit_does_not_misclassify_profile_as_document_query(self):
        response = self.orchestrator._maybe_short_circuit_unselected_document_request(
            user_request="Can you update my profile preferences?",
            selected_documents=[],
        )
        self.assertIsNone(response)

    def test_format_document_status_prefers_selected_document_state(self):
        status = self.orchestrator._format_document_status(
            {
                "has_documents": False,
                "document_count": 0,
                "selected_count": 1,
                "context_message": "Metadata unavailable.",
            }
        )
        self.assertIn("selected for this conversation", status)
        self.assertIn("use search_documents", status.lower())


if __name__ == '__main__':
    unittest.main()
