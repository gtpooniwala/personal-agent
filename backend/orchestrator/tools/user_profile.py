from pydantic import BaseModel, Field, PrivateAttr
from typing import Literal, Optional, Dict, Any
import os
import json
from backend.config import settings
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool

# Use BASE_DIR from environment or fallback to project root
BASE_DIR = os.environ.get("BASE_DIR")
if not BASE_DIR:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
USER_PROFILE_DIR = os.path.join(BASE_DIR, "data", "user_profiles")
os.makedirs(USER_PROFILE_DIR, exist_ok=True)

def get_profile_path(user_id: str) -> str:
    return os.path.join(USER_PROFILE_DIR, f"{user_id}.json")

def load_user_profile(user_id: str) -> Dict[str, Any]:
    path = get_profile_path(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_user_profile(user_id: str, profile: Dict[str, Any]):
    path = get_profile_path(user_id)
    print(f"[DEBUG] Writing profile for user_id={user_id} to {path}: {profile}")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)

class UserProfileInput(BaseModel):
    action: Literal["read", "update"] = Field(..., description="Read or update the user profile.")
    instruction: Optional[str] = Field(None, description="A natural language instruction describing what to do with the user profile, such as add, update, delete, or modify specific information. This can include both what to change and the new information.")
    user_prompt: Optional[str] = Field(None, description="The full, original user message that triggered this update. Always include this for updates.")

class UserProfileTool(BaseTool):
    name: str = "user_profile"
    description: str = (
        "Read or update the user's profile. "
        "The user profile is for long-term, user-specific memory: persistent facts, preferences, background, and traits that should be remembered across all conversations. "
        "The scratchpad is for temporary, conversation-specific notes and should NOT be used for long-term or user-specific information. "
        "Whenever you learn new information about the user that should be remembered for future conversations, use this tool to update the profile. "
        "Whenever you need to personalize your answer, understand the user's background, or even if you think the user profile might be remotely relevant to the current question, proactively retrieve the user profile for context. "
        "Err on the side of reading the user profile whenever in doubt—it is better to have more context than less. "
        "When updating the user profile, ALWAYS use this tool for any information about the user's identity, preferences, background, or persistent facts. Do NOT use the scratchpad for this purpose. "
        "When updating, provide a natural language instruction describing what to do (e.g., add, update, delete, or modify specific information) and the new information or context. "
        "ALWAYS include the full, original user message (user_prompt) that triggered this update, so the LLM can extract all relevant facts. "
        "Use 'read' to get the current profile for context. "
        "Use 'update' to add, update, or delete information in the user profile using a natural language instruction and the user's original message. "
        "For 'update', the tool will use the LLM to interpret the instruction and user_prompt and modify the profile accordingly."
    )
    args_schema: type = UserProfileInput
    _user_id: str = PrivateAttr()
    _llm: Any = PrivateAttr()

    def __init__(self, user_id: str = "default"):
        super().__init__()
        self._user_id = user_id
        self._llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.2,
            openai_api_key=settings.openai_api_key,
            max_tokens=600
        )

    def _run(self, action: str, instruction: Optional[str] = None, user_prompt: Optional[str] = None) -> dict:
        if action == "read":
            return load_user_profile(self._user_id)
        elif action == "update":
            current_profile = load_user_profile(self._user_id)
            updated_profile = self._merge_profile_with_llm(current_profile, instruction, user_prompt)
            save_user_profile(self._user_id, updated_profile)
            return updated_profile
        else:
            return {"error": f"Unknown action: {action}"}

    async def _arun(self, action: str, instruction: Optional[str] = None) -> dict:
        return self._run(action, instruction)

    def _merge_profile_with_llm(self, current_profile: Dict[str, Any], instruction: Optional[str], user_prompt: Optional[str]) -> Dict[str, Any]:
        prompt = f"""
You are an assistant that maintains a structured user profile for personalization.\n
Current profile (JSON):\n{json.dumps(current_profile, indent=2)}\n
Instruction: {instruction}\n
User's original message: {user_prompt}\n
Extract all relevant facts about the user from the user's message and update the profile as instructed. You may add, update, or delete any information as requested.\n
IMPORTANT: Only use the scratchpad for temporary, session-specific notes. For all persistent, user-specific facts, preferences, or background, ALWAYS use the user profile.\n
Return the updated profile as a valid JSON object only, with no extra text or explanation. Do not lose any existing information unless it is contradicted by the instruction or user message.\n"""
        response = self._llm.invoke(prompt)
        response_text = getattr(response, 'content', str(response))
        print(f"[DEBUG] LLM response: {response_text}")
        try:
            # Try to extract JSON from the LLM response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end != -1:
                result = json.loads(response_text[start:end])
                print(f"[DEBUG] Parsed LLM result: {result}")
                return result
        except Exception as e:
            print(f"[UserProfileTool] LLM JSON parse failed: {e}. Returning current profile.")
        # Final fallback: return current profile if all else fails
        print(f"[DEBUG] Returning current profile: {current_profile}")
        return current_profile
