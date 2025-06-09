from typing import Dict, List, Type, Any, Optional
from orchestrator.tools.calculator import CalculatorTool
from orchestrator.tools.time import CurrentTimeTool
from orchestrator.tools.document_qa import DocumentQATool
from orchestrator.tools.scratchpad import ScratchpadTool
from orchestrator.tools.integrations import GmailTool, CalendarTool, TodoistTool
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for managing available tools and agents in the orchestrator system.
    
    This is the central hub that:
    1. Manages all available tools/agents
    2. Handles tool lifecycle (initialization, updates, etc.)
    3. Provides tools to the orchestrator based on context
    4. Supports dynamic tool addition/removal
    
    The registry makes it easy to add new tools - just implement the tool
    and register it here. The orchestrator will automatically discover it.
    """
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        self.user_id = user_id
        self.selected_documents = selected_documents or []
        self._tools = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """
        Initialize all available tools/agents.
        
        This is where new tools are registered. To add a new tool:
        1. Import it at the top of this file
        2. Add it to this method
        3. That's it! The orchestrator will automatically discover it.
        """
        # Core computational tools (always available)
        self._tools["calculator"] = CalculatorTool()
        self._tools["current_time"] = CurrentTimeTool()
        self._tools["scratchpad"] = ScratchpadTool(self.user_id)
        
        # Context-dependent tools (available based on user state)
        self._tools["document_qa"] = DocumentQATool(self.user_id, self.selected_documents)
        
        # Future integration tools (placeholders for now)
        self._tools["gmail"] = GmailTool()
        self._tools["calendar"] = CalendarTool()
        self._tools["todoist"] = TodoistTool()
    
    def update_selected_documents(self, selected_documents: List[str]):
        """
        Update the context for document-dependent tools.
        
        This demonstrates how tools can be dynamically reconfigured
        based on changing user context.
        """
        self.selected_documents = selected_documents
        # Reinitialize document QA tool with new context
        self._tools["document_qa"] = DocumentQATool(self.user_id, self.selected_documents)
        logger.info(f"Updated tool registry with {len(selected_documents)} selected documents")
    
    def get_available_tools(self) -> List[Any]:
        """
        Get list of tools that should be available to the orchestrator.
        
        This method determines which tools are actually provided to the orchestrator
        based on current context. For example, document_qa is only provided
        when documents are selected.
        """
        # Always include basic computational tools
        available_tools = ["calculator", "current_time", "scratchpad"]
        
        # Context-dependent tool inclusion
        if len(self.selected_documents) > 0:
            available_tools.append("document_qa")
        
        # Future: Add more conditional tool inclusion logic here
        # if self.user_has_gmail_access:
        #     available_tools.append("gmail")
        
        return [self._tools[tool_name] for tool_name in available_tools]
    
    def get_all_tools(self) -> List[Any]:
        """Get all tools including inactive/placeholder ones."""
        return list(self._tools.values())
    
    def register_tool(self, name: str, tool: Any):
        """
        Register a new tool with the registry.
        
        This allows dynamic tool addition at runtime.
        
        Args:
            name: Unique identifier for the tool
            tool: Tool instance implementing the required interface
        """
        self._tools[name] = tool
        logger.info(f"Registered new tool: {name}")
    
    def unregister_tool(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Returns:
            bool: True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get_tool(self, name: str) -> Any:
        """Get a specific tool by name."""
        return self._tools.get(name)
    
    def list_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())
    
    def get_tool_info(self) -> List[Dict[str, str]]:
        """Get information about all registered tools."""
        return [
            {
                "name": name,
                "description": getattr(tool, 'description', 'No description available'),
                "active": name in [t.name for t in self.get_available_tools()]
            }
            for name, tool in self._tools.items()
        ]
