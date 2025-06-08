#!/usr/bin/env python3
import sys
import os
sys.path.append('/Users/gauravpooniwala/Documents/code/projects/personal-agent/backend')

import asyncio
from agent.core import PersonalAgent
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_behavior():
    """Test agent behavior with simple greetings"""
    print("Testing agent behavior with simple greetings...")
    
    agent = PersonalAgent()
    conversation_id = agent.create_conversation()
    
    test_messages = [
        "hi",
        "hello", 
        "good morning",
        "what's up"
    ]
    
    for message in test_messages:
        print(f"\n--- Testing: '{message}' ---")
        try:
            result = await agent.process_message(message, conversation_id)
            print(f"Response: {result['response']}")
            print(f"Agent actions: {result.get('agent_actions', 'None')}")
            print(f"Token usage: {result.get('token_usage', 'Unknown')}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_behavior())
