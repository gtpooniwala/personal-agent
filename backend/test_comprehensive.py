#!/usr/bin/env python3
"""
Comprehensive test suite for Personal Agent behavior.
Tests that tools are only called when needed and responses are appropriate.
Includes RAG (document Q&A) functionality testing.
"""

import sys
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
import json

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from orchestrator.core import CoreOrchestrator

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise

def display_orchestrator_prompt():
    """Display the orchestrator prompt being used in tests."""
    print("🤖 ORCHESTRATOR PROMPT USED IN TESTS:")
    print("=" * 90)
    
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
    print("=" * 90)
    print()

class AgentTester:
    def __init__(self):
        self.orchestrator = CoreOrchestrator()
        self.results = []
        self.failed_tests = []
        
    async def test_query(self, query: str, expected_tool_usage: Optional[str] = None, 
                        should_not_use_tools: bool = False, 
                        description: str = "") -> Dict[str, Any]:
        """
        Test a single query and validate tool usage.
        
        Args:
            query: The user query to test
            expected_tool_usage: Name of tool that should be used (if any)
            should_not_use_tools: Whether this query should NOT use any tools
            description: Description of what this test validates
        """
        print(f"\n🧪 Testing: {query}")
        print(f"   Expected: {description}")
        
        try:
            # Process the query
            result = await self.orchestrator.process_request(
                user_request=query, 
                conversation_id="test-conversation"
            )
            response = result.get("response", "")
            
            # Extract tool usage information from response and orchestration actions
            tools_used = self._extract_tools_used(response, result)
            
            # Validate tool usage
            test_result = {
                "query": query,
                "description": description,
                "response": response,
                "tools_used": tools_used,
                "expected_tool": expected_tool_usage,
                "should_not_use_tools": should_not_use_tools,
                "passed": False,
                "reason": ""
            }
            
            # Check if test passed
            if should_not_use_tools:
                if not tools_used:
                    test_result["passed"] = True
                    test_result["reason"] = "✅ Correctly avoided using tools"
                else:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Unexpectedly used tools: {tools_used}"
            elif expected_tool_usage:
                if len(tools_used) == 1 and expected_tool_usage in tools_used:
                    test_result["passed"] = True
                    test_result["reason"] = f"✅ Correctly used only {expected_tool_usage}"
                elif expected_tool_usage in tools_used and len(tools_used) > 1:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Used {expected_tool_usage} but also used other tools: {tools_used}"
                elif expected_tool_usage not in tools_used:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Expected {expected_tool_usage}, got {tools_used}"
                else:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Unexpected tool usage pattern: {tools_used}"
            else:
                # No specific expectation, just check for reasonable response
                if response and response.strip() and response.lower() not in ["n/a", "none"]:
                    test_result["passed"] = True
                    test_result["reason"] = "✅ Provided reasonable response"
                else:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Poor response: '{response}'"
            
            print(f"   Result: {test_result['reason']}")
            print(f"   Response: {response[:100]}{'...' if len(response) > 100 else ''}")
            
            self.results.append(test_result)
            
            if not test_result["passed"]:
                self.failed_tests.append(test_result)
                
            return test_result
            
        except Exception as e:
            error_result = {
                "query": query,
                "description": description,
                "error": str(e),
                "passed": False,
                "reason": f"❌ Exception: {str(e)}"
            }
            print(f"   Result: {error_result['reason']}")
            self.results.append(error_result)
            self.failed_tests.append(error_result)
            return error_result
    
    def _extract_tools_used(self, response: str, result: Dict[str, Any]) -> List[str]:
        """Extract tool names from agent response by looking for tool usage patterns."""
        tools_used = []
        
        # Check orchestration_actions first (most reliable)
        orchestration_actions = result.get("orchestration_actions", [])
        if orchestration_actions:
            for action in orchestration_actions:
                if isinstance(action, dict):
                    tool_name = action.get("tool", "").lower()
                    if tool_name:
                        tools_used.append(tool_name)
        
        # Only rely on orchestration_actions, not response text patterns
        # Response text patterns were causing false positives
        return tools_used
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        # 1. GREETINGS - Should NOT use tools
        print("\n📋 Category 1: Greetings (should NOT use tools)")
        greeting_tests = [
            ("hi", "Simple greeting"),
            ("hello", "Simple greeting"),
            ("hey there", "Casual greeting"),
            ("how are you?", "Personal greeting"),
            ("what's up", "Casual greeting"),
        ]
        
        for query, desc in greeting_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 2. GENERAL CONVERSATION - Should NOT use tools
        print("\n📋 Category 2: General Conversation (should NOT use tools)")
        conversation_tests = [
            ("How can you help me?", "General capability question"),
            ("What can you do?", "Capability inquiry"),
            ("Thank you", "Gratitude expression"),
            ("That's interesting", "Conversational response"),
        ]
        
        for query, desc in conversation_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 3. MATHEMATICAL CALCULATIONS - Should use calculator
        print("\n📋 Category 3: Mathematical Calculations (should use calculator)")
        math_tests = [
            ("What is 15 + 27?", "Simple addition"),
            ("Calculate 123 * 456", "Multiplication"),
            ("What's 1000 divided by 25?", "Division"),
            ("What is 100 - 37?", "Subtraction"),
        ]
        
        for query, desc in math_tests:
            await self.test_query(query, expected_tool_usage="calculator", description=desc)
        
        # 4. TIME QUERIES - Should use current_time
        print("\n📋 Category 4: Time Queries (should use current_time)")
        time_tests = [
            ("What time is it?", "Direct time query"),
            ("What's the current time?", "Current time request"),
            ("Tell me the time", "Time request"),
        ]
        
        for query, desc in time_tests:
            await self.test_query(query, expected_tool_usage="current_time", description=desc)
        
        # 5. SCRATCHPAD TESTS - Should use scratchpad tool  
        print("\n📋 Category 5: Scratchpad Tool Tests (should use scratchpad)")
        scratchpad_tests = [
            ("Save a note that the user prefers morning meetings", "Agent saves context"),
            ("Remember that the current task is planning a trip", "Agent saves task context"),
            ("Add to scratchpad: user mentioned budget of $5000", "Agent saves important details"),
            ("Show my scratchpad", "Agent reads context"),
            ("What context do I have saved?", "Agent displays context"),
            ("Search scratchpad for budget", "Agent searches context"),
            ("Update note 1 with new information", "Agent updates context"),
            ("Clear my scratchpad when done", "Agent clears context"),
            ("Save progress: completed step 1 of the plan", "Agent tracks progress"),
            ("Remember the user's timezone is PST", "Agent saves user preference"),
        ]
        
        for query, desc in scratchpad_tests:
            await self.test_query(query, expected_tool_usage="scratchpad", description=desc)
        
        # 6. DOCUMENT Q&A (RAG) - Conceptual tests without actual documents
        print("\n📋 Category 6: Document Q&A (RAG) Behavior Tests")
        rag_tests = [
            ("What information is in my documents?", "Document query without actual documents"),
            ("Tell me about the uploaded files", "File query without actual documents"),
            ("Search my documents for information about AI", "Search query without actual documents"),
        ]
        
        # These should not use tools since no documents are actually selected
        for query, desc in rag_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 7. PROBLEMATIC HISTORICAL CASES - Should NOT use tools inappropriately
        print("\n📋 Category 7: Previously Problematic Cases")
        problematic_tests = [
            ("hi", "Historical issue: returned '12' from calculator"),
            ("hello", "Historical issue: returned 'N/A'"),
            ("how are you", "Historical issue: empty response"),
        ]
        
        for query, desc in problematic_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
    
    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.get("passed", False))
        failed_tests = len(self.failed_tests)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS ({len(self.failed_tests)}):")
            print("-" * 40)
            for i, test in enumerate(self.failed_tests, 1):
                print(f"{i}. Query: '{test['query']}'")
                print(f"   Description: {test['description']}")
                print(f"   Reason: {test['reason']}")
                if 'tools_used' in test:
                    print(f"   Tools Used: {test['tools_used']}")
                if 'response' in test:
                    response_preview = test['response'][:150] + "..." if len(test['response']) > 150 else test['response']
                    print(f"   Response: {response_preview}")
                print()
        
        return passed_tests == total_tests

async def main():
    """Main test runner."""
    print("🚀 Starting Comprehensive Agent Test Suite")
    print("=" * 60)
    
    # Display the orchestrator prompt at the start
    display_orchestrator_prompt()
    
    tester = AgentTester()
    
    try:
        await tester.run_all_tests()
        success = tester.print_summary()
        
        # Save detailed results to file
        with open("test_results.json", "w") as f:
            json.dump(tester.results, f, indent=2)
        print(f"\n💾 Detailed results saved to test_results.json")
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
