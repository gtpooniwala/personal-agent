import ast
import logging
import math
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

MAX_SAFE_EXPONENT = 100
MAX_AST_NODES = 64
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Load,
)


def _safe_eval_expression(expression: str) -> float:
    """Safely evaluate arithmetic-only expressions."""
    parsed = ast.parse(expression, mode="eval")
    nodes = list(ast.walk(parsed))

    if len(nodes) > MAX_AST_NODES:
        raise ValueError("Expression is too complex.")

    for node in nodes:
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    def _validate_number(value: object) -> int | float:
        if type(value) not in (int, float):
            raise ValueError("Expression produced a non-real result.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Expression produced a non-finite result.")
        return value

    def _eval(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise ValueError("Only numeric literals are allowed.")
            return node.value

        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return _validate_number(+operand)
            if isinstance(node.op, ast.USub):
                return _validate_number(-operand)
            raise ValueError("Unsupported unary operator.")

        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)

            if isinstance(node.op, ast.Add):
                return _validate_number(left + right)
            if isinstance(node.op, ast.Sub):
                return _validate_number(left - right)
            if isinstance(node.op, ast.Mult):
                return _validate_number(left * right)
            if isinstance(node.op, ast.Div):
                return _validate_number(left / right)
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_SAFE_EXPONENT:
                    raise ValueError(
                        f"Exponent magnitude exceeds safe limit ({MAX_SAFE_EXPONENT})."
                    )
                return _validate_number(left**right)

            raise ValueError("Unsupported binary operator.")

        raise ValueError("Unsupported expression.")

    return _validate_number(_eval(parsed))


class CalculatorInput(BaseModel):
    """Input model for calculator tool - expects structured mathematical expression from LLM.
    
    Fields:
        expression (str): Clean mathematical expression to evaluate (e.g., '2**4', '15+27', '100/25').
    """
    
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
        if len(v) > 256:
            raise ValueError("Expression is too long")

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
    
    Features:
    - Secure evaluation of mathematical expressions
    - Supports +, -, *, /, ** (exponentiation)
    - Input validation for safety
    - Used for all math/calculation queries
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
            result = _safe_eval_expression(expression)
            rendered = int(result) if float(result).is_integer() else result
            
            logger.info(f"Calculator tool executed: {expression} = {rendered}")
            return f"The result is: {rendered}"
            
        except ZeroDivisionError:
            return "Error: Division by zero is not allowed."
        except Exception as e:
            logger.error(f"Calculator tool error: {str(e)}")
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, expression: str) -> str:
        """Async version of the calculation tool."""
        return self._run(expression)
