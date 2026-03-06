from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, PrivateAttr
from typing import List, Dict, Any, Optional, Type

from backend.llm import create_chat_model, MissingProviderKeyError, MissingModelDependencyError

class ResponseAgentInput(BaseModel):
    """Input for the Response Agent. Contains all information and tool results needed to craft the final user response.
    
    Fields:
        user_query (str): The original user query.
        tool_results (list): Results from all tools used for this user query.
        conversation_history (list): Recent conversation history for context (optional).
    """
    user_query: str = Field(..., description="The original user query.")
    tool_results: List[Dict[str, Any]] = Field(
        ..., description="A list of results from all tools used for this user query. Each result should include the tool name, input, and output.")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Recent conversation history for context (optional). Each message should have a role and content.")

class ResponseAgentTool(BaseTool):
    """
    Tool: response_agent
    Description: Synthesizes a final, user-facing response from the user query, tool results, and conversation history using a modern LangChain Runnable (prompt | llm).
    
    Features:
    - Synthesizes tool results and conversation history into a single, natural response
    - Avoids technical jargon/tool names in user answers
    - Used as the final step in every agent workflow
    """
    name: str = "response_agent"
    description: str = (
        "Given a user query, a list of tool results, and optional conversation history, generates a clear, natural, and helpful response for the user. "
        "This tool is for synthesizing the final answer after all tool calls are complete. "
        "It does not select or invoke tools itself." \
    )
    args_schema: Type[BaseModel] = ResponseAgentInput
    _chain: Any = PrivateAttr(default=None)
    _initialization_error: Optional[str] = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            llm = create_chat_model("response_agent", temperature=0.3)
            prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "You are a helpful personal assistant. Given the user's query, tool results, and optional conversation history, craft a clear and natural final response. Do not mention tool names.",
                ),
                (
                    "user",
                    "User query:\n{user_query}\n\nConversation history:\n{conversation_history_str}\n\nTool results:\n{tool_results_str}\n\nRespond to the user directly.",
                ),
            ])
            self._chain = prompt | llm
        except (MissingProviderKeyError, MissingModelDependencyError) as exc:
            self._initialization_error = str(exc)

    def _run(self, user_query: str, tool_results: List[Dict[str, Any]], conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        if self._initialization_error:
            return self._initialization_error
        # Prepare tool results as a string for the prompt
        tool_results_str = "\n".join([
            f"[{tr.get('tool', 'tool')}] {tr.get('output', '')}" for tr in tool_results if tr.get('output', '')
        ]) if tool_results else ""
        # Format conversation history for the prompt
        if conversation_history:
            conversation_history_str = "\n".join([
                f"{msg.get('role', '').capitalize()}: {msg.get('content', '')}" for msg in conversation_history
            ])
        else:
            conversation_history_str = "(No prior conversation history)"
        inputs = {
            "user_query": user_query,
            "tool_results_str": tool_results_str,
            "conversation_history_str": conversation_history_str,
        }
        response = self._chain.invoke(inputs)
        return response.content if hasattr(response, "content") else str(response)
