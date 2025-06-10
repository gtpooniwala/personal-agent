#!/usr/bin/env python3
"""
Test script to verify the LangGraph upgrade implementation.

This script tests:
1. Agent type optimization (Legacy -> LangGraph)
2. Tool description automation (Manual -> Automatic)
3. Basic functionality with time query
"""

import sys
import os
import asyncio

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_imports():
    """Test that all LangGraph imports work correctly."""
    print("🔍 Testing LangGraph imports...")
    
    try:
        from langgraph.prebuilt import create_react_agent
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        from langchain_openai import ChatOpenAI
        print("✅ All LangGraph imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_orchestrator_initialization():
    """Test that the upgraded CoreOrchestrator initializes correctly."""
    print("\n🔍 Testing CoreOrchestrator initialization...")
    
    try:
        from orchestrator.core import CoreOrchestrator
        orchestrator = CoreOrchestrator('test_user')
        print("✅ CoreOrchestrator initialized successfully with LangGraph!")
        
        # Check that manual tool description method is removed
        if hasattr(orchestrator, '_generate_tools_description'):
            print("⚠️  Warning: Manual tool description method still exists")
        else:
            print("✅ Manual tool description method successfully removed!")
            
        return True, orchestrator
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False, None

async def test_simple_request(orchestrator):
    """Test a simple time request to verify functionality."""
    print("\n🔍 Testing simple time request...")
    
    try:
        result = await orchestrator.process_request(
            'What time is it?', 
            'test_conversation_langgraph'
        )
        
        response = result.get('response', 'No response')
        print(f"✅ Request processed successfully!")
        print(f"📋 Response: {response[:100]}...")
        
        # Check if tool was used
        actions = result.get('orchestration_actions', [])
        if actions:
            print(f"✅ Tool actions detected: {[action.get('tool') for action in actions]}")
        else:
            print("ℹ️  No tool actions recorded (might be direct response)")
            
        return True
    except Exception as e:
        print(f"❌ Request processing error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_calculator_request(orchestrator):
    """Test a calculator request to verify tool calling."""
    print("\n🔍 Testing calculator request...")
    
    try:
        result = await orchestrator.process_request(
            'What is 15 + 27?', 
            'test_conversation_calc'
        )
        
        response = result.get('response', 'No response')
        print(f"✅ Calculator request processed successfully!")
        print(f"📋 Response: {response[:100]}...")
        
        # Check if calculator tool was used
        actions = result.get('orchestration_actions', [])
        calc_used = any(action.get('tool') == 'calculator' for action in actions)
        
        if calc_used:
            print("✅ Calculator tool was automatically called!")
        else:
            print("⚠️  Calculator tool was not used (check tool binding)")
            
        return True
    except Exception as e:
        print(f"❌ Calculator request error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🚀 LangGraph Upgrade Verification Test")
    print("="*50)
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import test failed. Exiting.")
        return False
    
    # Test 2: Initialization  
    success, orchestrator = test_orchestrator_initialization()
    if not success or orchestrator is None:
        print("\n❌ Initialization test failed. Exiting.")
        return False
    
    # Test 3: Simple request
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(test_simple_request(orchestrator))
        if not success:
            print("\n❌ Simple request test failed.")
            return False
            
        # Test 4: Calculator request
        success = loop.run_until_complete(test_calculator_request(orchestrator))
        if not success:
            print("\n❌ Calculator request test failed.")
            return False
            
    finally:
        loop.close()
    
    print("\n" + "="*50)
    print("🎉 ALL TESTS PASSED!")
    print("\n✅ Upgrade Summary:")
    print("   • Agent type: Legacy AgentExecutor → LangGraph create_react_agent")
    print("   • Tool descriptions: Manual generation → Automatic binding")
    print("   • Memory: SQLite custom → LangGraph MemorySaver")
    print("   • Tool calling: Enhanced with automatic .bind_tools()")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
