from langchain.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


class CalculatorTool(BaseTool):
    """
    Mathematical calculation tool/agent.
    
    This is a specialized tool that handles all mathematical computations.
    It's designed to be safe, reliable, and transparent about its operations.
    
    Features:
    - Supports basic arithmetic (+, -, *, /)
    - Handles exponentiation (^ converted to **)
    - Input validation for security
    - Clear error reporting
    """
    
    name = "calculator"
    description = """Mathematical calculation tool. Use this for ANY mathematical calculations, arithmetic, or numeric problems. 

Examples of when to use:
- "What is 2 + 3?"
- "Calculate 15 * 27"  
- "What's 2^4?"
- "Divide 100 by 25"

Input should be a mathematical expression like '2+3', '10*5', '2**4'.
NEVER do mental math - ALWAYS use this tool for numbers.
Do NOT use for simple greetings, general conversation, or non-mathematical questions."""
    
    def _run(self, query: str) -> str:
        """
        Execute mathematical calculation.
        
        This is the core calculation logic that:
        1. Extracts mathematical expressions from natural language
        2. Sanitizes input for security
        3. Converts user-friendly notation (^ to **)
        4. Safely evaluates the expression
        5. Returns clear results or error messages
        """
        try:
            # Extract mathematical expression from natural language
            import re
            
            # Common word-to-operator mappings
            query = query.lower().strip()
            query = re.sub(r'\bdivided by\b', '/', query)
            query = re.sub(r'\btimes\b', '*', query)
            query = re.sub(r'\bplus\b', '+', query)
            query = re.sub(r'\bminus\b', '-', query)
            query = re.sub(r'\bto the power of\b', '**', query)
            
            # Extract numbers and mathematical operators using regex first
            # Match mathematical expressions including numbers, operators, and parentheses
            math_expressions = re.findall(r'\d+(?:\.\d+)?(?:\s*[+\-*/^]\s*\d+(?:\.\d+)?)*', query)
            
            if math_expressions:
                # Use the longest mathematical expression found
                expression = max(math_expressions, key=len)
            else:
                # Fallback: try to extract any sequence with numbers and operators
                expression = re.sub(r'[^0-9+\-*/^().\s]', '', query)
                
            # Replace ^ with ** for exponentiation (user-friendly input) AFTER extraction
            expression = expression.replace('^', '**')
                
            # Clean up the expression
            expression = expression.strip()
            if not expression:
                return "Error: No valid mathematical expression found."
            
            # Replace multiple spaces with single space and clean up
            expression = re.sub(r'\s+', '', expression)  # Remove all spaces for evaluation
            
            # Final security check - only allow safe mathematical characters
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in mathematical expression. Only numbers and basic operators (+, -, *, /, ^, parentheses) are allowed."
            
            # Evaluate the mathematical expression
            result = eval(expression)
            
            logger.info(f"Calculator tool executed: {query} -> {expression} = {result}")
            return f"The result is: {result}"
            
        except ZeroDivisionError:
            return "Error: Division by zero is not allowed."
        except SyntaxError:
            return "Error: Invalid mathematical expression. Please check your syntax."
        except Exception as e:
            logger.error(f"Calculator tool error: {str(e)}")
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the calculation tool."""
        return self._run(query)
