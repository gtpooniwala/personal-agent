from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests

class InternetSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on the internet.")

class InternetSearchTool(BaseTool):
    """
    Tool: internet_search
    Purpose: Search the internet for up-to-date information using DuckDuckGo Instant Answer API.

    When to use:
    - Use this tool for general knowledge, research, current events, facts, or questions that require up-to-date information from the web.
    - Use when the answer is not found in uploaded documents or is not a calculation or time query.
    - Do NOT use for document-specific, math, or time queries.

    Example triggers:
    - "Who is the president of the United States?"
    - "What is the capital of France?"
    - "Latest news about AI regulation."
    - "How tall is Mount Everest?"
    - "What is the weather in Paris?"

    Example non-triggers:
    - "What does my contract say?" (use document search)
    - "What is 2+2?" (use calculator)
    - "What time is it?" (use time tool)
    """
    name: str = "internet_search"
    description: str = (
        "Search the internet for up-to-date information using DuckDuckGo Instant Answer API. "
        "Use for general knowledge, research, news, or when the answer is not in documents. "
        "Do NOT use for document-specific, math, or time queries."
    )
    args_schema: type = InternetSearchInput

    def _run(self, query: str) -> str:
        """Synchronous search using DuckDuckGo Instant Answer API."""
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            # Prefer AbstractText, fallback to related topics or answer
            if data.get("AbstractText"):
                return data["AbstractText"]
            elif data.get("Answer"):
                return data["Answer"]
            elif data.get("RelatedTopics"):
                topics = data["RelatedTopics"]
                if topics and isinstance(topics, list):
                    first = topics[0]
                    if isinstance(first, dict) and first.get("Text"):
                        return first["Text"]
            return "No direct answer found, but you can try rephrasing your query."
        except Exception as e:
            return f"Internet search failed: {e}"

    async def _arun(self, query: str) -> str:
        # For now, just call the sync version
        return self._run(query)
