# Internet Search Tool

## Overview
The Internet Search Tool enables the agent to search the web for up-to-date information using multiple providers (DuckDuckGo, Bing, Google, SerpAPI). It is used for general knowledge, research, and news queries.

## Features Implemented
- Supports multiple search providers
- API key integration for Bing, Google, SerpAPI
- Used for general knowledge, research, and news
- Not used for document-specific, math, or time queries
- Always available to the agent

## Technical Implementation
- Tool: `InternetSearchTool` (Pydantic + LangChain BaseTool)
- Providers: DuckDuckGo (default), Bing, Google, SerpAPI
- Provider selection via input or LLM
- API keys set via environment/config

## Usage Examples
- "Search the web for latest AI news"
- "Find recent research on quantum computing"

## Files Modified
- `backend/orchestrator/tools/internet_search.py`
- `backend/orchestrator/tools/web_search_providers.py`
- `backend/orchestrator/tool_registry.py`
