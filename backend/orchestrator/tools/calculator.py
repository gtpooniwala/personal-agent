from langchain.tools import BaseTool
from pydantic import BaseModel, Field, field_validator
from typing import Type
import logging
import re

logger = logging.getLogger(__name__)


class CalculatorInput(BaseModel):
    """Input model for calculator tool - expects structured mathematical expression from LLM."""
    
    expression: str = Field(
        description="Clean mathematical expression to evaluate (e.g., '2**4', '15+27', '100/25'). Use ** for exponentiation, not ^.",
        min_length=1
    )
    
    @field_validator('expression')
    @classmethod
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
    
    name: str = "calculator"
    description: str = """Perform mathematical calculations with precision.

Use for any mathematical expressions, calculations, or computations.
Accepts standard math notation: +, -, *, /, ** (for exponents).
Examples: "2**8", "15*7", "200*0.25", "(15+5)/4" """
    
    args_schema: Type[BaseModel] = CalculatorInput
    
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
