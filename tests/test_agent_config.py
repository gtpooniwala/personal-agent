"""Tests for backend/config/agent_config.yaml."""
import os
import sys
import unittest

YAML_TESTS_AVAILABLE = True
YAML_IMPORT_ERROR = ""
try:
    import yaml
except Exception as exc:
    YAML_TESTS_AVAILABLE = False
    YAML_IMPORT_ERROR = str(exc)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


@unittest.skipUnless(YAML_TESTS_AVAILABLE, f"YAML dependency unavailable: {YAML_IMPORT_ERROR}")
class TestAgentConfig(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(project_root, "backend", "config", "agent_config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def test_agent_config_has_conversation_naming_section(self):
        self.assertIn("conversation_naming", self.config)
        self.assertIsInstance(self.config["conversation_naming"], dict)

    def test_conversation_naming_has_required_keys(self):
        naming = self.config["conversation_naming"]
        required_keys = [
            "delay_minutes",
            "retry_delay_minutes",
            "title_max_length",
            "context_messages",
            "max_retries",
        ]
        for key in required_keys:
            self.assertIn(key, naming, f"Missing required key: {key}")

    def test_conversation_naming_values_are_positive_integers(self):
        naming = self.config["conversation_naming"]
        for key, value in naming.items():
            self.assertIsInstance(value, int, f"{key} must be an integer, got {type(value)}")
            self.assertGreater(value, 0, f"{key} must be positive, got {value}")


if __name__ == "__main__":
    unittest.main()
