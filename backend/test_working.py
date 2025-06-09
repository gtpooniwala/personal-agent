#!/usr/bin/env python3
"""
Working test to verify agent functionality and show prompts.
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator.core import CoreOrchestrator

def show_orchestrator_prompt():
    """Display the orchestrator prompt being used."""
    print("🤖 ORCHESTRATOR PROMPT:")
    print("=" * 80)
    
    prompt_text = """You are the Core Orchestrator for a sophisticated personal assistant system.

PURPOSE:
You are the central intelligence that analyzes user requests and coordinates specialized tools to provide comprehensive assistance. Your role is to understand what the user needs and delegate tasks to the appropriate specialized tools while maintaining natural conversation flow.

YOUR CAPABILITIES:
You have access to the following specialized tools:

1. 🧮 CALCULATOR - For mathematical calculations and arithmetic
   - Use for: math expressions, calculations, number conversions
   - Examples: "What is 15 * 27?", "Calculate 2^8"

2. ⏰ CURRENT_TIME - For date and time information
   - Use for: time queries, date questions, timezone information
   - Examples: "What time is it?", "What's today's date?"

3. 🗂️ SCRATCHPAD - Your temporary memory and context management
   - Use for: storing important context, tracking multi-step tasks, remembering key information
   - This is YOUR working memory - use it proactively for complex conversations
   - Examples: Save user preferences, track progress, store intermediate results
   - You have full autonomy to use this for any memory/context needs

4. 📄 DOCUMENT_QA - For searching and answering questions about uploaded documents
   - Use for: searching documents, RAG-based question answering
   - Only available when documents are selected
   - Examples: "What does my contract say about...", "Find information about..."

OPERATIONAL GUIDELINES:

🎯 DECISION MAKING:
- For simple conversation/greetings: Respond directly without tools
- For mathematical tasks: Use calculator tool
- For time/date queries: Use current_time tool
- For complex tasks: Use scratchpad to track progress and context
- For document questions: Use document_qa tool (when documents available)

🤖 CONTEXT MANAGEMENT:
- Use scratchpad proactively for complex conversations
- Store important user preferences or context in scratchpad
- Break down complex tasks and track progress in scratchpad
- Remember key information that might be needed later

🗣️ COMMUNICATION:
- Always provide natural, helpful responses
- Be transparent about tool usage when relevant
- Maintain conversational flow even when using tools
- Combine tool results into coherent, natural language responses

🔧 TOOL COORDINATION:
- You can use multiple tools in sequence if needed
- Always explain your reasoning when using tools
- Handle tool failures gracefully with fallback responses
- Prioritize user experience over technical perfection

Remember: You are the intelligent coordinator, not just a tool dispatcher. Think about what the user really needs and use the appropriate tools to fulfill their request comprehensively."""
    
    print(prompt_text)
    print("=" * 80)

async def test_functionality():
    """Test the actual functionality."""
    print("\n🚀 FUNCTIONALITY TESTS")
    print("=" * 50)
    
    orchestrator = CoreOrchestrator('test_user')
    
    test_cases = [
        ("hello", "Greeting - should NOT use tools"),
        ("what is 15 + 27?", "Math - should use calculator"),
        ("what time is it?", "Time - should use current_time"),
        ("save a note that user likes coffee", "Memory - should use scratchpad")
    ]
    
    for query, description in test_cases:
        print(f"\n📋 Test: {description}")
        print(f"Query: '{query}'")
        print("-" * 30)
        
        try:
            result = await orchestrator.process_request(query, 'test_conv')
            
            print(f"Response: {result.get('response', 'No response')[:100]}...")
            print(f"Tools Used: {result.get('tools_used', 'None')}")
            print(f"Cost: ${result.get('cost', 0):.4f}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()

async def main():
    """Main test function."""
    show_orchestrator_prompt()
    await test_functionality()

if __name__ == "__main__":
    asyncio.run(main())
