from langchain_core.tools import BaseTool
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Type

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful personal assistant. Given the user's query, the results from all tools used, and optional conversation history, craft a clear, natural, and helpful response for the user. Integrate tool results smoothly, avoid technical jargon, and ensure the answer is easy to understand. Do not decide which tools to use—only synthesize the provided information into a final response. Do not refuse to answer or say 'I don't know' unless absolutely necessary. If you can answer the question directly, do so without relying on the tools."),
            ("user", "{user_query}"),
            ("system", "Here is the recent conversation history (if any):\n{conversation_history_str}"),
            ("assistant", "{tool_results_str}"),
            ("system", "Now, using all the above information, write a single, clear, natural, and helpful response for the user. Do not echo the user query. Do not mention tool names. Just answer as a helpful assistant.")
        ])
        
        # Use the new RunnableSequence pattern: prompt | llm
        object.__setattr__(self, "chain", prompt | llm)

    def _run(self, user_query: str, tool_results: List[Dict[str, Any]], conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
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
        response = self.chain.invoke(inputs)
        return response.content if hasattr(response, "content") else str(response)
