from langchain.tools import BaseTool
from typing import Dict, List, Type, Any, Optional
from datetime import datetime
import math
import asyncio
import logging

logger = logging.getLogger(__name__)


class CalculatorTool(BaseTool):
    """Calculator tool for mathematical calculations only."""
    
    name = "calculator"
    description = "ALWAYS use this tool for ANY mathematical calculations, arithmetic, or numeric problems. Input should be a mathematical expression like '2+3', '10*5', '2**4'. NEVER do mental math - ALWAYS use this tool for numbers. Do NOT use for simple greetings, general conversation, or non-mathematical questions."
    
    def _run(self, query: str) -> str:
        """Execute the calculator tool."""
        try:
            # Replace ^ with ** for exponentiation
            query = query.replace('^', '**')
            
            # Simple safety check for basic math expressions
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in query):
                return "Error: Invalid characters in mathematical expression"
            
            # Evaluate the expression
            result = eval(query)
            return f"The result is: {result}"
        except Exception as e:
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool."""
        return self._run(query)


class CurrentTimeTool(BaseTool):
    """Tool to get current date and time information only."""
    
    name = "current_time"
    description = "Use ONLY when explicitly asked about current time, date, or timestamps. Examples: 'what time is it', 'what's the date', 'current time'. Do NOT use for greetings or general conversation. Input: use 'now'."
    
    def _run(self, query: str = "now") -> str:
        """Get current time."""
        now = datetime.now()
        return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    async def _arun(self, query: str = "now") -> str:
        """Async version of the tool."""
        return self._run(query)


class BaseServiceTool(BaseTool):
    """Base class for future service integration tools."""
    
    def __init__(self, user_id: str = "default"):
        super().__init__()
        # Store user_id as a private attribute to avoid Pydantic field issues
        self._user_id = user_id
    
    def _run(self, query: str) -> str:
        """Base implementation to be overridden."""
        raise NotImplementedError("Service tools must implement _run method")
    
    async def _arun(self, query: str) -> str:
        """Base async implementation."""
        return self._run(query)


# Placeholder tools for future implementation
class GmailTool(BaseTool):
    """Gmail integration tool - placeholder for future implementation."""
    
    name = "gmail_search"
    description = "Search and read Gmail emails. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Gmail integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class CalendarTool(BaseTool):
    """Google Calendar integration tool - placeholder for future implementation."""
    
    name = "calendar_events"
    description = "Get calendar events and schedule meetings. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Calendar integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class TodoistTool(BaseTool):
    """Todoist integration tool - placeholder for future implementation."""
    
    name = "todoist_tasks"
    description = "Manage tasks with Todoist. Currently not implemented."
    
    def _run(self, query: str) -> str:
        return "Todoist integration is not yet implemented. This is a placeholder for future development."
    
    async def _arun(self, query: str) -> str:
        return self._run(query)


class DocumentQATool(BaseTool):
    """Tool for answering questions about uploaded documents using RAG."""
    
    name = "document_qa"
    description = "Answer questions about uploaded documents. Use this when users ask about document content, want to search documents, or need information from their uploaded PDFs."
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, '_user_id', user_id)
        object.__setattr__(self, '_selected_documents', selected_documents or [])
    
    def _run(self, query: str) -> str:
        """Search documents and provide answers based on content."""
        try:
            # Check if any documents are selected
            if len(self._selected_documents) == 0:
                return "No documents are currently selected for search. Please select documents in the sidebar to enable document Q&A functionality."
            
            # Import here to avoid circular imports
            from services.document_service import doc_processor
            
            # Use the synchronous version to avoid event loop conflicts
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            results = doc_processor.search_documents_sync(
                query, 
                self._user_id, 
                limit=3, 
                selected_documents=selected_docs
            )
            
            if not results:
                return f"I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s). The query might not be related to the document content, or the documents may still be processing."
            
            # Format response with relevant document excerpts
            response_parts = ["Based on your uploaded documents, here's what I found:\n"]
            
            for i, result in enumerate(results, 1):
                similarity_score = result.get('similarity', 0)
                if similarity_score > 0.7:  # High relevance
                    relevance = "highly relevant"
                elif similarity_score > 0.5:  # Medium relevance
                    relevance = "moderately relevant"
                else:
                    relevance = "somewhat relevant"
                
                response_parts.append(
                    f"**{i}. From '{result['document_name']}' (chunk {result['chunk_index'] + 1}) - {relevance}:**\n"
                    f"{result['content'][:500]}{'...' if len(result['content']) > 500 else ''}\n"
                )
            
            response_parts.append(
                f"\n*Found {len(results)} relevant passages. "
                f"The information comes from {len(set(r['document_name'] for r in results))} document(s).*"
            )
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error in document Q&A: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool."""
        try:
            # Check if any documents are selected
            if len(self._selected_documents) == 0:
                return "No documents are currently selected for search. Please select documents in the sidebar to enable document Q&A functionality."
            
            from services.document_service import doc_processor
            
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            results = await doc_processor.search_documents(
                query, 
                self._user_id, 
                limit=3,
                selected_documents=selected_docs
            )
            
            if not results:
                return f"I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s). The query might not be related to the document content, or the documents may still be processing."
            
            # Format response with relevant document excerpts
            response_parts = ["Based on your uploaded documents, here's what I found:\n"]
            
            for i, result in enumerate(results, 1):
                similarity_score = result.get('similarity', 0)
                if similarity_score > 0.7:  # High relevance
                    relevance = "highly relevant"
                elif similarity_score > 0.5:  # Medium relevance
                    relevance = "moderately relevant"
                else:
                    relevance = "somewhat relevant"
                
                response_parts.append(
                    f"**{i}. From '{result['document_name']}' (chunk {result['chunk_index'] + 1}) - {relevance}:**\n"
                    f"{result['content'][:500]}{'...' if len(result['content']) > 500 else ''}\n"
                )
            
            response_parts.append(
                f"\n*Found {len(results)} relevant passages. "
                f"The information comes from {len(set(r['document_name'] for r in results))} document(s).*"
            )
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error in document Q&A: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}"


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        self.user_id = user_id
        self.selected_documents = selected_documents or []
        self._tools = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize available tools."""
        # MVP tools that work
        self._tools["calculator"] = CalculatorTool()
        self._tools["current_time"] = CurrentTimeTool()
        
        # Document Q&A tool with user context and selected documents
        self._tools["document_qa"] = DocumentQATool(self.user_id, self.selected_documents)
        
        # Placeholder tools for future implementation (no user_id needed for now)
        self._tools["gmail"] = GmailTool()
        self._tools["calendar"] = CalendarTool()
        self._tools["todoist"] = TodoistTool()
    
    def update_selected_documents(self, selected_documents: List[str]):
        """Update selected documents and reinitialize document QA tool."""
        self.selected_documents = selected_documents
        self._tools["document_qa"] = DocumentQATool(self.user_id, self.selected_documents)
    
    def get_available_tools(self) -> List[BaseTool]:
        """Get list of available tools for the agent."""
        # Always include basic tools
        working_tools = ["calculator", "current_time"]
        
        # Only include document Q&A if documents are selected
        if len(self.selected_documents) > 0:
            working_tools.append("document_qa")
        
        return [self._tools[tool_name] for tool_name in working_tools]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all tools including placeholders."""
        return list(self._tools.values())
    
    def add_tool(self, name: str, tool: BaseTool):
        """Add a new tool to the registry."""
        self._tools[name] = tool
    
    def get_tool(self, name: str) -> BaseTool:
        """Get a specific tool by name."""
        return self._tools.get(name)
