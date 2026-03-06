# Orchestrator module for the Personal Agent
import warnings

# LangChain 1.2.x imports a compatibility shim that emits this warning on Python 3.14.
# Keep this narrowly scoped to the known upstream message.
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    category=UserWarning,
    module=r"langchain_core\._api\.deprecation",
)

from .core import CoreOrchestrator
from .tool_registry import ToolRegistry

__all__ = ['CoreOrchestrator', 'ToolRegistry']
