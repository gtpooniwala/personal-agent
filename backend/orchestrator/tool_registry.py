from datetime import datetime, timezone
from typing import Callable, Dict, List, Any, Optional
from time import monotonic
from backend.config import settings
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr
from .tools.calculator import CalculatorTool
from .tools.time import CurrentTimeTool
from .tools.search_documents import SearchDocumentsTool
from .tools.scratchpad import ScratchpadTool
from .tools.response_agent import ResponseAgentTool
from .tools.gmail import GmailReadTool, get_gmail_readiness
from .tools.user_profile import UserProfileTool
from .tools.summarisation_agent import SummarisationAgent
from backend.orchestrator.tools.internet_search import InternetSearchTool
import logging

logger = logging.getLogger(__name__)


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class InstrumentedTool(BaseTool):
    """Run-scoped wrapper that records tool-call latency without changing behavior."""

    name: str
    description: str
    args_schema: Any = None
    return_direct: bool = False
    _wrapped: BaseTool = PrivateAttr()
    _timing_sink: Optional[Callable[[Dict[str, Any]], None]] = PrivateAttr(default=None)

    def __init__(
        self,
        wrapped: BaseTool,
        timing_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__(
            name=wrapped.name,
            description=wrapped.description,
            args_schema=getattr(wrapped, "args_schema", None),
            return_direct=getattr(wrapped, "return_direct", False),
        )
        self._wrapped = wrapped
        self._timing_sink = timing_sink

    def _record_timing(self, started_at: float, started_timestamp: datetime) -> None:
        if self._timing_sink is None:
            return
        ended_timestamp = datetime.now(timezone.utc)
        duration_ms = max(int((monotonic() - started_at) * 1000), 0)
        self._timing_sink(
            {
                "tool": self.name,
                "started_at": _isoformat_utc(started_timestamp),
                "ended_at": _isoformat_utc(ended_timestamp),
                "duration_ms": duration_ms,
            }
        )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        started_at = monotonic()
        started_timestamp = datetime.now(timezone.utc)
        try:
            return self._wrapped._run(*args, **kwargs)
        finally:
            self._record_timing(started_at, started_timestamp)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        started_at = monotonic()
        started_timestamp = datetime.now(timezone.utc)
        try:
            wrapped_arun = getattr(self._wrapped, "_arun", None)
            if callable(wrapped_arun):
                return await wrapped_arun(*args, **kwargs)
            return self._wrapped._run(*args, **kwargs)
        finally:
            self._record_timing(started_at, started_timestamp)


class ToolRegistry:
    """
    Registry for managing available tools and agents in the orchestrator system.
    
    This is the central hub that:
    1. Manages all available tools/agents
    2. Handles tool lifecycle (initialization, updates, etc.)
    3. Provides tools to the orchestrator based on context
    4. Supports dynamic tool addition/removal
    
    The registry makes it easy to add new tools - just implement the tool
    and register it here. The orchestrator will automatically discover it.
    """

    GMAIL_CAPABILITY_REFRESH_TTL_SECONDS = 5.0
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        self.user_id = user_id
        self.selected_documents = list(selected_documents or [])
        self._tools = {}
        self._last_runtime_capability_refresh_at: Optional[float] = None
        self._tool_timing_sink: Optional[Callable[[Dict[str, Any]], None]] = None
        self._initialize_tools()

    def _initialize_tools(self):
        """
        Initialize all available tools/agents.
        """
        # Core computational tools (always available)
        self._tools["calculator"] = CalculatorTool()
        self._tools["current_time"] = CurrentTimeTool()
        self._tools["scratchpad"] = ScratchpadTool(self.user_id)
        self._sync_gmail_tool()

        # Response agent tool (for handling responses)
        self._tools["response_agent"] = ResponseAgentTool()

        # Internet search tool (for web searching)
        self._tools["internet_search"] = InternetSearchTool()

        # User profile tool (always available)
        self._tools["user_profile"] = UserProfileTool(self.user_id)
        # Summarisation agent (always available)
        self._tools["summarisation_agent"] = SummarisationAgent()
        self._set_search_documents_tool(self.selected_documents)

    def _sync_gmail_tool(self) -> None:
        gmail_ready, gmail_reasons = get_gmail_readiness(
            settings.enable_gmail_integration,
            self.user_id,
        )
        if gmail_ready:
            gmail_tool: BaseTool = GmailReadTool(self.user_id)
            if self._tool_timing_sink is not None:
                gmail_tool = InstrumentedTool(gmail_tool, self._tool_timing_sink)
            self._tools["gmail_read"] = gmail_tool
            self._last_runtime_capability_refresh_at = monotonic()
            return

        self._tools.pop("gmail_read", None)
        logger.info(
            "Skipping gmail_read tool registration: %s",
            ", ".join(gmail_reasons),
        )
        self._last_runtime_capability_refresh_at = monotonic()

    def refresh_runtime_capabilities(self, *, force: bool = False) -> None:
        """Refresh tools whose availability can change at runtime."""
        if not force and self._last_runtime_capability_refresh_at is not None:
            if monotonic() - self._last_runtime_capability_refresh_at < self.GMAIL_CAPABILITY_REFRESH_TTL_SECONDS:
                return
        self._sync_gmail_tool()

    def _set_search_documents_tool(self, selected_documents: Optional[List[str]]) -> None:
        """Refresh the document-scoped search tool without rebuilding static tools."""
        self.selected_documents = list(selected_documents or [])
        if self.selected_documents:
            self._tools["search_documents"] = SearchDocumentsTool(self.user_id, self.selected_documents)
        else:
            self._tools.pop("search_documents", None)

    def update_selected_documents(self, selected_documents: List[str]):
        """
        Update the context for document-dependent tools.
        """
        self._set_search_documents_tool(selected_documents)
        logger.info(f"Updated tool registry with {len(selected_documents)} selected documents")

    def clone_with_selected_documents(
        self,
        selected_documents: Optional[List[str]] = None,
        *,
        tool_timing_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> "ToolRegistry":
        """
        Create a run-scoped registry that reuses static tool instances and rebuilds
        only document-dependent state.
        """
        clone = object.__new__(ToolRegistry)
        clone.user_id = self.user_id
        clone._tools = {name: tool for name, tool in self._tools.items() if name != "search_documents"}
        clone.selected_documents = []
        clone._last_runtime_capability_refresh_at = self._last_runtime_capability_refresh_at
        clone._tool_timing_sink = tool_timing_sink
        clone._set_search_documents_tool(selected_documents)
        if tool_timing_sink is not None:
            clone.refresh_runtime_capabilities(force=True)
            clone._wrap_active_tools(tool_timing_sink)
        return clone

    def _wrap_active_tools(
        self,
        timing_sink: Callable[[Dict[str, Any]], None],
    ) -> None:
        self._tool_timing_sink = timing_sink
        for tool_name in ("calculator", "current_time", "scratchpad", "internet_search", "user_profile", "gmail_read", "search_documents"):
            tool = self._tools.get(tool_name)
            if tool is not None:
                if isinstance(tool, InstrumentedTool):
                    tool = tool._wrapped
                self._tools[tool_name] = InstrumentedTool(tool, timing_sink)

    def get_available_tools(self) -> List[Any]:
        """
        Get list of tools that should be available to the orchestrator.
        """
        self.refresh_runtime_capabilities()
        # This is capability gating only. The model owns normal tool selection
        # from the tools exposed here.
        available_tools = ["calculator", "current_time", "scratchpad", "internet_search", "user_profile"]
        if "gmail_read" in self._tools:
            available_tools.append("gmail_read")
        # Only include search_documents if documents are selected
        if self.selected_documents and len(self.selected_documents) > 0:
            available_tools.append("search_documents")
        return [self._tools[tool_name] for tool_name in available_tools if tool_name in self._tools]
    
    def get_all_tools(self) -> List[Any]:
        """Get all tools including inactive/placeholder ones."""
        return list(self._tools.values())
    
    def register_tool(self, name: str, tool: Any):
        """
        Register a new tool with the registry.
        
        This allows dynamic tool addition at runtime.
        
        Args:
            name: Unique identifier for the tool
            tool: Tool instance implementing the required interface
        """
        self._tools[name] = tool
        logger.info(f"Registered new tool: {name}")
    
    def unregister_tool(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Returns:
            bool: True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get_tool(self, name: str) -> Any:
        """Get a specific tool by name."""
        return self._tools.get(name)
    
    def list_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())
    
    def get_tool_info(self) -> List[Dict[str, str]]:
        """Get information about all registered tools."""
        active_tool_names = {tool.name for tool in self.get_available_tools()}
        return [
            {
                "name": name,
                "description": getattr(tool, 'description', 'No description available'),
                "active": name in active_tool_names,
            }
            for name, tool in list(self._tools.items())
        ]
