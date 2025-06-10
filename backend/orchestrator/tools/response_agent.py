from langchain_core.tools import BaseTool
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Type

class ResponseAgentInput(BaseModel):
    """Input for the Response Agent. Contains all information and tool results needed to craft the final user response."""
    user_query: str = Field(..., description="The original user query.")
    tool_results: List[Dict[str, Any]] = Field(
        ..., description="A list of results from all tools used for this user query. Each result should include the tool name, input, and output.")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Recent conversation history for context (optional). Each message should have a role and content.")

class ResponseAgentTool(BaseTool):
    """
    Tool: response_agent
    Description: Synthesizes a final, user-facing response from the user query, tool results, and conversation history using an LLMChain. This tool does not select or invoke other tools; it only generates the final answer for the user based on provided context and tool outputs.
    """
    name: str = "response_agent"
    description: str = (
        "Given a user query, a list of tool results, and optional conversation history, generates a clear, natural, and helpful response for the user. "
        "This tool is for synthesizing the final answer after all tool calls are complete. "
        "It does not select or invoke tools itself."
    )
    args_schema: Type[BaseModel] = ResponseAgentInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful personal assistant. Given the user's query, the results from all tools used, and optional conversation history, craft a clear, natural, and helpful response for the user. Integrate tool results smoothly, avoid technical jargon, and ensure the answer is easy to understand. Do not decide which tools to use—only synthesize the provided information into a final response. Do not refuse to answer or say 'I don't know' unless absolutely necessary. If you can answer the question directly, do so without relying on the tools."),
            ("user", "{user_query}"),
            ("assistant", "{tool_results_str}"),
            ("system", "Now, using all the above information, write a single, clear, natural, and helpful response for the user. Do not echo the user query. Do not mention tool names. Just answer as a helpful assistant.")
        ])
        object.__setattr__(self, "chain", LLMChain(llm=llm, prompt=prompt))

    def _run(self, user_query: str, tool_results: List[Dict[str, Any]], conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        # Prepare tool results as a string for the prompt
        tool_results_str = "\n".join([
            f"[{tr.get('tool', 'tool')}] {tr.get('output', '')}" for tr in tool_results if tr.get('output', '')
        ]) if tool_results else ""
        # Optionally, you could also include conversation_history in the prompt if needed
        inputs = {
            "user_query": user_query,
            "tool_results_str": tool_results_str,
        }
        response = self.chain.invoke(inputs)
        return response["text"] if isinstance(response, dict) and "text" in response else str(response)
