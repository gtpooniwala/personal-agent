#!/usr/bin/env python3
"""
Simple test to validate agent behavior
"""

import sys
import os
import asyncio

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.core import PersonalAgent

async def test_basic_agent():
    agent = PersonalAgent()
    
    print("🧪 Testing basic agent functionality...")
    
    # Test 1: Simple greeting (should NOT use tools)
    print("\n1. Testing greeting:")
    result = await agent.process_message("hi", "test-conversation")
    response = result.get("response", "")
    agent_actions = result.get("agent_actions", [])
    
    print(f"   Query: hi")
    print(f"   Response: {response}")
    print(f"   Tools used: {agent_actions}")
    
    # Test 2: Math calculation (should use calculator)
    print("\n2. Testing math calculation:")
    result = await agent.process_message("what is 5 + 3?", "test-conversation")
    response = result.get("response", "")
    agent_actions = result.get("agent_actions", [])
    
    print(f"   Query: what is 5 + 3?")
    print(f"   Response: {response}")
    print(f"   Tools used: {agent_actions}")
    
    # Test 3: Time query (should use current_time)
    print("\n3. Testing time query:")
    result = await agent.process_message("what time is it?", "test-conversation")
    response = result.get("response", "")
    agent_actions = result.get("agent_actions", [])
    
    print(f"   Query: what time is it?")
    print(f"   Response: {response}")
    print(f"   Tools used: {agent_actions}")
    
    print("\n✅ Basic tests completed!")

if __name__ == "__main__":
    asyncio.run(test_basic_agent())
