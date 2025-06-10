from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)


class TimeInput(BaseModel):
    """Input model for time tool with validation."""
    
    query: str = Field(
        default="now",
        description="Time query - any time-related request"
    )
    
    format_type: Optional[Literal["standard", "verbose", "iso"]] = Field(
        default="standard",
        description="Output format preference"
    )
    
    @validator('query', pre=True)
    def validate_query(cls, v):
        """Validate and normalize the query."""
        if not isinstance(v, str):
            return "now"
        return v.strip().lower()
    
    @validator('format_type', pre=True, always=True)
    def parse_format(cls, v, values):
        """Parse format preference from query."""
        query = values.get('query', '').lower()
        
        if any(word in query for word in ['detailed', 'verbose', 'full']):
            return "verbose"
        elif any(word in query for word in ['iso', 'standard', 'formatted']):
            return "iso"
        else:
            return "standard"


class CurrentTimeTool(BaseTool):
    """
    Date and time information tool with Pydantic input validation.
    
    This specialized tool handles all time-related queries.
    It provides accurate, formatted time information for users.
    
    Features:
    - Current date and time
    - Multiple output formats
    - Timezone awareness (currently local time)
    - Pydantic input validation
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
    
    args_schema = TimeInput
    
    def _run(self, query: str = "now") -> str:
        """
        Get current date and time information using validated input.
        
        Args:
            query: Time-related query (pre-validated by Pydantic)
            
        Returns:
            Formatted current time information
        """
        try:
            # Parse input using Pydantic model
            try:
                parsed_input = TimeInput(query=query)
            except Exception as e:
                # Fallback for simple usage
                parsed_input = TimeInput()
            
            now = datetime.now()
            
            # Format based on parsed preference
            if parsed_input.format_type == "verbose":
                formatted_time = now.strftime('%A, %B %d, %Y at %I:%M:%S %p')
                return f"Current date and time: {formatted_time}"
            elif parsed_input.format_type == "iso":
                formatted_time = now.isoformat()
                return f"Current date and time (ISO format): {formatted_time}"
            else:
                # Standard format
                formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
                return f"Current date and time: {formatted_time}"
            
        except Exception as e:
            logger.error(f"Time tool error: {str(e)}")
            return f"Error getting current time: {str(e)}"
    
    async def _arun(self, query: str = "now") -> str:
        """Async version of the time tool."""
        return self._run(query)
