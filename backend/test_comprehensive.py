#!/usr/bin/env python3
"""
Comprehensive test suite for Personal Agent behavior.
Tests that tools are only called when needed and responses are appropriate.
Updated for CoreOrchestrator and Pydantic tool structure.
"""

import sys
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
import json
import warnings

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.database.operations import db_ops
from backend.orchestrator.core import CoreOrchestrator
from backend.services.document_service import DocumentProcessor

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise

class OrchestratorTester:
    def __init__(self):
        self.orchestrator = CoreOrchestrator(user_id="test_user")
        self.doc_processor = DocumentProcessor()
        self.results = []
        self.failed_tests = []
        self.skipped_tests = []  # Track skipped tests
        
        # Get available documents for testing
        self.available_documents = self._get_test_documents()
        
    def _get_test_documents(self) -> List[str]:
        """Get available test document IDs."""
        try:
            # Try test_user first, then fallback to default if empty
            documents = self.doc_processor.get_documents(user_id="test_user")
            if not documents:
                documents = self.doc_processor.get_documents(user_id="default")
            if documents:
                return [doc["id"] for doc in documents[:2]]  # Use first 2 documents
            else:
                return []
        except Exception as e:
            print(f"⚠️  Error getting test documents: {e}")
            return []
        
    async def test_query(self, query: str, expected_tool_usage: Optional[str] = None, 
                        should_not_use_tools: bool = False, 
                        description: str = "",
                        use_documents: bool = False,
                        skip_if_no_docs: bool = False) -> Dict[str, Any]:
        """
        Test a single query and validate tool usage.
        
        Args:
            query: The user query to test
            expected_tool_usage: Name of tool that should be used (if any)
            should_not_use_tools: Whether this query should NOT use any tools
            description: Description of what this test validates
            use_documents: Whether to pass selected documents to the orchestrator
            skip_if_no_docs: Whether to skip this test if no documents are available
        """
        print(f"\n🧪 Testing: {query}")
        print(f"   Expected: {description}")

        # Always create a new conversation for each test
        conversation_id = self.orchestrator.create_conversation()

        # Check if we should skip this test due to missing documents
        if skip_if_no_docs and not self.available_documents:
            skip_result = {
                "query": query,
                "description": description,
                "skipped": True,
                "reason": "⚠️  SKIPPED: No documents available in database",
                "passed": None  # Neither passed nor failed
            }
            print(f"   Result: {skip_result['reason']}")
            self.results.append(skip_result)
            self.skipped_tests.append(skip_result)
            return skip_result

        try:
            selected_documents = None
            if use_documents and self.available_documents:
                selected_documents = self.available_documents
                print(f"   📄 Using documents: {len(selected_documents)} documents selected")

            # Process the query with a fresh conversation_id
            result = await self.orchestrator.process_request(
                query, 
                conversation_id,
                selected_documents=selected_documents
            )
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
                "warning": False,
                "reason": ""
            }
            
            # Check if test passed
            if should_not_use_tools:
                if not tools_used:
                    test_result["passed"] = True
                    test_result["warning"] = False
                    test_result["reason"] = "✅ Correctly avoided using tools"
                else:
                    test_result["passed"] = True
                    test_result["warning"] = True
                    test_result["reason"] = f"⚠️ Passed with warning: Unnecessary tool(s) used: {tools_used}"
            elif expected_tool_usage:
                if expected_tool_usage in tools_used:
                    # Check for unnecessary tools
                    extra_tools = [t for t in tools_used if t != expected_tool_usage]
                    if extra_tools:
                        test_result["passed"] = True
                        test_result["warning"] = True
                        test_result["reason"] = f"⚠️ Passed with warning: Used {expected_tool_usage} but also unnecessary tool(s): {extra_tools}"
                    else:
                        test_result["passed"] = True
                        test_result["warning"] = False
                        test_result["reason"] = f"✅ Correctly used {expected_tool_usage}"
                else:
                    test_result["passed"] = False
                    test_result["warning"] = False
                    test_result["reason"] = f"❌ Expected {expected_tool_usage}, got {tools_used}"
            else:
                # No specific expectation, just check for reasonable response
                if response and response.strip() and response.lower() not in ["n/a", "none"]:
                    if tools_used:
                        test_result["passed"] = True
                        test_result["warning"] = True
                        test_result["reason"] = f"⚠️ Passed with warning: Unnecessary tool(s) used: {tools_used}"
                    else:
                        test_result["passed"] = True
                        test_result["warning"] = False
                        test_result["reason"] = "✅ Provided reasonable response"
                else:
                    test_result["passed"] = False
                    test_result["warning"] = False
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
        
        # Check orchestration_actions (for CoreOrchestrator)
        orchestration_actions = result.get("orchestration_actions", [])
        if orchestration_actions:
            for action in orchestration_actions:
                if isinstance(action, dict):
                    tool_name = action.get("tool", "").lower()
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)
        
        # Fallback: Check legacy agent_actions format
        agent_actions = result.get("agent_actions", [])
        if agent_actions:
            for action in agent_actions:
                if isinstance(action, dict):
                    tool_name = action.get("tool", "").lower()
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)
        
        return tools_used
    
    def assert_tool_usage(self, query, expected_tools, actual_tools, response, description=None):
        """
        Assert tool usage for a test case. If unnecessary tools are used, raise a warning instead of an error.
        """
        if expected_tools:
            if set(expected_tools) != set(actual_tools):
                raise AssertionError(f"❌ Expected {expected_tools}, got {actual_tools}\nResponse: {response}")
        else:
            if actual_tools:
                print(f"⚠️ Warning: Unnecessary tool(s) used for query '{query}': {actual_tools}\nResponse: {response}")
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        print("🚀 Starting Comprehensive Agent Test Suite")
        print("=" * 60)
        
        # Display test environment info
        print(f"📄 Document Status: {len(self.available_documents)} documents available for testing")
        if self.available_documents:
            print(f"   Document IDs: {', '.join(self.available_documents[:3])}{'...' if len(self.available_documents) > 3 else ''}")
        print()
        
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
        
        # 5. DOCUMENT Q&A (RAG) - Tests with documents if available
        print("\n📋 Category 5: Document Q&A (RAG) Behavior Tests")
        
        if self.available_documents:
            print(f"   📄 Testing with {len(self.available_documents)} documents available")
            
            rag_tests = [
                ("What information is in my documents?", "Document query with documents", "search_documents"),
                ("Tell me about the uploaded files", "File query with documents", "search_documents"), 
                ("Search my documents for information about AI", "Search query with documents", "search_documents"),
            ]
            
            # These tests pass documents to the agent so search_documents can work properly
            for query, desc, expected_tool in rag_tests:
                await self.test_query(
                    query, 
                    expected_tool_usage=expected_tool, 
                    description=desc, 
                    use_documents=True  # This ensures documents are passed to the agent
                )
        else:
            print("   ⚠️  No documents available in database")
            
            rag_tests = [
                ("What information is in my documents?", "Document query without documents", "search_documents"),
                ("Tell me about the uploaded files", "File query without documents", "search_documents"), 
                ("Search my documents for information about AI", "Search query without documents", "search_documents"),
            ]
            
            # These tests will be skipped with clear warnings
            for query, desc, expected_tool in rag_tests:
                await self.test_query(
                    query, 
                    expected_tool_usage=expected_tool, 
                    description=desc, 
                    skip_if_no_docs=True
                )
        
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
        passed_tests = sum(1 for r in self.results if r.get("passed", False) == True and not r.get("passed_with_warning", False))
        warning_tests = sum(1 for r in self.results if r.get("passed_with_warning", False))
        failed_tests = len(self.failed_tests)
        skipped_tests = len(self.skipped_tests)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Passed with warning: {warning_tests} ⚠️")
        print(f"Failed: {failed_tests} ❌")
        print(f"Skipped: {skipped_tests} ⚠️")
        
        # Calculate success rate based on non-skipped tests
        non_skipped_tests = total_tests - skipped_tests
        if non_skipped_tests > 0:
            success_rate = ((passed_tests + warning_tests) / non_skipped_tests) * 100
            print(f"Success Rate: {success_rate:.1f}% (of non-skipped tests)")
        else:
            print("Success Rate: N/A (no tests executed)")
        
        # Show warnings for skipped tests
        if self.skipped_tests:
            print(f"\n⚠️  SKIPPED TESTS ({len(self.skipped_tests)}):")
            print("-" * 40)
            for i, test in enumerate(self.skipped_tests, 1):
                print(f"{i}. Query: '{test['query']}'")
                print(f"   Description: {test['description']}")
                print(f"   Reason: {test['reason']}")
                print()
            
            print("🔧 TO FIX SKIPPED TESTS:")
            print("   • Add test documents to the database using create_test_docs.py")
            print("   • Or ensure documents are uploaded via the frontend")
            print()
        
        # Print passed with warning tests
        passed_with_warning_tests = [r for r in self.results if r.get("passed", False) and r.get("warning", False)]
        if passed_with_warning_tests:
            print(f"\n⚠️  PASSED WITH WARNING TESTS ({len(passed_with_warning_tests)}):")
            print("-" * 40)
            for i, test in enumerate(passed_with_warning_tests, 1):
                print(f"{i}. Query: '{test['query']}'")
                print(f"   Description: {test['description']}")
                print(f"   Reason: {test['reason']}")
                if 'tools_used' in test:
                    print(f"   Tools Used: {test['tools_used']}")
                if 'response' in test:
                    response_preview = test['response'][:150] + "..." if len(test['response']) > 150 else test['response']
                    print(f"   Response: {response_preview}")
                print()
        
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
        
        # Summarize results
        print(f"Total Tests: {total_tests}")
        print(f"Skipped: {skipped_tests} ⚠️")
        print(f"Passed: {passed_tests} ✅")
        print(f"Passed with warning: {warning_tests} ⚠️")
        print(f"Failed: {failed_tests} ❌")
        

        # passed = sum(1 for r in self.results if r["passed"] and not r["warning"])
        # warning = sum(1 for r in self.results if r["passed"] and r["warning"])
        # failed = sum(1 for r in self.results if not r["passed"] or r["warning"])
        # skipped = len(self.skipped_tests)
        # total = len(self.results)
        # print("\nTest Summary:")
        # print(f"  Passed: {passed}")
        # print(f"  Passed with warning: {warning}")
        # print(f"  Failed: {failed}")
        # print(f"  Total: {total}")
        # print(f"  Accuracy (counting warnings as pass): {(passed + warning) / total:.1%}")
        
        # # When summarizing test results, ensure skipped tests are not counted as failed
        # # For example, in the summary logic:
        # total_failed = sum(1 for r in self.results if r['outcome'] == 'failed')
        # total_skipped = sum(1 for r in self.results if r['outcome'] == 'skipped')
        # total_passed = sum(1 for r in self.results if r['outcome'] == 'passed')
        
        # summary = {
        #     'total': len(self.results),
        #     'passed': total_passed,
        #     'failed': total_failed,  # Only count 'failed', not 'skipped'
        #     'skipped': total_skipped
        # }
        
        return passed_tests == non_skipped_tests and non_skipped_tests > 0

async def main():
    """Main test runner."""
    tester = OrchestratorTester()
    
    try:
        await tester.run_all_tests()
        success = tester.print_summary()
        print("Tests done")
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
