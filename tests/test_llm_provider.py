"""Tests for provider-agnostic LLM response normalization."""

import unittest

from backend.llm.provider import extract_text


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


if __name__ == "__main__":
    unittest.main()
