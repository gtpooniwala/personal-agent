"""Tests for provider-agnostic LLM model selection and response normalization."""

import unittest
from unittest.mock import patch

from backend.llm import provider
from backend.llm.provider import (
    MissingModelDependencyError,
    MissingProviderKeyError,
    create_chat_model,
    create_embeddings_model,
    extract_text,
)


class _FakeResponse:
    def __init__(self, content):
        self.content = content


class TestExtractText(unittest.TestCase):
    def test_extract_text_handles_structured_content_blocks(self):
        response = _FakeResponse(
            [
                {"type": "text", "text": "First line"},
                {"type": "thinking", "signature": "ignored"},
                {"type": "text", "text": "Second line"},
            ]
        )

        self.assertEqual(extract_text(response), "First line\nSecond line")

    def test_extract_text_keeps_plain_strings(self):
        response = _FakeResponse("plain text")
        self.assertEqual(extract_text(response), "plain text")


class TestModelFactoryRouting(unittest.TestCase):
    @patch.object(provider.settings, "openai_api_key", "test-openai-key")
    @patch.object(provider, "ChatOpenAI")
    def test_create_chat_model_routes_openai_models_to_chat_openai(self, mock_chat_openai):
        create_chat_model("orchestrator", model_override="gpt-4.1-mini", temperature=0.2, max_tokens=64)
        mock_chat_openai.assert_called_once_with(
            model="gpt-4.1-mini",
            temperature=0.2,
            openai_api_key="test-openai-key",
            max_tokens=64,
        )

    @patch.object(provider.settings, "gemini_api_key", None)
    def test_create_chat_model_requires_gemini_key_when_gemini_selected(self):
        with patch.object(provider, "_load_gemini_chat_class"):
            with self.assertRaises(MissingProviderKeyError):
                create_chat_model("orchestrator", model_override="gemini-3-pro-preview")

    @patch.object(provider.settings, "gemini_api_key", "test-gemini-key")
    @patch.object(provider, "_load_gemini_chat_class")
    def test_create_chat_model_uses_gemini_factory_for_gemini_models(self, mock_load_chat_class):
        fake_chat_class = mock_load_chat_class.return_value
        create_chat_model("orchestrator", model_override="gemini-3-pro-preview", temperature=0.1)
        fake_chat_class.assert_called_once_with(
            model="gemini-3-pro-preview",
            temperature=0.1,
            google_api_key="test-gemini-key",
        )

    @patch.object(provider, "import_module")
    def test_import_gemini_module_wraps_missing_top_level_dependency(self, mock_import_module):
        exc = ModuleNotFoundError("No module named 'langchain_google_genai'")
        exc.name = "langchain_google_genai"
        mock_import_module.side_effect = exc

        with self.assertRaises(MissingModelDependencyError):
            provider._import_gemini_module()

    @patch.object(provider.settings, "openai_api_key", None)
    def test_create_embeddings_model_requires_openai_key_for_openai_embeddings(self):
        with patch.dict(provider.llm_config, {"embeddings": {"provider": "openai", "model": "text-embedding-3-small"}}, clear=False):
            with self.assertRaises(MissingProviderKeyError):
                create_embeddings_model()


if __name__ == "__main__":
    unittest.main()
