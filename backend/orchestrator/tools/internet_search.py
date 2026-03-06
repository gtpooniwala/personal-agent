from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Literal, Optional
from backend.config import settings
from .web_search_providers import duckduckgo_search, bing_search, google_search, serpapi_search

class InternetSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on the internet.")
    provider: Optional[Literal["bing", "duckduckgo", "google", "serpapi"]] = Field(
        default="duckduckgo", description="Which search provider to use. Defaults to DuckDuckGo."
    )
    # Optionally allow override of API keys (for testing)
    bing_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    google_cx: Optional[str] = None
    serpapi_key: Optional[str] = None

class InternetSearchTool(BaseTool):
    """
    Tool: internet_search
    Purpose: Search the internet for up-to-date information using a configurable provider.
    """
    name: str = "internet_search"
    description: str = (
        "Search the internet for up-to-date information using DuckDuckGo, Bing, Google, or SerpAPI. "
        "Provider is chosen by the LLM or defaults to DuckDuckGo. "
        "Use for general knowledge, research, news, or when the answer is not in documents. "
        "Do NOT use for document-specific, math, or time queries."
    )
    args_schema: type = InternetSearchInput

    def _run(self, query: str, provider: Optional[str] = None, bing_api_key: Optional[str] = None,
             google_api_key: Optional[str] = None, google_cx: Optional[str] = None, serpapi_key: Optional[str] = None) -> str:
        provider = provider or "duckduckgo"
        if provider == "bing":
            api_key = bing_api_key or getattr(settings, "bing_api_key", None)
            if not api_key:
                return "Bing API key not configured. Please set BING_API_KEY in your environment."
            result = bing_search(query, api_key)
        elif provider == "duckduckgo":
            result = duckduckgo_search(query)
        elif provider == "google":
            api_key = google_api_key or getattr(settings, "google_api_key", None)
            cx = google_cx or getattr(settings, "google_cx", None)
            if not api_key or not cx:
                return "Google Custom Search API key and CX not configured."
            result = google_search(query, api_key, cx)
        elif provider == "serpapi":
            api_key = serpapi_key or getattr(settings, "serpapi_key", None)
            if not api_key:
                return "SerpAPI key not configured."
            result = serpapi_search(query, api_key)
        else:
            return f"Unknown search provider: {provider}"
        return result or f"No direct answer found from {provider}. Try rephrasing your query or using a different provider."

    async def _arun(self, query: str, **kwargs) -> str:
        return self._run(query, **kwargs)
