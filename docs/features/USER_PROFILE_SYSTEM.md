# User Profile System

## Overview
The User Profile Tool provides persistent, user-specific memory for the agent. It stores facts, preferences, background, and traits that should be remembered across all conversations, enabling deep personalization and long-term context.

## Features Implemented
- Read and update user profile with natural language instructions
- LLM-powered extraction and merging of profile data
- Profile is stored as structured JSON per user
- Used for personalization, context, and remembering user facts
- Always available to the agent

## Technical Implementation
- Tool: `UserProfileTool` (Pydantic + LangChain BaseTool)
- Actions: `read` (retrieve profile), `update` (modify profile)
- LLM interprets instructions and merges new info into profile
- Profile stored in `data/user_profiles/{user_id}.json`
- Not for temporary notes (use ScratchpadTool for that)

## Usage Examples
- "Remember my favorite color is blue"
- "What do you know about me?"
- "Update my profile: I moved to New York"

## Files Modified
- `backend/orchestrator/tools/user_profile.py`
- `backend/orchestrator/tool_registry.py`
