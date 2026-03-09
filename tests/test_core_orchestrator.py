"""
Comprehensive tests for the Core Orchestrator functionality.
"""
import sys
import os
import asyncio
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, Mock, patch, MagicMock

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

    def test_build_run_context_keeps_request_state_local(self):
        """Foreground execution context should carry request state instead of writing it to self."""
        mock_agent = Mock()
        mock_registry = Mock()
        mock_registry.selected_documents = ["doc-1"]

        with patch.object(
            self.orchestrator.tool_registry,
            "clone_with_selected_documents",
            return_value=mock_registry,
        ) as mock_clone, patch.object(
            self.orchestrator,
            "_build_orchestrator_agent",
            return_value=mock_agent,
        ) as mock_build, patch.object(
            self.orchestrator,
            "_ensure_llm",
            return_value="fake-llm",
        ), patch.object(
            self.orchestrator,
            "get_condensed_conversation_history",
            return_value=[{"role": "user", "content": "Hello"}],
        ):
            context = self.orchestrator._build_run_context(
                user_request="Hi there",
                conversation_id="conv-ctx",
                selected_documents=["doc-1"],
            )

        mock_clone.assert_called_once_with(["doc-1"])
        mock_build.assert_called_once_with(
            "conv-ctx",
            mock_registry,
            llm="fake-llm",
        )
        self.assertEqual(context.user_request, "Hi there")
        self.assertEqual(context.conversation_id, "conv-ctx")
        self.assertEqual(context.selected_documents, ("doc-1",))
        self.assertEqual(
            context.condensed_history,
            ({"role": "user", "content": "Hello"},),
        )
        self.assertIs(context.run_registry, mock_registry)
        self.assertIs(context.run_agent, mock_agent)
        self.assertEqual(context.llm, "fake-llm")
        self.assertFalse(hasattr(self.orchestrator, "selected_documents"))
        self.assertFalse(hasattr(self.orchestrator, "run_agent"))

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

    def test_process_request_uses_agent_path_for_document_query_without_selected_docs(self):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}
        response_agent_tool = Mock()
        response_agent_tool.synthesize.return_value = (
            "I'm sorry, I wasn't able to process your uploaded contract to find information "
            "about termination. Please try uploading the document again."
        )
        run_registry = Mock()
        run_registry.get_tool.side_effect = lambda name: response_agent_tool if name == "response_agent" else None
        direct_response = AsyncMock(return_value="direct fallback")

        with patch.object(self.orchestrator.tool_registry, "clone_with_selected_documents", return_value=run_registry), \
             patch.object(self.orchestrator, "_build_orchestrator_agent", return_value=mock_agent), \
             patch.object(self.orchestrator, "_ensure_llm"), \
             patch.object(self.orchestrator, "_generate_direct_response", direct_response), \
             patch("backend.orchestrator.core.db_ops") as mock_db_ops, \
             patch("backend.orchestrator.core.increment_counter"), \
             patch("backend.orchestrator.core.observe_operation") as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None

            result = asyncio.run(
                self.orchestrator.process_request(
                    "What does my uploaded contract say about termination?",
                    "conv-docs",
                    selected_documents=[],
                )
            )

        mock_agent.invoke.assert_called_once()
        response_agent_tool.synthesize.assert_called_once()
        direct_response.assert_not_awaited()
        self.assertEqual(result["orchestration_actions"], [])
        self.assertIn("contract", result["response"].lower())
        self.assertIn("no documents are currently selected", result["response"].lower())
        self.assertNotIn("uploading the document again", result["response"].lower())

    def test_process_request_uses_honest_direct_response_when_agent_fails(self):
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("provider timeout")
        direct_response = AsyncMock(return_value="Fallback answer")
        response_agent_tool = Mock()
        run_registry = Mock()
        run_registry.get_tool.side_effect = lambda name: response_agent_tool if name == "response_agent" else None

        with patch.object(self.orchestrator.tool_registry, "clone_with_selected_documents", return_value=run_registry), \
             patch.object(self.orchestrator, "_build_orchestrator_agent", return_value=mock_agent), \
             patch.object(self.orchestrator, "_ensure_llm"), \
             patch.object(self.orchestrator, "_generate_direct_response", direct_response), \
             patch("backend.orchestrator.core.db_ops") as mock_db_ops, \
             patch("backend.orchestrator.core.increment_counter"), \
             patch("backend.orchestrator.core.observe_operation") as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None

            result = asyncio.run(
                self.orchestrator.process_request(
                    "What is 15 + 27?",
                    "conv-fallback",
                    selected_documents=[],
                )
            )

        direct_response.assert_awaited_once()
        response_agent_tool.synthesize.assert_not_called()
        self.assertEqual(result["response"], "Fallback answer")
        self.assertEqual(result["orchestration_actions"], [])

    def test_process_request_enforces_document_capability_boundary_after_agent_failure(self):
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("provider timeout")
        direct_response = AsyncMock(
            return_value=(
                "I'm sorry, I wasn't able to process the uploaded contract to find information "
                "about termination. Please make sure the contract was successfully uploaded and try again."
            )
        )
        response_agent_tool = Mock()
        run_registry = Mock()
        run_registry.get_tool.side_effect = lambda name: response_agent_tool if name == "response_agent" else None

        with patch.object(self.orchestrator.tool_registry, "clone_with_selected_documents", return_value=run_registry), \
             patch.object(self.orchestrator, "_build_orchestrator_agent", return_value=mock_agent), \
             patch.object(self.orchestrator, "_ensure_llm"), \
             patch.object(self.orchestrator, "_generate_direct_response", direct_response), \
             patch("backend.orchestrator.core.db_ops") as mock_db_ops, \
             patch("backend.orchestrator.core.increment_counter"), \
             patch("backend.orchestrator.core.observe_operation") as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None

            result = asyncio.run(
                self.orchestrator.process_request(
                    "What does my uploaded contract say about termination?",
                    "conv-fallback-docs",
                    selected_documents=[],
                )
            )

        direct_response.assert_awaited_once()
        self.assertEqual(result["orchestration_actions"], [])
        self.assertIn("no documents are currently selected", result["response"].lower())
        self.assertNotIn("successfully uploaded", result["response"].lower())

    def test_process_request_clears_tool_actions_when_response_composition_falls_back(self):
        mock_agent = MagicMock()
        mock_tool_call = {
            "id": "tool-call-1",
            "name": "calculator",
            "args": {"expression": "2+2"},
        }
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [mock_tool_call]
        mock_tool_message = Mock()
        mock_tool_message.tool_calls = []
        mock_tool_message.tool_call_id = "tool-call-1"
        mock_tool_message.content = "4"
        mock_agent.invoke.return_value = {"messages": [mock_ai_message, mock_tool_message]}
        run_registry = Mock()
        response_agent_tool = Mock()
        response_agent_tool.synthesize.side_effect = RuntimeError("response synthesis failed")
        run_registry.get_tool.side_effect = (
            lambda name: response_agent_tool if name == "response_agent" else None
        )
        direct_response = AsyncMock(return_value="Fallback answer")

        with patch.object(
            self.orchestrator.tool_registry,
            "clone_with_selected_documents",
            return_value=run_registry,
        ), patch.object(
            self.orchestrator,
            "_build_orchestrator_agent",
            return_value=mock_agent,
        ), patch.object(
            self.orchestrator,
            "_ensure_llm",
            return_value=Mock(),
        ), patch.object(
            self.orchestrator,
            "_generate_direct_response",
            direct_response,
        ), patch("backend.orchestrator.core.db_ops") as mock_db_ops, patch(
            "backend.orchestrator.core.increment_counter"
        ) as mock_increment, patch(
            "backend.orchestrator.core.observe_operation"
        ) as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None

            result = asyncio.run(
                self.orchestrator.process_request(
                    "What is 2+2?",
                    "conv-compose-fallback",
                    selected_documents=[],
                )
            )

        direct_response.assert_awaited_once()
        self.assertEqual(result["response"], "Fallback answer")
        self.assertEqual(result["orchestration_actions"], [])
        incremented_keys = [call.args[0] for call in mock_increment.call_args_list]
        self.assertIn("orchestrator.tool_calls_total", incremented_keys)
        self.assertIn("orchestrator.tool_calls.calculator.total", incremented_keys)

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

    def test_process_request_uses_isolated_registry_per_run(self):
        """
        Concurrent calls to process_request must not share tool registry state.

        Each call must build its own ToolRegistry so that selected_documents from
        one run cannot leak into another run that uses different documents.
        """
        captured_registries = {}
        capture_lock = threading.Lock()
        overlap_barrier = threading.Barrier(2, timeout=5)

        def capturing_build(conversation_id, tool_registry, **kwargs):
            with capture_lock:
                captured_registries[conversation_id] = tool_registry

            # Return a minimal mock agent that mimics the LangGraph interface
            mock_agent = MagicMock()

            def invoke(*args, **kwargs):
                overlap_barrier.wait()
                return {"messages": []}

            mock_agent.invoke.side_effect = invoke
            return mock_agent

        docs_a = ["doc-a"]
        docs_b = ["doc-b"]

        with patch.object(self.orchestrator, '_build_orchestrator_agent', side_effect=capturing_build), \
             patch.object(self.orchestrator, '_ensure_llm'), \
             patch('backend.orchestrator.core.db_ops') as mock_db_ops, \
             patch('backend.orchestrator.core.observe_operation') as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None

            def run_request(message, conversation_id, selected_documents):
                asyncio.run(self.orchestrator.process_request(
                    message, conversation_id, selected_documents=selected_documents
                ))

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(run_request, "hello from A", "conv-a", docs_a),
                    executor.submit(run_request, "hello from B", "conv-b", docs_b),
                ]
                for future in futures:
                    future.result(timeout=5)

        self.assertEqual(set(captured_registries), {"conv-a", "conv-b"})
        self.assertIsNot(
            captured_registries["conv-a"],
            captured_registries["conv-b"],
            "Each run must receive a distinct ToolRegistry instance",
        )
        self.assertEqual(captured_registries["conv-a"].selected_documents, docs_a)
        self.assertEqual(captured_registries["conv-b"].selected_documents, docs_b)

    def test_process_request_does_not_store_agent_on_self(self):
        """process_request must not write orchestrator_agent back to self."""
        with patch.object(self.orchestrator, '_build_orchestrator_agent') as mock_build, \
             patch.object(self.orchestrator, '_ensure_llm'), \
             patch('backend.orchestrator.core.db_ops') as mock_db_ops, \
             patch('backend.orchestrator.core.observe_operation') as mock_obs:
            mock_obs.return_value.__enter__ = Mock(return_value=None)
            mock_obs.return_value.__exit__ = Mock(return_value=False)
            mock_db_ops.get_conversation_history.return_value = []
            mock_db_ops.save_message.return_value = None
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {"messages": []}
            mock_build.return_value = mock_agent

            asyncio.run(self.orchestrator.process_request(
                "test", "conv-x", selected_documents=[]
            ))

        self.assertFalse(hasattr(self.orchestrator, 'orchestrator_agent'),
                         "orchestrator_agent must not be stored as instance state")
        self.assertFalse(hasattr(self.orchestrator, 'current_conversation_id'),
                         "current_conversation_id must not be stored as instance state")


if __name__ == '__main__':
    unittest.main()
