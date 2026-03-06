"""Tests for backend.llm.provider model/provider routing behavior."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.llm import provider


class TestLLMProviderRouting(unittest.TestCase):
    def test_split_provider_model_infers_openai_embedding_models(self):
        inferred_provider, inferred_model = provider._split_provider_model(
            "text-embedding-3-small", "gemini"
        )
        self.assertEqual(inferred_provider, "openai")
        self.assertEqual(inferred_model, "text-embedding-3-small")

    def test_create_embeddings_model_routes_text_embedding_to_openai(self):
        config = {
            "providers": {"default": "gemini"},
            "embeddings": {"model": "text-embedding-3-small"},
        }

        with patch.object(provider, "llm_config", config), patch.object(
            provider.settings, "openai_api_key", "test-openai-key"
        ), patch.object(provider.settings, "gemini_api_key", "test-gemini-key"), patch(
            "backend.llm.provider.OpenAIEmbeddings"
        ) as mock_openai_embeddings, patch.object(
            provider, "_load_gemini_embeddings_class"
        ) as mock_load_gemini_embeddings_class:
            expected = object()
            mock_openai_embeddings.return_value = expected

            actual = provider.create_embeddings_model()

            self.assertIs(actual, expected)
            mock_openai_embeddings.assert_called_once_with(
                model="text-embedding-3-small",
                openai_api_key="test-openai-key",
            )
            mock_load_gemini_embeddings_class.assert_not_called()

    def test_import_gemini_module_maps_missing_package_to_dependency_error(self):
        missing_error = ModuleNotFoundError("No module named 'langchain_google_genai'")
        missing_error.name = "langchain_google_genai"

        with patch("backend.llm.provider.import_module", side_effect=missing_error):
            with self.assertRaises(provider.MissingModelDependencyError) as ctx:
                provider._import_gemini_module()

        self.assertIn("langchain-google-genai is not installed", str(ctx.exception))

    def test_import_gemini_module_does_not_mask_runtime_import_failure(self):
        with patch("backend.llm.provider.import_module", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                provider._import_gemini_module()

    def test_load_gemini_classes_read_from_imported_module(self):
        fake_module = SimpleNamespace(
            ChatGoogleGenerativeAI=object,
            GoogleGenerativeAIEmbeddings=object,
        )
        with patch("backend.llm.provider.import_module", return_value=fake_module):
            self.assertIs(provider._load_gemini_chat_class(), object)
            self.assertIs(provider._load_gemini_embeddings_class(), object)


if __name__ == "__main__":
    unittest.main()
