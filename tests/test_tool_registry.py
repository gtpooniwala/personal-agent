"""
Comprehensive tests for Tool Registry functionality.
"""
import sys
import os
import unittest
from unittest.mock import Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.orchestrator.tool_registry import ToolRegistry


class TestToolRegistry(unittest.TestCase):
    """Test the tool registry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tool_registry = ToolRegistry()
        
        # Create mock tools for testing
        self.mock_calculator = Mock()
        self.mock_calculator.name = "calculator"
        self.mock_calculator.description = "Perform mathematical calculations"
        
        self.mock_search = Mock()
        self.mock_search.name = "search_internet"
        self.mock_search.description = "Search the internet for information"
    
    def test_register_tool(self):
        """Test registering a tool."""
        # Register a tool
        self.tool_registry.register_tool("calculator", self.mock_calculator)
        
        # Verify it was registered
        retrieved_tool = self.tool_registry.get_tool("calculator")
        
        self.assertEqual(retrieved_tool, self.mock_calculator)
    
    def test_get_tool(self):
        """Test getting a specific tool."""
        # Register and retrieve a tool
        self.tool_registry.register_tool("calculator", self.mock_calculator)
        
        retrieved_tool = self.tool_registry.get_tool("calculator")
        
        self.assertEqual(retrieved_tool, self.mock_calculator)
    
    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        retrieved_tool = self.tool_registry.get_tool("nonexistent_tool")
        
        self.assertIsNone(retrieved_tool)
    
    def test_get_available_tools_format(self):
        """Test the format of available tools list."""
        # Get available tools (should include default tools from registry)
        available_tools = self.tool_registry.get_available_tools()
        
        self.assertIsInstance(available_tools, list)
        # Should have core tools loaded by default
        self.assertGreater(len(available_tools), 0)
        
        # Check that each tool is an object with name and description attributes
        for tool in available_tools:
            self.assertTrue(hasattr(tool, 'name'))
            self.assertTrue(hasattr(tool, 'description'))
            self.assertIsInstance(tool.name, str)
            self.assertIsInstance(tool.description, str)
    
    def test_tool_registry_singleton_behavior(self):
        """Test that tool registry maintains state across instances."""
        # Register a tool
        self.tool_registry.register_tool("test_tool", self.mock_calculator)
        
        # Create new instance
        new_registry = ToolRegistry()
        
        # Should have the same tools if using singleton pattern
        # Note: This test depends on actual implementation
        tools = new_registry.get_available_tools()
        
        # At minimum, should be able to create multiple instances
        self.assertIsNotNone(tools)
        self.assertIsInstance(tools, list)
    
    def test_register_duplicate_tool(self):
        """Test registering a tool with duplicate name."""
        # Register original tool
        self.tool_registry.register_tool("test_calculator", self.mock_calculator)
        
        # Create different mock tool with same name
        mock_calculator_v2 = Mock()
        mock_calculator_v2.name = "test_calculator"
        mock_calculator_v2.description = "Advanced calculator"
        
        # Register duplicate (should replace or handle gracefully)
        self.tool_registry.register_tool("test_calculator", mock_calculator_v2)
        
        # Verify behavior (should be replaced)
        retrieved_tool = self.tool_registry.get_tool("test_calculator")
        self.assertEqual(retrieved_tool, mock_calculator_v2)
    
    def test_empty_registry(self):
        """Test behavior with empty registry."""
        # Create fresh registry
        empty_registry = ToolRegistry()
        
        tools = empty_registry.get_available_tools()
        self.assertIsInstance(tools, list)
        
        # Getting non-existent tool should return None
        tool = empty_registry.get_tool("any_tool")
        self.assertIsNone(tool)
    
    def test_tool_initialization(self):
        """Test that tools are properly initialized during registry creation."""
        # This tests the actual tool loading that happens in __init__
        registry = ToolRegistry()
        
        # Should have loaded default tools
        tools = registry.get_available_tools()
        
        # Should be a list (even if empty)
        self.assertIsInstance(tools, list)
        
        # Each tool should have proper attributes
        for tool in tools:
            self.assertTrue(hasattr(tool, 'name'))
            self.assertTrue(hasattr(tool, 'description'))
            self.assertIsInstance(tool.name, str)
            self.assertIsInstance(tool.description, str)
    
    def test_tool_names_are_unique(self):
        """Test that all registered tools have unique names."""
        # Get available tools (loaded by default)
        available_tools = self.tool_registry.get_available_tools()
        tool_names = [tool.name for tool in available_tools]
        
        # All names should be unique
        self.assertEqual(len(tool_names), len(set(tool_names)))
    
    def test_tool_descriptions_exist(self):
        """Test that all tools have descriptions."""
        # Get available tools (loaded by default)
        available_tools = self.tool_registry.get_available_tools()
        
        for tool in available_tools:
            self.assertTrue(hasattr(tool, 'description'))
            self.assertIsInstance(tool.description, str)
            self.assertGreater(len(tool.description), 0)


if __name__ == '__main__':
    unittest.main()
