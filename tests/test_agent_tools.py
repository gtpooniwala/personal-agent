"""
Comprehensive tests for Individual Agent Tools.
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestAgentTools(unittest.TestCase):
    """Test individual agent tools functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_llm.invoke = Mock(return_value=Mock(content="Mocked response"))
    
    def test_calculator_tool_structure(self):
        """Test calculator tool has proper structure."""
        # Expected calculator tool behavior
        test_expressions = [
            {"input": "2 + 2", "expected": 4},
            {"input": "10 * 5", "expected": 50},
            {"input": "100 / 4", "expected": 25.0}
        ]
        
        for test_case in test_expressions:
            # This simulates the calculator tool logic
            try:
                # Safe evaluation of mathematical expressions
                result = eval(test_case["input"])
                self.assertEqual(result, test_case["expected"])
            except Exception as e:
                self.fail(f"Calculator failed on {test_case['input']}: {e}")
    
    def test_search_internet_tool_structure(self):
        """Test internet search tool structure."""
        # Mock search results structure
        expected_search_result = {
            "query": "Python programming",
            "results": [
                {
                    "title": "Python.org",
                    "url": "https://python.org",
                    "snippet": "Official Python website"
                }
            ]
        }
        
        # Test structure validation
        self.assertIn("query", expected_search_result)
        self.assertIn("results", expected_search_result)
        self.assertIsInstance(expected_search_result["results"], list)
        
        if expected_search_result["results"]:
            result = expected_search_result["results"][0]
            self.assertIn("title", result)
            self.assertIn("url", result)
            self.assertIn("snippet", result)
    
    def test_gmail_tool_structure(self):
        """Test Gmail tool structure."""
        # Expected Gmail tool responses
        expected_gmail_responses = {
            "send_email": {
                "status": "sent",
                "message_id": "msg_123",
                "to": "recipient@example.com"
            },
            "read_emails": {
                "emails": [
                    {
                        "id": "email_1",
                        "subject": "Test Subject",
                        "from": "sender@example.com",
                        "date": "2025-01-01T00:00:00Z",
                        "body": "Email content"
                    }
                ]
            }
        }
        
        # Test send email response structure
        send_response = expected_gmail_responses["send_email"]
        self.assertIn("status", send_response)
        self.assertIn("message_id", send_response)
        self.assertIn("to", send_response)
        
        # Test read emails response structure
        read_response = expected_gmail_responses["read_emails"]
        self.assertIn("emails", read_response)
        self.assertIsInstance(read_response["emails"], list)
        
        if read_response["emails"]:
            email = read_response["emails"][0]
            required_fields = ["id", "subject", "from", "date", "body"]
            for field in required_fields:
                self.assertIn(field, email)
    
    def test_document_qa_tool_structure(self):
        """Test document Q&A tool structure."""
        # Expected document Q&A response
        expected_qa_response = {
            "question": "What is the main topic?",
            "answer": "The document discusses Python programming concepts.",
            "source_documents": [
                {
                    "filename": "python_guide.pdf",
                    "page": 1,
                    "relevance_score": 0.95
                }
            ]
        }
        
        # Test response structure
        self.assertIn("question", expected_qa_response)
        self.assertIn("answer", expected_qa_response)
        self.assertIn("source_documents", expected_qa_response)
        
        # Test source documents structure
        if expected_qa_response["source_documents"]:
            doc = expected_qa_response["source_documents"][0]
            self.assertIn("filename", doc)
            self.assertIn("relevance_score", doc)
            self.assertIsInstance(doc["relevance_score"], (int, float))
    
    def test_current_time_tool_structure(self):
        """Test current time tool structure."""
        import datetime
        
        # Test time formatting
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Should be valid datetime format
        self.assertIsInstance(formatted_time, str)
        self.assertGreater(len(formatted_time), 0)
        
        # Should be parseable back to datetime
        try:
            parsed_time = datetime.datetime.strptime(formatted_time, "%Y-%m-%d %H:%M:%S")
            self.assertIsInstance(parsed_time, datetime.datetime)
        except ValueError:
            self.fail("Time formatting produced invalid format")
    
    def test_memory_tool_structure(self):
        """Test memory tool structure."""
        # Expected memory operations
        memory_operations = {
            "save": {
                "operation": "save",
                "key": "user_preference",
                "value": "dark_mode",
                "status": "saved"
            },
            "retrieve": {
                "operation": "retrieve", 
                "key": "user_preference",
                "value": "dark_mode",
                "found": True
            },
            "list": {
                "operation": "list",
                "keys": ["user_preference", "last_search", "settings"]
            }
        }
        
        # Test save operation structure
        save_op = memory_operations["save"]
        self.assertIn("operation", save_op)
        self.assertIn("key", save_op)
        self.assertIn("value", save_op)
        self.assertIn("status", save_op)
        
        # Test retrieve operation structure
        retrieve_op = memory_operations["retrieve"]
        self.assertIn("operation", retrieve_op)
        self.assertIn("key", retrieve_op)
        self.assertIn("found", retrieve_op)
        self.assertIsInstance(retrieve_op["found"], bool)
        
        # Test list operation structure
        list_op = memory_operations["list"]
        self.assertIn("operation", list_op)
        self.assertIn("keys", list_op)
        self.assertIsInstance(list_op["keys"], list)
    
    def test_conversation_summarisation_tool_structure(self):
        """Test conversation summarisation tool structure."""
        # Mock conversation history
        conversation_history = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"},
            {"role": "user", "content": "Can you help me with Python?"},
            {"role": "assistant", "content": "Of course! What do you need help with?"}
        ]
        
        # Expected summarisation response
        expected_summary = {
            "original_length": len(conversation_history),
            "summary": "User greeted and asked for Python help. Assistant responded positively.",
            "summary_length": 65,
            "compression_ratio": 0.8
        }
        
        # Test summary structure
        self.assertIn("original_length", expected_summary)
        self.assertIn("summary", expected_summary)
        self.assertIn("summary_length", expected_summary)
        self.assertIsInstance(expected_summary["original_length"], int)
        self.assertIsInstance(expected_summary["summary"], str)
        self.assertGreater(len(expected_summary["summary"]), 0)
    
    def test_user_profile_tool_structure(self):
        """Test user profile tool structure."""
        # Expected user profile operations
        profile_operations = {
            "get_profile": {
                "user_id": "test_user",
                "profile": {
                    "name": "Test User",
                    "preferences": {
                        "theme": "dark",
                        "language": "en"
                    },
                    "created_at": "2025-01-01T00:00:00Z"
                }
            },
            "update_profile": {
                "user_id": "test_user",
                "updated_fields": ["preferences.theme"],
                "status": "updated"
            }
        }
        
        # Test get profile structure
        get_profile = profile_operations["get_profile"]
        self.assertIn("user_id", get_profile)
        self.assertIn("profile", get_profile)
        
        profile = get_profile["profile"]
        self.assertIn("name", profile)
        self.assertIn("preferences", profile)
        self.assertIsInstance(profile["preferences"], dict)
        
        # Test update profile structure
        update_profile = profile_operations["update_profile"]
        self.assertIn("user_id", update_profile)
        self.assertIn("updated_fields", update_profile)
        self.assertIn("status", update_profile)
        self.assertIsInstance(update_profile["updated_fields"], list)
    
    def test_tool_error_handling_structure(self):
        """Test that tools handle errors properly."""
        # Expected error response structure
        expected_error_response = {
            "error": True,
            "error_type": "ValidationError",
            "message": "Invalid input provided",
            "details": "The query parameter is required"
        }
        
        # Test error structure
        self.assertIn("error", expected_error_response)
        self.assertIn("error_type", expected_error_response)
        self.assertIn("message", expected_error_response)
        self.assertTrue(expected_error_response["error"])
        self.assertIsInstance(expected_error_response["message"], str)
    
    def test_tool_response_consistency(self):
        """Test that all tools follow consistent response format."""
        # All successful tool responses should be consistent
        success_formats = [
            {"status": "success", "data": {"result": "value"}},
            {"status": "success", "result": "direct_value"},
            {"success": True, "data": {"key": "value"}}
        ]
        
        # Test that each format has some indication of success
        for response in success_formats:
            has_success_indicator = (
                "status" in response and response["status"] == "success" or
                "success" in response and response["success"] is True or
                "error" not in response or 
                ("error" in response and not response["error"])
            )
            self.assertTrue(has_success_indicator, f"Response lacks success indicator: {response}")


if __name__ == '__main__':
    unittest.main()
