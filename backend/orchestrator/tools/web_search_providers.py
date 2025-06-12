# Modular web search providers for InternetSearchTool
import requests
from typing import Optional

# --- DuckDuckGo ---
def duckduckgo_search(query: str) -> Optional[str]:
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
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
        return None
    except Exception:
        return None

# --- Bing Web Search ---
def bing_search(query: str, api_key: str) -> Optional[str]:
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "mkt": "en-US"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # Try to extract answer box or first web page snippet
        if "answerBox" in data and "answer" in data["answerBox"]:
            return data["answerBox"]["answer"]
        if "webPages" in data and "value" in data["webPages"]:
            first = data["webPages"]["value"][0]
            if "snippet" in first:
                return first["snippet"]
        return None
    except Exception:
        return None

# --- Google Custom Search ---
def google_search(query: str, api_key: str, cx: str) -> Optional[str]:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": api_key, "cx": cx}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # Try to extract answer box or first result snippet
        if "items" in data and len(data["items"]) > 0:
            return data["items"][0].get("snippet")
        if "answer_box" in data:
            return data["answer_box"].get("answer")
        return None
    except Exception:
        return None

# --- SerpAPI ---
def serpapi_search(query: str, api_key: str) -> Optional[str]:
    url = "https://serpapi.com/search"
    params = {"q": query, "api_key": api_key, "engine": "google"}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # Try to extract answer box or first organic result
        if "answer_box" in data and "answer" in data["answer_box"]:
            return data["answer_box"]["answer"]
        if "organic_results" in data and len(data["organic_results"]) > 0:
            return data["organic_results"][0].get("snippet")
        return None
    except Exception:
        return None
