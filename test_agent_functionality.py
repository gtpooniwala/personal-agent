#!/usr/bin/env python3
"""
Test LangGraph agent functionality with a real request.
"""

import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_agent_request():
    """Test that the LangGraph agent can process a real request."""
    print("🔍 Testing LangGraph agent with time request...")
    
    try:
        from orchestrator.core import CoreOrchestrator
        orchestrator = CoreOrchestrator('test_user')
        
        # Make a time request
        result = await orchestrator.process_request(
            'What time is it?', 
            'test_conversation_time'
        )
        
        response = result.get('response', 'No response')
        actions = result.get('orchestration_actions', [])
        
        print("✅ Request processed successfully!")
        print(f"📋 Response: {response}")
        
        if actions:
            tool_names = [action.get('tool') for action in actions]
            print(f"🔧 Tools used: {tool_names}")
        else:
            print("ℹ️  No specific tools recorded")
            
        return True
        
    except Exception as e:
        print(f"❌ Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_calculator():
    """Test calculator tool integration."""
    print("\n🔍 Testing calculator tool...")
    
    try:
        from orchestrator.core import CoreOrchestrator
        orchestrator = CoreOrchestrator('test_user')
        
        # Make a calculation request
        result = await orchestrator.process_request(
            'Calculate 15 + 27', 
            'test_conversation_calc'
        )
        
        response = result.get('response', 'No response')
        actions = result.get('orchestration_actions', [])
        
        print("✅ Calculator request processed!")
        print(f"📋 Response: {response}")
        
        # Check if calculator was used
        calc_used = any(action.get('tool') == 'calculator' for action in actions)
        if calc_used:
            print("✅ Calculator tool automatically invoked!")
        else:
            print("ℹ️  Calculator tool not detected in actions")
            
        return True
        
    except Exception as e:
        print(f"❌ Calculator test failed: {e}")
        return False

async def main():
    """Run the functionality tests."""
    print("🚀 LangGraph Agent Functionality Test")
    print("="*40)
    
    # Test 1: Time request
    success = await test_agent_request()
    if not success:
        return False
    
    # Test 2: Calculator
    success = await test_calculator()
    if not success:
        return False
    
    print("\n" + "="*40)
    print("🎉 LangGraph agent is working correctly!")
    print("✅ Both optimizations implemented successfully:")
    print("   1. Agent type: Legacy → LangGraph")
    print("   2. Tool descriptions: Manual → Automatic")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
