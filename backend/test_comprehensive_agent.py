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
logger = logging.getLogger(__name__)


class AgentTestSuite:
    """Comprehensive test suite for Personal Agent behavior."""
    
    def __init__(self):
        self.agent = PersonalAgent()
        self.conversation_id = None
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []
    
    def setup(self):
        """Setup test environment."""
        print("🚀 Setting up Personal Agent Test Suite...")
        self.conversation_id = self.agent.create_conversation()
        print(f"✅ Created test conversation: {self.conversation_id}\n")
    
    async def run_test(self, test_name: str, message: str, should_use_tools: bool, 
                      expected_tools: Optional[List[str]] = None, 
                      response_should_contain: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run a single test case.
        
        Args:
            test_name: Name of the test
            message: Message to send to agent
            should_use_tools: Whether tools should be used
            expected_tools: List of tools that should be used (if any)
            response_should_contain: Keywords that should be in response
        """
        print(f"🧪 Testing: {test_name}")
        print(f"   Input: '{message}'")
        
        try:
            result = await self.agent.process_message(message, self.conversation_id)
            
            # Extract test data
            response = result.get('response', '')
            agent_actions = result.get('agent_actions', [])
            used_tools = [action['tool'] for action in agent_actions] if agent_actions else []
            
            # Determine if test passed
            test_passed = True
            failure_reasons = []
            
            # Check tool usage expectations
            if should_use_tools and not used_tools:
                test_passed = False
                failure_reasons.append(f"Expected tools to be used, but none were used")
            
            if not should_use_tools and used_tools:
                test_passed = False
                failure_reasons.append(f"Expected no tools, but used: {used_tools}")
            
            # Check specific tool expectations
            if expected_tools:
                for expected_tool in expected_tools:
                    if expected_tool not in used_tools:
                        test_passed = False
                        failure_reasons.append(f"Expected tool '{expected_tool}' was not used")
                
                # Check for unexpected tools
                for used_tool in used_tools:
                    if used_tool not in expected_tools:
                        test_passed = False
                        failure_reasons.append(f"Unexpected tool '{used_tool}' was used")
            
            # Check response content
            if response_should_contain:
                response_lower = response.lower()
                for keyword in response_should_contain:
                    if keyword.lower() not in response_lower:
                        test_passed = False
                        failure_reasons.append(f"Response should contain '{keyword}'")
            
            # Check for empty response
            if not response or response.strip() == '' or response.strip().lower() == 'n/a':
                test_passed = False
                failure_reasons.append("Response was empty or 'N/A'")
            
            # Print results
            if test_passed:
                print(f"   ✅ PASSED")
                print(f"   Response: '{response}'")
                if used_tools:
                    print(f"   Tools used: {used_tools}")
                self.passed_tests += 1
            else:
                print(f"   ❌ FAILED")
                print(f"   Response: '{response}'")
                print(f"   Tools used: {used_tools}")
                for reason in failure_reasons:
                    print(f"   Reason: {reason}")
                self.failed_tests += 1
            
            # Store test result
            test_result = {
                'test_name': test_name,
                'message': message,
                'response': response,
                'used_tools': used_tools,
                'expected_tools': expected_tools,
                'should_use_tools': should_use_tools,
                'passed': test_passed,
                'failure_reasons': failure_reasons,
                'token_usage': result.get('token_usage', 0)
            }
            self.test_results.append(test_result)
            
            print()  # Empty line for readability
            return test_result
            
        except Exception as e:
            print(f"   💥 ERROR: {str(e)}")
            self.failed_tests += 1
            print()
            return {
                'test_name': test_name,
                'message': message,
                'error': str(e),
                'passed': False
            }
    
    async def test_greetings_no_tools(self):
        """Test that greetings don't inappropriately use tools."""
        print("=" * 60)
        print("🗣️  TESTING GREETINGS (Should NOT use tools)")
        print("=" * 60)
        
        greeting_tests = [
            ("Simple Hi", "hi", ["hello", "assist"]),
            ("Simple Hello", "hello", ["hello", "assist"]),
            ("Casual Hey", "hey", ["hello", "hey", "assist"]),
            ("Morning Greeting", "good morning", ["morning", "assist"]),
            ("Evening Greeting", "good evening", ["evening", "assist"]),
            ("How are you", "how are you", ["how", "assist"]),
            ("What's up", "what's up", ["assist"]),
            ("Casual sup", "sup", ["assist"]),
            ("Thanks", "thank you", ["thank", "welcome"]),
            ("Goodbye", "goodbye", ["goodbye", "bye"]),
        ]
        
        for test_name, message, expected_words in greeting_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=False,
                response_should_contain=expected_words
            )
    
    async def test_general_questions_no_tools(self):
        """Test that general knowledge questions don't use tools."""
        print("=" * 60)
        print("📚 TESTING GENERAL KNOWLEDGE (Should NOT use tools)")
        print("=" * 60)
        
        knowledge_tests = [
            ("Capital Question", "what is the capital of france", ["paris"]),
            ("Simple Fact", "who wrote hamlet", ["shakespeare"]),
            ("Geography", "which continent is brazil in", ["south america"]),
            ("Science Fact", "what is the chemical symbol for water", ["h2o"]),
            ("History Question", "when did world war 2 end", ["1945"]),
            ("Literature", "who wrote 1984", ["orwell"]),
            ("Basic Info", "what is the largest planet", ["jupiter"]),
            ("Color Question", "what color do you get mixing red and blue", ["purple"]),
            ("Animal Fact", "what is the fastest land animal", ["cheetah"]),
            ("Technology", "what does AI stand for", ["artificial intelligence"]),
        ]
        
        for test_name, message, expected_words in knowledge_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=False,
                response_should_contain=expected_words
            )
    
    async def test_math_requires_calculator(self):
        """Test that mathematical questions properly use calculator."""
        print("=" * 60)
        print("🔢 TESTING MATHEMATICS (Should use calculator tool)")
        print("=" * 60)
        
        math_tests = [
            ("Simple Addition", "what is 15 + 27", ["calculator"], ["42"]),
            ("Multiplication", "calculate 8 * 9", ["calculator"], ["72"]),
            ("Division", "what is 100 divided by 4", ["calculator"], ["25"]),
            ("Subtraction", "what is 50 - 23", ["calculator"], ["27"]),
            ("Complex Math", "what is 12 * 8 + 5", ["calculator"], ["101"]),
            ("Exponentiation", "what is 2 to the power of 8", ["calculator"], ["256"]),
            ("Percentage", "what is 15% of 200", ["calculator"], ["30"]),
            ("Decimal Math", "what is 3.5 * 4", ["calculator"], ["14"]),
            ("Large Numbers", "what is 999 + 1", ["calculator"], ["1000"]),
            ("Square", "what is 12 squared", ["calculator"], ["144"]),
        ]
        
        for test_name, message, expected_tools, expected_result in math_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=True,
                expected_tools=expected_tools,
                response_should_contain=expected_result
            )
    
    async def test_time_requires_time_tool(self):
        """Test that time questions properly use current_time tool."""
        print("=" * 60)
        print("🕐 TESTING TIME QUERIES (Should use current_time tool)")
        print("=" * 60)
        
        time_tests = [
            ("Current Time", "what time is it", ["current_time"]),
            ("Current Date", "what is today's date", ["current_time"]),
            ("Date and Time", "what is the current date and time", ["current_time"]),
            ("Just Time", "tell me the time", ["current_time"]),
            ("Time Now", "what time is it now", ["current_time"]),
            ("Today", "what day is today", ["current_time"]),
            ("Current Timestamp", "give me the current timestamp", ["current_time"]),
        ]
        
        for test_name, message, expected_tools in time_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=True,
                expected_tools=expected_tools,
                response_should_contain=["2025", "june"]  # Should contain current date
            )
    
    async def test_conversational_flow(self):
        """Test conversational responses that should NOT use tools."""
        print("=" * 60)
        print("💬 TESTING CONVERSATIONAL RESPONSES (Should NOT use tools)")
        print("=" * 60)
        
        conversation_tests = [
            ("Tell me about AI", "tell me about artificial intelligence", ["artificial", "intelligence"]),
            ("Explain concept", "explain machine learning", ["machine", "learning"]),
            ("Give advice", "how can I learn programming", ["programming", "learn"]),
            ("Opinion question", "what do you think about space exploration", ["space"]),
            ("Recommendation", "recommend a good book", ["book"]),
            ("How-to question", "how do I bake a cake", ["bake", "cake"]),
            ("Comparison", "difference between python and javascript", ["python", "javascript"]),
            ("List question", "what are some benefits of exercise", ["exercise", "benefits"]),
            ("Future prediction", "what will technology be like in 10 years", ["technology"]),
            ("Personal question", "what is your favorite color", ["color"]),
        ]
        
        for test_name, message, expected_words in conversation_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=False,
                response_should_contain=expected_words
            )
    
    async def test_edge_cases(self):
        """Test edge cases and potential problematic inputs."""
        print("=" * 60)
        print("⚠️  TESTING EDGE CASES")
        print("=" * 60)
        
        edge_tests = [
            # These should NOT use tools
            ("Empty-like", "hmm", False, None),
            ("Single word", "yes", False, None),
            ("Question about math (not calculation)", "what is mathematics", False, ["mathematics"]),
            ("Question about time (not current time)", "what is time", False, ["time"]),
            
            # These SHOULD use tools
            ("Math with words", "calculate fifteen plus twenty", True, ["calculator"]),
            ("Time with different phrasing", "current time please", True, ["current_time"]),
        ]
        
        for test_name, message, should_use_tools, expected_words in edge_tests:
            await self.run_test(
                test_name=test_name,
                message=message,
                should_use_tools=should_use_tools,
                response_should_contain=expected_words
            )
    
    def print_summary(self):
        """Print test summary and statistics."""
        print("=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        total_tests = self.passed_tests + self.failed_tests
        pass_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.passed_tests} ✅")
        print(f"Failed: {self.failed_tests} ❌")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if self.failed_tests > 0:
            print("\n🚨 FAILED TESTS:")
            for result in self.test_results:
                if not result.get('passed', False):
                    print(f"   ❌ {result['test_name']}: {result['message']}")
                    if 'failure_reasons' in result:
                        for reason in result['failure_reasons']:
                            print(f"      - {reason}")
        
        # Token usage statistics
        total_tokens = sum(result.get('token_usage', 0) for result in self.test_results)
        avg_tokens = total_tokens / len(self.test_results) if self.test_results else 0
        
        print(f"\n📈 TOKEN USAGE:")
        print(f"Total Tokens: {total_tokens}")
        print(f"Average per Test: {avg_tokens:.1f}")
        
        print("\n" + "=" * 80)
        
        return pass_rate >= 90  # Consider 90%+ pass rate as success

async def main():
    """Run the comprehensive test suite."""
    test_suite = AgentTestSuite()
    test_suite.setup()
    
    try:
        # Run all test categories
        await test_suite.test_greetings_no_tools()
        await test_suite.test_general_questions_no_tools()
        await test_suite.test_math_requires_calculator()
        await test_suite.test_time_requires_time_tool()
        await test_suite.test_conversational_flow()
        await test_suite.test_edge_cases()
        
        # Print final summary
        success = test_suite.print_summary()
        
        if success:
            print("🎉 TEST SUITE PASSED! Agent behavior is working correctly.")
            return 0
        else:
            print("💥 TEST SUITE FAILED! Agent needs improvement.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️  Test suite interrupted by user.")
        return 130
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
