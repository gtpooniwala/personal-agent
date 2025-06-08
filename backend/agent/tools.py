from langchain.tools import BaseTool
from typing import Dict, List, Type, Any
from datetime import datetime
import math


class CalculatorTool(BaseTool):
    """Simple calculator tool for basic math operations."""
    
    name = "calculator"
    description = "Useful for performing basic mathematical calculations. Input should be a mathematical expression like '2+3', '10*5', '2**4' for powers."
    
    def _run(self, query: str) -> str:
        """Execute the calculator tool."""
        try:
            # Replace ^ with ** for exponentiation
            query = query.replace('^', '**')
            
            # Simple safety check for basic math expressions
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in query):
                return "Error: Invalid characters in mathematical expression"
            
            # Evaluate the expression
            result = eval(query)
            return f"The result is: {result}"
        except Exception as e:
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool."""
        return self._run(query)


class CurrentTimeTool(BaseTool):
    """Tool to get the current date and time."""
    
    name = "current_time"
    description = "Get the current date and time. Use this when asked about the current time, date, or 'what time is it'. Input: just use 'now' or leave empty."
    
    def _run(self, query: str = "now") -> str:
        """Get current time."""
        now = datetime.now()
        return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    async def _arun(self, query: str = "now") -> str:
        """Async version of the tool."""
        return self._run(query)


class BaseServiceTool(BaseTool):
    """Base class for future service integration tools."""
    
    def __init__(self, user_id: str = "default"):
        super().__init__()
        # Store user_id as a private attribute to avoid Pydantic field issues
        self._user_id = user_id
    
    def _run(self, query: str) -> str:
        """Base implementation to be overridden."""
        raise NotImplementedError("Service tools must implement _run method")
    
    async def _arun(self, query: str) -> str:
        """Base async implementation."""
        return self._run(query)


# Placeholder tools for future implementation
class GmailTool(BaseTool):
    """Gmail integration tool - placeholder for future implementation."""
    
    name = "gmail_search"
    description = "Search and read Gmail emails. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Gmail integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class CalendarTool(BaseTool):
    """Google Calendar integration tool - placeholder for future implementation."""
    
    name = "calendar_events"
    description = "Get calendar events and schedule meetings. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Calendar integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class TodoistTool(BaseTool):
    """Todoist integration tool - placeholder for future implementation."""
    
    name = "todoist_tasks"
    description = "Manage tasks with Todoist. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Todoist integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._tools = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize available tools."""
        # MVP tools that work
        self._tools["calculator"] = CalculatorTool()
        self._tools["current_time"] = CurrentTimeTool()
        
        # Placeholder tools for future implementation (no user_id needed for now)
        self._tools["gmail"] = GmailTool()
        self._tools["calendar"] = CalendarTool()
        self._tools["todoist"] = TodoistTool()
    
    def get_available_tools(self) -> List[BaseTool]:
        """Get list of available tools for the agent."""
        # For MVP, only return working tools
        working_tools = ["calculator", "current_time"]
        return [self._tools[tool_name] for tool_name in working_tools]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all tools including placeholders."""
        return list(self._tools.values())
    
    def add_tool(self, name: str, tool: BaseTool):
        """Add a new tool to the registry."""
        self._tools[name] = tool
    
    def get_tool(self, name: str) -> BaseTool:
        """Get a specific tool by name."""
        return self._tools.get(name)
