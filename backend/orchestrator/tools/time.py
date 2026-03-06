from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal, Type
import logging

logger = logging.getLogger(__name__)


class TimeInput(BaseModel):
    """Input model for time tool with validation.
    
    Fields:
        query (str): Time query (e.g., 'now', 'current time', 'today')
        format_type (str): Output format preference (standard, verbose, iso)
    """
    
    query: str = Field(
        default="now",
        description="Time query - any time-related request"
    )
    
    format_type: Optional[Literal["standard", "verbose", "iso"]] = Field(
        default="standard",
        description="Output format preference"
    )
    
    @field_validator('query', mode='before')
    @classmethod
    def validate_query(cls, v):
        """Validate and normalize the query."""
        if not isinstance(v, str):
            return "now"
        return v.strip().lower()
    
    @field_validator('format_type', mode='before')
    @classmethod
    def parse_format(cls, v):
        """Parse format preference from query."""
        # Since we can't access other fields in V2, use a simple default
        if v is None:
            return "standard"
        return v


class CurrentTimeTool(BaseTool):
    """
    Date and time information tool with Pydantic input validation.
    
    Features:
    - Current date and time
    - Multiple output formats (standard, verbose, iso)
    - Timezone awareness (local time)
    - Input validation
    - Used for all time/date queries
    """
    
    name: str = "current_time"
    description: str = """Get current date and time information.

Use when users ask for current time, date, or temporal information.
Provides real-time data the LLM cannot access.
Examples: "What time is it?", "What's today's date?", "current time" """
    
    args_schema: Type[BaseModel] = TimeInput
    
    def _run(
        self,
        query: str = "now",
        format_type: Optional[Literal["standard", "verbose", "iso"]] = "standard",
        **kwargs,
    ) -> str:
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
                parsed_input = TimeInput(query=query, format_type=format_type)
            except Exception:
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
    
    async def _arun(
        self,
        query: str = "now",
        format_type: Optional[Literal["standard", "verbose", "iso"]] = "standard",
        **kwargs,
    ) -> str:
        """Async version of the time tool."""
        return self._run(query=query, format_type=format_type, **kwargs)
