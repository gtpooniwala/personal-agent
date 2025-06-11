#!/usr/bin/env python3
"""
Debug test to see what's happening with the orchestrator.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.core import CoreOrchestrator

def debug_orchestrator():
    """Debug the orchestrator setup and show the prompt."""
    
    print("🚀 Debug Orchestrator Test")
    print("=" * 50)
    
    try:
        orchestrator = CoreOrchestrator('test_user')
        print("✅ Orchestrator created")
        
        # Setup the agent
        orchestrator._setup_orchestrator_agent('test_conv')
        print("✅ Agent setup called")
        
        # Check if agent was created
        if orchestrator.orchestrator_agent:
            print("✅ Agent created successfully")
            print(f"Agent type: {type(orchestrator.orchestrator_agent)}")
        else:
            print("❌ Agent is None")
            return
            
        # Show available tools
        tools = orchestrator.tool_registry.get_available_tools()
        print(f"🔧 Available tools: {[tool.name for tool in tools]}")
        
        # Try to show the prompt (this might not work directly)
        print("\n🤖 Trying to extract prompt information...")
        
        # Test a simple call
        print("\n📞 Testing simple synchronous call...")
        # We can't easily test async here, so let's just verify the setup worked
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_orchestrator()
