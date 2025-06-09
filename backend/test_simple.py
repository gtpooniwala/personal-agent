#!/usr/bin/env python3
"""
Simple test script to verify agent functionality and show prompts.
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator.core import CoreOrchestrator

async def test_with_prompt_display():
    """Test the orchestrator and display the prompts being used."""
    
    print("🚀 Simple Agent Test with Prompt Display")
    print("=" * 60)
    
    orchestrator = CoreOrchestrator('test_user')
    
    # Test cases with expected behavior
    test_cases = [
        {
            "query": "hello",
            "expected": "Simple greeting - should NOT use tools",
            "category": "Greeting"
        },
        {
            "query": "what is 15 + 27?",
            "expected": "Should use calculator tool",
            "category": "Math"
        },
        {
            "query": "what time is it?",
            "expected": "Should use current_time tool", 
            "category": "Time"
        },
        {
            "query": "save a note that user likes coffee",
            "expected": "Should use scratchpad tool",
            "category": "Scratchpad"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['category']}")
        print(f"Query: '{test_case['query']}'")
        print(f"Expected: {test_case['expected']}")
        print("-" * 40)
        
        try:
            # Show the orchestrator prompt being used
            print("🤖 Orchestrator Prompt Preview:")
            # Get the prompt from the orchestrator setup
            orchestrator._setup_orchestrator_agent('test_conv')
            
            # Extract prompt from agent (this is tricky with LangChain, so we'll show our configured prompt)
            if hasattr(orchestrator, 'orchestrator_agent') and orchestrator.orchestrator_agent:
                print("✅ Agent initialized successfully")
            else:
                print("❌ Agent not initialized")
                continue
                
            print("\n🔄 Processing request...")
            result = await orchestrator.process_request(test_case['query'], 'test_conv')
            
            print(f"📤 Response: {result.get('response', 'No response')}")
            
            # Show tools used
            tools_used = result.get('tools_used', [])
            if tools_used:
                print(f"🔧 Tools Used: {tools_used}")
            else:
                print("🔧 Tools Used: None")
                
            print(f"💰 Cost: ${result.get('cost', 0):.4f}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_with_prompt_display())
