from langchain_core.tools import BaseTool
from backend.llm import create_chat_model, extract_text

class SummarisationAgent(BaseTool):
    """
    Tool: summarisation_agent
    Description: Summarises a conversation history to fit within the context window.

    Features:
    - Summarises long conversations to preserve key context, facts, and user intent
    - Used to keep agent context efficient and within model limits
    - Runs asynchronously in the background after assistant response if conversation is long
    """

    name: str = "summarisation_agent"
    description: str = "Summarises a conversation history to fit within the context window."

    def _build_prompt(self, conversation_history: str) -> str:
        return (
            "Summarise the following conversation so that the key context, facts, and user intent are preserved. "
            "Be concise but do not lose important details.\n\n" + conversation_history
        )

    def _run(self, conversation_history, max_tokens=512):
        llm = create_chat_model(
            "summarisation_agent",
            temperature=0.2,
            max_tokens=max_tokens,
        )
        response = llm.invoke(self._build_prompt(conversation_history))
        return extract_text(response)

    async def _arun(self, conversation_history, max_tokens=512):
        llm = create_chat_model(
            "summarisation_agent",
            temperature=0.2,
            max_tokens=max_tokens,
        )
        response = await llm.ainvoke(self._build_prompt(conversation_history))
        return extract_text(response)
