# Test Organization

This directory contains all test files for the Personal Agent project, organized by type and purpose.

## Directory Structure

### `/html/` - Frontend Test Files
- `chat_time_test.html` - Test file for chat time functionality
- `current_time_test.html` - Test file for current time display
- `debug_time_format.html` - Debug test for time formatting
- `test_time_formatting_live.html` - Live time formatting test
- `time_formatting_test.html` - Time formatting validation test

### `/backend/tests/` - Backend Test Files
- `test_comprehensive.py` - Main comprehensive test suite (22 test cases)
  - Tests agent behavior, tool usage, mathematical calculations, time queries, document Q&A, and historical edge cases
  - **Run with**: `python backend/tests/test_comprehensive.py`

### `/backend/tests/legacy/` - Legacy/Utility Scripts
- `fix_document_timestamps.py` - Database utility script for fixing document timestamps
- `test_agent_behavior.py` - Early agent behavior test script

### `/backend/tests/resources/` - Test Resources
- `test_document.pdf` - Sample PDF for document Q&A testing
- `test_document.txt` - Text version of test document

## Running Tests

### Main Test Suite
```bash
cd backend
python tests/test_comprehensive.py
```

### Frontend Tests
Open any HTML file in `/html/` directory in a web browser to test frontend functionality.

## Test Coverage

The comprehensive test suite covers:
- ✅ Greetings (5 tests) - Should not use tools
- ✅ General conversation (4 tests) - Should not use tools  
- ✅ Mathematical calculations (4 tests) - Should use calculator
- ✅ Time queries (3 tests) - Should use current_time tool
- ✅ Document Q&A behavior (3 tests) - Should handle RAG appropriately
- ✅ Historical problem cases (3 tests) - Previously problematic scenarios

**Total: 22 tests with 100% pass rate**
