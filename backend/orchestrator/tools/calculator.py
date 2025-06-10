from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator
import logging
import re

logger = logging.getLogger(__name__)


class CalculatorInput(BaseModel):
    """Input model for calculator tool - expects structured mathematical expression from LLM."""
    
    expression: str = Field(
        description="Clean mathematical expression to evaluate (e.g., '2**4', '15+27', '100/25'). Use ** for exponentiation, not ^.",
        min_length=1
    )
    
    @validator('expression')
    def validate_expression(cls, v: str) -> str:
        """Validate that the expression contains only safe mathematical characters."""
        if not isinstance(v, str):
            raise ValueError("Expression must be a string")
            
        v = v.strip()
        if not v:
            raise ValueError("Expression cannot be empty")
        
        # Only allow safe mathematical characters
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in v):
            raise ValueError("Expression contains invalid characters. Only numbers and operators (+, -, *, /, **, parentheses) are allowed")
        
        # Basic syntax check
        try:
            compile(v, '<string>', 'eval')
        except SyntaxError:
            raise ValueError("Invalid mathematical expression syntax")
            
        return v


class CalculatorTool(BaseTool):
    """
    Mathematical calculation tool expecting structured input from LLM.
    
    The LLM should provide clean mathematical expressions ready for evaluation.
    """
    
    name = "calculator"
    description = """Mathematical calculation tool. Provide a clean mathematical expression for evaluation.

IMPORTANT: 
- Use ** for exponentiation, not ^
- Provide expressions ready for evaluation: '2**4', '15+27', '100/25'
- Do not include natural language - only mathematical expressions

Examples:
- For "2 to the power of 4": use expression="2**4"
- For "15 plus 27": use expression="15+27"  
- For "100 divided by 25": use expression="100/25"

The LLM should parse natural language and convert to proper mathematical notation."""
    
    args_schema = CalculatorInput
    
    def _run(self, expression: str) -> str:
        """
        Execute mathematical calculation with validated expression.
        
        Args:
            expression: Clean mathematical expression (validated by Pydantic)
            
        Returns:
            String containing the calculation result
        """
        try:
            # Pydantic has already validated the expression
            result = eval(expression)
            
            logger.info(f"Calculator tool executed: {expression} = {result}")
            return f"The result is: {result}"
            
        except ZeroDivisionError:
            return "Error: Division by zero is not allowed."
        except Exception as e:
            logger.error(f"Calculator tool error: {str(e)}")
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, expression: str) -> str:
        """Async version of the calculation tool."""
        return self._run(expression)
