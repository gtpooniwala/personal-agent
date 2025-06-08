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

from agent.core import PersonalAgent

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise

class AgentTester:
    def __init__(self):
        self.agent = PersonalAgent()
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
            result = await self.agent.process_message(query, "test-conversation")
            response = result.get("response", "")
            
            # Extract tool usage information from response and agent actions
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
                if expected_tool_usage in tools_used:
                    test_result["passed"] = True
                    test_result["reason"] = f"✅ Correctly used {expected_tool_usage}"
                else:
                    test_result["passed"] = False
                    test_result["reason"] = f"❌ Expected {expected_tool_usage}, got {tools_used}"
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
        
        # Check agent_actions first (most reliable)
        agent_actions = result.get("agent_actions", [])
        if agent_actions:
            for action in agent_actions:
                if isinstance(action, dict):
                    tool_name = action.get("tool", "").lower()
                    if tool_name:
                        tools_used.append(tool_name)
        
        # Only rely on agent_actions, not response text patterns
        # Response text patterns were causing false positives
        return tools_used
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        print("🚀 Starting Comprehensive Agent Test Suite")
        print("=" * 60)
        
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
        
        # 5. DOCUMENT Q&A (RAG) - Conceptual tests without actual documents
        print("\n📋 Category 5: Document Q&A (RAG) Behavior Tests")
        rag_tests = [
            ("What information is in my documents?", "Document query without actual documents"),
            ("Tell me about the uploaded files", "File query without actual documents"),
            ("Search my documents for information about AI", "Search query without actual documents"),
        ]
        
        # These should not use tools since no documents are actually selected
        for query, desc in rag_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 6. PROBLEMATIC HISTORICAL CASES - Should NOT use tools inappropriately
        print("\n📋 Category 6: Previously Problematic Cases")
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
