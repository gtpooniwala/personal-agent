#!/usr/bin/env python3
"""
Comprehensive test suite for Personal Agent behavior.
Tests that tools are only called when needed and responses are appropriate.
"""

import sys
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
import re
import json

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        
        # Also check response text for tool usage patterns
        response_lower = response.lower()
        
        # Check for calculator usage
        if any(word in response_lower for word in ["calculate", "calculator", "computed", "calculation", "math"]):
            if "calculator" not in tools_used:
                tools_used.append("calculator")
            
        # Check for time tool usage
        if any(word in response_lower for word in ["current time", "current_time", "time is", "time:", "am", "pm"]):
            if "current_time" not in tools_used:
                tools_used.append("current_time")
            
        return tools_used
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        print("🚀 Starting Comprehensive Agent Test Suite")
        print("=" * 60)
        
        # Test Categories
        
        # 1. GREETINGS - Should NOT use tools
        print("\n📋 Category 1: Greetings (should NOT use tools)")
        greeting_tests = [
            ("hi", "Simple greeting"),
            ("hello", "Simple greeting"),
            ("hey there", "Casual greeting"),
            ("good morning", "Time-based greeting"),
            ("how are you?", "Personal greeting"),
            ("what's up", "Casual greeting"),
            ("greetings", "Formal greeting"),
            ("hello!", "Greeting with punctuation"),
        ]
        
        for query, desc in greeting_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 2. GENERAL CONVERSATION - Should NOT use tools
        print("\n📋 Category 2: General Conversation (should NOT use tools)")
        conversation_tests = [
            ("How can you help me?", "General capability question"),
            ("What can you do?", "Capability inquiry"),
            ("Tell me about yourself", "Self-description request"),
            ("I'm having a good day", "Personal sharing"),
            ("That's interesting", "Conversational response"),
            ("Thank you", "Gratitude expression"),
            ("Goodbye", "Farewell"),
            ("Nice to meet you", "Social pleasantry"),
            ("I understand", "Acknowledgment"),
            ("Can you help me?", "General help request"),
        ]
        
        for query, desc in conversation_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 3. GENERAL KNOWLEDGE - Should NOT use tools
        print("\n📋 Category 3: General Knowledge (should NOT use tools)")
        knowledge_tests = [
            ("What is the capital of France?", "Geography question"),
            ("Who wrote Romeo and Juliet?", "Literature question"),
            ("What is Python?", "Technology question"),
            ("Explain machine learning", "Technical concept"),
            ("What is the largest planet?", "Science question"),
            ("How does photosynthesis work?", "Biology question"),
            ("What is democracy?", "Political concept"),
            ("Tell me about the Renaissance", "History question"),
            ("What are the primary colors?", "Art/Science question"),
            ("How do computers work?", "Technology explanation"),
        ]
        
        for query, desc in knowledge_tests:
            await self.test_query(query, should_not_use_tools=True, description=desc)
        
        # 4. MATHEMATICAL CALCULATIONS - Should use calculator
        print("\n📋 Category 4: Mathematical Calculations (should use calculator)")
        math_tests = [
            ("What is 15 + 27?", "Simple addition"),
            ("Calculate 123 * 456", "Multiplication"),
            ("What's 1000 divided by 25?", "Division"),
            ("Compute 2 to the power of 8", "Exponentiation"),
            ("What is the square root of 144?", "Square root"),
            ("Calculate 15% of 200", "Percentage calculation"),
            ("What's 25 * 4 + 10?", "Complex arithmetic"),
            ("Solve 2x + 5 = 15", "Simple algebra"),
            ("What is 100 - 37?", "Subtraction"),
            ("Calculate the area of a circle with radius 5", "Geometry calculation"),
        ]
        
        for query, desc in math_tests:
            await self.test_query(query, expected_tool_usage="calculator", description=desc)
        
        # 5. TIME QUERIES - Should use current_time
        print("\n📋 Category 5: Time Queries (should use current_time)")
        time_tests = [
            ("What time is it?", "Direct time query"),
            ("What's the current time?", "Current time request"),
            ("Tell me the time", "Time request"),
            ("What time is it now?", "Present time query"),
            ("Can you tell me what time it is?", "Polite time request"),
            ("I need to know the current time", "Time information need"),
            ("What's the time right now?", "Immediate time query"),
        ]
        
        for query, desc in time_tests:
            await self.test_query(query, expected_tool_usage="current_time", description=desc)
        
        # 6. EDGE CASES - Various expectations
        print("\n📋 Category 6: Edge Cases")
        edge_cases = [
            ("", "Empty query", True),  # Should not use tools
            ("   ", "Whitespace only", True),  # Should not use tools
            ("?", "Question mark only", True),  # Should not use tools
            ("12", "Number only", True),  # Should not use tools
            ("hello what time is it?", "Mixed greeting + time", "current_time"),  # Should use time
            ("hi can you calculate 5+5?", "Mixed greeting + math", "calculator"),  # Should use calculator
            ("time", "Single word - ambiguous", True),  # Should not use tools
            ("calculate", "Single word - ambiguous", True),  # Should not use tools
            ("What is 2+2 and what time is it?", "Multiple tool needs", None),  # Complex case
        ]
        
        for test_case in edge_cases:
            if len(test_case) == 3:
                query, desc, should_not_use = test_case
                if should_not_use is True:
                    await self.test_query(query, should_not_use_tools=True, description=desc)
                else:
                    await self.test_query(query, expected_tool_usage=should_not_use, description=desc)
            else:
                query, desc, expected_tool = test_case
                await self.test_query(query, expected_tool_usage=expected_tool, description=desc)
        
        # 7. PROBLEMATIC HISTORICAL CASES - Should NOT use tools inappropriately
        print("\n📋 Category 7: Previously Problematic Cases")
        problematic_tests = [
            ("hi", "Historical issue: returned '12' from calculator"),
            ("hello", "Historical issue: returned 'N/A'"),
            ("how are you", "Historical issue: empty response"),
            ("nice weather", "Historical issue: inappropriate tool usage"),
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
        
        # Category breakdown
        categories = {
            "Greetings": 0,
            "General Conversation": 0,
            "General Knowledge": 0,
            "Mathematical Calculations": 0,
            "Time Queries": 0,
            "Edge Cases": 0,
            "Previously Problematic": 0
        }
        
        category_failures = {cat: 0 for cat in categories}
        
        for test in self.results:
            desc = test.get('description', '')
            if any(word in desc.lower() for word in ['greeting', 'hello', 'hi']):
                categories["Greetings"] += 1
                if not test.get("passed", False):
                    category_failures["Greetings"] += 1
            elif 'conversation' in desc.lower():
                categories["General Conversation"] += 1
                if not test.get("passed", False):
                    category_failures["General Conversation"] += 1
            elif any(word in desc.lower() for word in ['knowledge', 'geography', 'literature', 'science']):
                categories["General Knowledge"] += 1
                if not test.get("passed", False):
                    category_failures["General Knowledge"] += 1
            elif any(word in desc.lower() for word in ['math', 'calculation', 'arithmetic']):
                categories["Mathematical Calculations"] += 1
                if not test.get("passed", False):
                    category_failures["Mathematical Calculations"] += 1
            elif 'time' in desc.lower():
                categories["Time Queries"] += 1
                if not test.get("passed", False):
                    category_failures["Time Queries"] += 1
            elif 'edge' in desc.lower():
                categories["Edge Cases"] += 1
                if not test.get("passed", False):
                    category_failures["Edge Cases"] += 1
            elif 'historical' in desc.lower() or 'problematic' in desc.lower():
                categories["Previously Problematic"] += 1
                if not test.get("passed", False):
                    category_failures["Previously Problematic"] += 1
        
        print(f"\n📈 CATEGORY BREAKDOWN:")
        print("-" * 40)
        for cat, total in categories.items():
            if total > 0:
                failures = category_failures[cat]
                success_rate = ((total - failures) / total * 100) if total > 0 else 0
                print(f"{cat}: {total - failures}/{total} ({success_rate:.1f}%)")
        
        return passed_tests == total_tests

async def run_tests():
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
    asyncio.run(run_tests())
