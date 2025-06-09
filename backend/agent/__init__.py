# Backward compatibility layer - redirect to orchestrator
from orchestrator import CoreOrchestrator
from orchestrator.memory import SQLiteConversationMemory

# Create PersonalAgent as an alias for CoreOrchestrator for backward compatibility
PersonalAgent = CoreOrchestrator

# Legacy tool imports - redirect to orchestrator tools
from orchestrator.tool_registry import ToolRegistry
from orchestrator.tools.calculator import CalculatorTool as BaseServiceTool

__all__ = ['PersonalAgent', 'SQLiteConversationMemory', 'ToolRegistry', 'BaseServiceTool']
