"""
Comprehensive tests for the Core Orchestrator functionality.
"""
import sys
import os
import asyncio
import unittest
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.orchestrator.core import CoreOrchestrator
from backend.database.operations import db_ops


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


if __name__ == '__main__':
    unittest.main()
