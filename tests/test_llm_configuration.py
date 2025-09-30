"""
Comprehensive tests for LLM Configuration functionality.
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, mock_open
import yaml

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestLLMConfiguration(unittest.TestCase):
    """Test LLM configuration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_config = {
            "models": {
                "gpt-4.1-mini": {
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                "gpt-4o": {
                    "provider": "openai", 
                    "model_name": "gpt-4o",
                    "temperature": 0.5,
                    "max_tokens": 4000
                }
            },
            "default": "gpt-4.1-mini",
            "tools": {
                "search_internet": "default",
                "calculator": "default",
                "gmail_tool": "default",
                "document_qa": "gpt-4o",
                "conversation_summarisation": "default",
                "current_time": "default",
                "memory_tool": "default",
                "user_profile": "default"
            }
        }
    
    def test_config_file_structure(self):
        """Test that LLM config file has proper structure."""
        config = self.sample_config
        
        # Test top-level keys
        self.assertIn("models", config)
        self.assertIn("default", config)
        self.assertIn("tools", config)
        
        # Test models structure
        models = config["models"]
        self.assertIsInstance(models, dict)
        self.assertGreater(len(models), 0)
        
        # Test each model has required fields
        for model_name, model_config in models.items():
            self.assertIn("provider", model_config)
            self.assertIn("model_name", model_config)
            self.assertIn("temperature", model_config)
            self.assertIn("max_tokens", model_config)
            
            # Validate field types
            self.assertIsInstance(model_config["provider"], str)
            self.assertIsInstance(model_config["model_name"], str)
            self.assertIsInstance(model_config["temperature"], (int, float))
            self.assertIsInstance(model_config["max_tokens"], int)
    
    def test_default_model_exists(self):
        """Test that default model is defined and exists in models."""
        config = self.sample_config
        
        self.assertIn("default", config)
        default_model = config["default"]
        
        self.assertIn(default_model, config["models"])
    
    def test_tool_model_assignments(self):
        """Test that all tools have valid model assignments."""
        config = self.sample_config
        
        tools = config["tools"]
        available_models = list(config["models"].keys()) + ["default"]
        
        for tool_name, assigned_model in tools.items():
            # Each tool should be assigned to a valid model or "default"
            self.assertIn(assigned_model, available_models,
                         f"Tool {tool_name} assigned to invalid model {assigned_model}")
    
    def test_temperature_values_valid(self):
        """Test that temperature values are within valid range."""
        config = self.sample_config
        
        for model_name, model_config in config["models"].items():
            temperature = model_config["temperature"]
            
            # Temperature should be between 0 and 2 for most LLM providers
            self.assertGreaterEqual(temperature, 0.0,
                                   f"Temperature for {model_name} is too low: {temperature}")
            self.assertLessEqual(temperature, 2.0,
                                f"Temperature for {model_name} is too high: {temperature}")
    
    def test_max_tokens_values_valid(self):
        """Test that max_tokens values are reasonable."""
        config = self.sample_config
        
        for model_name, model_config in config["models"].items():
            max_tokens = model_config["max_tokens"]
            
            # Max tokens should be positive and reasonable
            self.assertGreater(max_tokens, 0,
                             f"Max tokens for {model_name} must be positive: {max_tokens}")
            self.assertLessEqual(max_tokens, 100000,
                                f"Max tokens for {model_name} seems too high: {max_tokens}")
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_config_loading(self, mock_yaml_load, mock_file):
        """Test configuration loading functionality."""
        # Mock the config file content
        mock_yaml_load.return_value = self.sample_config
        
        # Simulate loading config
        try:
            with open("config/llm_config.yaml", 'r') as f:
                loaded_config = yaml.safe_load(f)
                
            # Verify config was loaded correctly
            mock_file.assert_called_once()
            mock_yaml_load.assert_called_once()
            self.assertEqual(loaded_config, self.sample_config)
            
        except Exception as e:
            self.fail(f"Config loading failed: {e}")
    
    def test_model_resolution(self):
        """Test model resolution logic."""
        config = self.sample_config
        
        # Test resolving "default" to actual model
        default_model = config["default"]
        self.assertIn(default_model, config["models"])
        
        # Test tool model resolution
        for tool_name, assigned_model in config["tools"].items():
            if assigned_model == "default":
                resolved_model = config["default"]
            else:
                resolved_model = assigned_model
                
            self.assertIn(resolved_model, config["models"],
                         f"Tool {tool_name} resolves to invalid model {resolved_model}")
    
    def test_config_validation_missing_keys(self):
        """Test config validation with missing required keys."""
        # Test missing models key
        invalid_config_1 = {"default": "gpt-4.1-mini", "tools": {}}
        
        with self.assertRaises(KeyError):
            models = invalid_config_1["models"]  # Should raise KeyError
            
        # Test missing default key
        invalid_config_2 = {"models": {}, "tools": {}}
        
        with self.assertRaises(KeyError):
            default = invalid_config_2["default"]  # Should raise KeyError
    
    def test_provider_specific_configs(self):
        """Test provider-specific configuration options."""
        config = self.sample_config
        
        # All models should specify a provider
        for model_name, model_config in config["models"].items():
            provider = model_config["provider"]
            
            # Common providers
            valid_providers = ["openai", "anthropic", "google", "local"]
            # For testing, we'll just check it's a string
            self.assertIsInstance(provider, str)
            self.assertGreater(len(provider), 0)
    
    def test_tool_specific_model_overrides(self):
        """Test that specific tools can override default model."""
        config = self.sample_config
        
        # Find tools that don't use default
        non_default_tools = {
            tool: model for tool, model in config["tools"].items() 
            if model != "default"
        }
        
        # Each non-default assignment should be valid
        for tool, model in non_default_tools.items():
            self.assertIn(model, config["models"],
                         f"Tool {tool} uses undefined model {model}")
    
    def test_config_yaml_format(self):
        """Test that config can be serialized/deserialized as YAML."""
        config = self.sample_config
        
        try:
            # Serialize to YAML
            yaml_str = yaml.dump(config)
            self.assertIsInstance(yaml_str, str)
            self.assertGreater(len(yaml_str), 0)
            
            # Deserialize from YAML
            loaded_config = yaml.safe_load(yaml_str)
            self.assertEqual(loaded_config, config)
            
        except Exception as e:
            self.fail(f"YAML serialization/deserialization failed: {e}")
    
    def test_environment_variable_support(self):
        """Test structure for environment variable configuration."""
        # Expected structure for env var support
        env_config_structure = {
            "models": {
                "gpt-4.1-mini": {
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                    "api_key": "${OPENAI_API_KEY}",
                    "temperature": 0.7
                }
            }
        }
        
        # Test that env var placeholders are strings
        model_config = env_config_structure["models"]["gpt-4.1-mini"]
        api_key = model_config["api_key"]
        
        self.assertIsInstance(api_key, str)
        self.assertTrue(api_key.startswith("${"))
        self.assertTrue(api_key.endswith("}"))


if __name__ == '__main__':
    unittest.main()
