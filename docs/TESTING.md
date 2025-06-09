# Testing Documentation

## Overview

The Personal Agent project includes a comprehensive testing framework designed to ensure proper agent behavior, tool usage, and system reliability. Testing is organized across multiple categories including unit tests, integration tests, behavior validation, and frontend testing.

## Test Architecture

### Test Categories

The testing framework validates several key aspects of agent behavior:

1. **Conversational Responses** - Ensures greetings and general conversation don't inappropriately use tools
2. **Tool Usage Validation** - Verifies tools are only called when necessary
3. **Mathematical Calculations** - Confirms calculator tool is used for computational queries
4. **Time Queries** - Validates current_time tool usage for temporal questions
5. **Document Q&A (RAG)** - Tests document-based question answering behavior
6. **Edge Cases** - Handles problematic or unusual input scenarios

### Testing Infrastructure

```text
tests/
├── backend/tests/
│   ├── test_comprehensive.py          # Main test suite (22 test cases)
│   └── legacy/                        # Historical test scripts
├── html/                              # Frontend testing files
│   ├── chat_time_test.html
│   ├── current_time_test.html
│   ├── debug_time_format.html
│   ├── test_time_formatting_live.html
│   ├── time_formatting_test.html
│   └── test_title_generation.html
└── README.md                          # Test organization documentation
```

## Running Tests

### Main Comprehensive Test Suite

The primary test suite provides complete behavior validation:

```bash
cd backend
python tests/test_comprehensive.py
```

**Test Coverage:**
- ✅ Greetings (5 tests) - Should not use tools
- ✅ General conversation (4 tests) - Should not use tools  
- ✅ Mathematical calculations (4 tests) - Should use calculator
- ✅ Time queries (3 tests) - Should use current_time tool
- ✅ Document Q&A behavior (3 tests) - Should handle RAG appropriately
- ✅ Historical problem cases (3 tests) - Previously problematic scenarios

**Total: 22 tests with expected 100% pass rate**

### Legacy Test Scripts

Several historical test scripts are available for specific testing scenarios:

```bash
# Basic import validation
python backend/test_imports.py

# Manual step-by-step testing
python backend/test_manual.py

# Alternative comprehensive test versions
python backend/test_comprehensive_agent.py
python backend/test_comprehensive_agent_clean.py
python backend/test_comprehensive_agent_fixed.py
```

### Frontend Tests

Frontend functionality can be tested by opening HTML files in a web browser:

```bash
# Navigate to test files
open tests/html/chat_time_test.html
open tests/html/current_time_test.html
open tests/html/time_formatting_test.html
```

## Test Implementation Details

### AgentTester Class

The main testing infrastructure is built around the `AgentTester` class:

```python
class AgentTester:
    def __init__(self):
        self.agent = PersonalAgent()
        self.results = []
        self.failed_tests = []
    
    async def test_query(self, query: str, expected_tool_usage: Optional[str] = None, 
                        should_not_use_tools: bool = False, 
                        description: str = "") -> Dict[str, Any]:
        # Test execution logic
        
    def _extract_tools_used(self, response: str, result: Dict[str, Any]) -> List[str]:
        # Tool usage detection
        
    def print_summary(self):
        # Test results reporting
```

### Test Validation Logic

Each test validates multiple aspects:

1. **Tool Usage Validation**
   - Checks if tools were used when expected
   - Validates correct tool selection
   - Ensures tools aren't used unnecessarily

2. **Response Quality**
   - Verifies non-empty responses
   - Checks for appropriate content
   - Validates against expected keywords

3. **Error Handling**
   - Catches and reports exceptions
   - Provides detailed failure reasons
   - Maintains test execution continuity

### Test Result Reporting

The testing framework provides comprehensive reporting:

```text
🚀 Starting Comprehensive Agent Test Suite
========================================================================================

📋 Category 1: Greetings (should NOT use tools)
   Testing: hi (Simple greeting)
   Result: ✅ Correctly avoided using tools
   Response: Hello! I'm here to help you with questions, calculations, and information...

📊 TEST SUMMARY
========================================================================================
Total Tests: 22
Passed: 22 ✅
Failed: 0 ❌
Pass Rate: 100.0%
```

## Test Data and Configuration

### Test Cases

The comprehensive test suite includes carefully selected test cases:

**Greeting Tests:**
- "hi", "hello", "hey there", "how are you?", "what's up"

**Mathematical Tests:**
- "What is 15 + 27?", "Calculate 123 * 456", "What's 1000 divided by 25?"

**Time Query Tests:**
- "What time is it?", "What's the current time?", "Tell me the time"

**Edge Cases:**
- Empty queries, single words, mixed requests, historical problem cases

### Historical Problem Cases

The test suite specifically addresses previously problematic scenarios:

- Greetings returning calculator results (e.g., "hi" → "12")
- Empty responses to basic queries
- Inappropriate tool usage for conversational requests

## Test Automation and CI/CD

### Test Result Persistence

Test results are automatically saved for analysis:

```python
# Save detailed results to file
with open("test_results.json", "w") as f:
    json.dump(tester.results, f, indent=2)
```

### Exit Code Handling

Tests return appropriate exit codes for automation:

```python
# Exit with appropriate code for CI/CD
sys.exit(0 if success else 1)
```

## Debugging and Troubleshooting

### Common Test Failures

1. **Tool Usage Issues**
   - Agent using tools when it shouldn't
   - Agent not using required tools
   - Wrong tool selection

2. **Response Quality Issues**
   - Empty or "N/A" responses
   - Inappropriate responses to queries

3. **System Errors**
   - Import failures
   - Configuration issues
   - API connection problems

### Debugging Tools

- **Verbose Logging**: Enable detailed logging for test execution
- **Individual Test Scripts**: Run specific test categories
- **Manual Testing**: Step-by-step agent interaction validation

### Test Environment Setup

Ensure proper test environment configuration:

```bash
# Backend dependencies
cd backend
pip install -r requirements.txt

# Environment variables
export OPENAI_API_KEY="your-api-key"

# Database setup (if needed)
python -c "from database.db_manager import DatabaseManager; DatabaseManager().create_tables()"
```

## Extending the Test Suite

### Adding New Test Categories

To add new test categories:

1. Define test cases in the appropriate category
2. Implement validation logic
3. Add to the main test runner
4. Update documentation

### Custom Test Scenarios

For specific use cases, create focused test scripts:

```python
# Example: Document Q&A specific testing
async def test_document_qa():
    # Custom RAG testing logic
    pass
```

## Test Metrics and Performance

### Performance Tracking

Tests track token usage and execution time:

```python
# Token usage statistics
total_tokens = sum(result.get('token_usage', 0) for result in self.test_results)
avg_tokens = total_tokens / len(self.test_results) if self.test_results else 0
```

### Success Criteria

- **Pass Rate**: Target 90%+ for production deployment
- **Response Time**: Monitor agent response latency
- **Tool Accuracy**: Validate correct tool selection rates

## Related Documentation

- [Development Guide](DEVELOPMENT_GUIDE.md) - Development workflow including testing
- [Architecture](ARCHITECTURE.md) - System architecture affecting test design
- [API Documentation](API.md) - API endpoints used in integration testing
- [Setup Guide](SETUP.md) - Environment setup for testing
