"""Tests for backend/config/llm_config.yaml."""
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
class TestLLMConfiguration(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(project_root, "backend", "config", "llm_config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def test_llm_config_has_required_top_level_keys(self):
        self.assertIn("llms", self.config)
        self.assertIsInstance(self.config["llms"], dict)

    def test_llm_config_includes_default_model(self):
        llms = self.config["llms"]
        self.assertIn("default", llms)
        self.assertIsInstance(llms["default"], str)
        self.assertGreater(len(llms["default"].strip()), 0)

    def test_llm_config_has_required_tool_mappings(self):
        llms = self.config["llms"]
        required_tool_keys = [
            "orchestrator",
            "response_agent",
            "document_qa",
            "user_profile",
            "planning_tool",
            "internet_search",
            "summarisation_agent",
        ]
        for key in required_tool_keys:
            self.assertIn(key, llms)
            self.assertIsInstance(llms[key], str)
            self.assertGreater(len(llms[key].strip()), 0)

    def test_llm_config_values_are_strings(self):
        for key, value in self.config["llms"].items():
            self.assertIsInstance(value, str, f"{key} should map to a model name string")


if __name__ == "__main__":
    unittest.main()
