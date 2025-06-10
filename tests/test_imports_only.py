#!/usr/bin/env python3
"""
Simple synchronous test to validate LangGraph orchestrator imports
"""

import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

print("Testing LangGraph orchestrator imports...")

try:
    from orchestrator.core import CoreOrchestrator
    print("✅ CoreOrchestrator import successful")
except Exception as e:
    print(f"❌ CoreOrchestrator import failed: {e}")

try:
    from orchestrator.tool_registry import ToolRegistry
    print("✅ ToolRegistry import successful")
except Exception as e:
    print(f"❌ ToolRegistry import failed: {e}")

try:
    from config import settings
    print("✅ Settings import successful")
except Exception as e:
    print(f"❌ Settings import failed: {e}")

try:
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    print("✅ LangGraph imports successful")
except Exception as e:
    print(f"❌ LangGraph imports failed: {e}")

print("Import test completed!")
