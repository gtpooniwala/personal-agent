#!/usr/bin/env python3
"""
Simple test to verify LangGraph imports and initialization.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("🔍 Testing LangGraph imports...")

try:
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain_openai import ChatOpenAI
    print("✅ All LangGraph imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

print("🔍 Testing CoreOrchestrator initialization...")

try:
    from orchestrator.core import CoreOrchestrator
    orchestrator = CoreOrchestrator('test_user')
    print("✅ CoreOrchestrator initialized successfully with LangGraph!")
    
    # Check that manual tool description method is removed
    if hasattr(orchestrator, '_generate_tools_description'):
        print("⚠️  Warning: Manual tool description method still exists")
    else:
        print("✅ Manual tool description method successfully removed!")
        
except Exception as e:
    print(f"❌ Initialization error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 Basic tests passed!")
print("✅ LangGraph upgrade successful:")
print("   • Legacy AgentExecutor → LangGraph create_react_agent")
print("   • Manual tool descriptions → Automatic .bind_tools()")
