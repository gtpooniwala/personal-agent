from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from backend.config import llm_config

class SummarisationAgent(BaseTool):
    name: str = "summarisation_agent"
    description: str = "Summarises a conversation history to fit within the context window."

    def _run(self, conversation_history, max_tokens=512):
        # Choose model from config or fallback
        model = llm_config.get('llms', {}).get('summarisation_agent', 'gpt-4.1 mini')
        llm = ChatOpenAI(model=model, temperature=0.2)
        prompt = (
            "Summarise the following conversation so that the key context, facts, and user intent are preserved. "
            "Be concise but do not lose important details.\n\n" + conversation_history
        )
        response = llm.invoke(prompt, max_tokens=max_tokens)
        # Only return the summary text, not the full object
        if hasattr(response, 'content'):
            return response.content
        return str(response)

    async def _arun(self, conversation_history, max_tokens=512):
        return self._run(conversation_history, max_tokens)
