from langchain.tools import BaseTool
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CurrentTimeTool(BaseTool):
    """
    Date and time information tool/agent.
    
    This specialized tool handles all time-related queries.
    It provides accurate, formatted time information for users.
    
    Features:
    - Current date and time
    - Formatted output for readability
    - Timezone awareness (currently local time)
    - Clear, consistent formatting
    """
    
    name = "current_time"
    description = """Date and time information tool. Use ONLY when explicitly asked about current time, date, or timestamps.

Examples of when to use:
- "What time is it?"
- "What's the date?"
- "Current time"
- "Tell me the time"
- "What day is it?"

Do NOT use for:
- General greetings or conversation
- Scheduling or calendar operations (use calendar tool instead)
- Time calculations (use calculator tool instead)

Input: use 'now' or any time-related query."""
    
    def _run(self, query: str = "now") -> str:
        """
        Get current date and time information.
        
        This provides formatted current time that's easy for users to read
        and understand. The format includes both date and time for completeness.
        """
        try:
            now = datetime.now()
            formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"Time tool executed for query: {query}")
            return f"Current date and time: {formatted_time}"
            
        except Exception as e:
            logger.error(f"Time tool error: {str(e)}")
            return f"Error getting current time: {str(e)}"
    
    async def _arun(self, query: str = "now") -> str:
        """Async version of the time tool."""
        return self._run(query)
