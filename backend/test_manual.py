#!/usr/bin/env python3
"""
Manual step-by-step agent test
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Step 1: Testing imports...")

try:
    print("Importing PersonalAgent...")
    from agent.core import PersonalAgent
    print("✅ PersonalAgent imported successfully")
    
    print("Creating PersonalAgent instance...")
    agent = PersonalAgent()
    print("✅ PersonalAgent instance created successfully")
    
    print("Getting available tools...")
    tools = agent.get_available_tools()
    print(f"✅ Available tools: {[tool['name'] for tool in tools]}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("Manual test completed!")
