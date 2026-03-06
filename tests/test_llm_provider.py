"""Tests for backend.llm.provider model/provider routing behavior."""

import os
import sys
import unittest
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
        ) as mock_openai_embeddings, patch(
            "backend.llm.provider.GoogleGenerativeAIEmbeddings"
        ) as mock_gemini_embeddings:
            expected = object()
            mock_openai_embeddings.return_value = expected

            actual = provider.create_embeddings_model()

            self.assertIs(actual, expected)
            mock_openai_embeddings.assert_called_once_with(
                model="text-embedding-3-small",
                openai_api_key="test-openai-key",
            )
            mock_gemini_embeddings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
