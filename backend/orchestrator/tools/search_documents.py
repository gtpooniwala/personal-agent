from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class DocumentQAInput(BaseModel):
    """Input model for document Q&A tool - expects structured query from LLM."""
    
    query: str = Field(
        description="The question or search query about the uploaded documents. Should be clear and specific."
    )
    
    max_results: Optional[int] = Field(
        default=3,
        description="Maximum number of document chunks to retrieve (1-5). Use more for complex queries that may need multiple sources."
    )


class DocumentQATool(BaseTool):
    """
    Document Q&A tool/agent using RAG (Retrieval Augmented Generation).
    
    This is a sophisticated tool that enables users to query their uploaded documents.
    It uses vector search and semantic matching to find relevant content.
    
    Features:
    - Semantic search across uploaded documents
    - Context-aware responses based on document content
    - Multi-document search capabilities
    - Relevance scoring and filtering
    - Transparent source attribution
    """
    
    name = "search_documents"
    description = """Search through uploaded documents to find relevant information and answer questions.

Use this tool when users:
- Ask questions about their uploaded documents
- Want to search for specific information in documents
- Need summaries or explanations from document content
- Reference "my documents", "uploaded files", etc.

Examples:
- "What does my contract say about termination?"
- "Search my documents for information about pricing"
- "Find information about AI in my documents"
- "Summarize the key points from my uploaded report"

The tool searches through selected documents and provides relevant excerpts with source attribution."""
    
    args_schema = DocumentQAInput
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation for internal attributes
        object.__setattr__(self, '_user_id', user_id)
        object.__setattr__(self, '_selected_documents', selected_documents or [])
    
    def _run(self, query: str, max_results: int = 3) -> str:
        """
        Search documents and provide answers based on content.
        
        Args:
            query: The search query or question
            max_results: Maximum number of chunks to retrieve (1-5)
        
        This method:
        1. Checks if documents are available for search
        2. Performs semantic search across selected documents
        3. Ranks results by relevance
        4. Formats response with source attribution
        5. Provides helpful feedback if no results found
        """
        try:
            # Validate and clamp max_results
            max_results = max(1, min(5, max_results))
            
            # Check if any documents are selected for search
            if len(self._selected_documents) == 0:
                return """No documents are currently selected for search. 

To use document Q&A:
1. Upload documents using the upload feature
2. Select documents in the sidebar
3. Ask questions about the document content

The document Q&A tool will then search through your selected documents to find relevant information."""
            
            # Import here to avoid circular imports
            from services.document_service import doc_processor
            
            # Perform document search with dynamic chunk limit
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            search_results = doc_processor.search_documents_sync(
                query, 
                self._user_id, 
                limit=max_results, 
                selected_documents=selected_docs
            )
            
            if not search_results:
                return f"""I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s) for your query: "{query}"

This could mean:
- The information isn't in the selected documents
- The documents are still being processed
- Try rephrasing your question with different keywords

You can try asking about different topics or selecting different documents."""
            
            # Format response with relevant document excerpts
            response_parts = ["Based on your uploaded documents, here's what I found:\n"]
            
            for i, result in enumerate(search_results, 1):
                similarity_score = result.get('similarity', 0)
                
                # Determine relevance level
                if similarity_score > 0.7:
                    relevance = "highly relevant"
                elif similarity_score > 0.5:
                    relevance = "moderately relevant"
                else:
                    relevance = "somewhat relevant"
                
                # Format each result with clear source attribution
                content_preview = result['content'][:500]
                if len(result['content']) > 500:
                    content_preview += "..."
                
                response_parts.append(
                    f"**{i}. From '{result['document_name']}' (section {result['chunk_index'] + 1}) - {relevance}:**\n"
                    f"{content_preview}\n"
                )
            
            # Add summary footer
            unique_documents = len(set(r['document_name'] for r in search_results))
            response_parts.append(
                f"\n*Found {len(search_results)} relevant passages from {unique_documents} document(s). "
                f"Results ranked by relevance to your query.*"
            )
            
            logger.info(f"Document Q&A tool found {len(search_results)} results for query: {query} (max_results: {max_results})")
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error in document Q&A tool: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}\n\nPlease try again or contact support if the issue persists."
    
    async def _arun(self, query: str) -> str:
        """
        Async version of the document search tool.
        
        This version uses the async document service for better performance
        in async contexts.
        """
        try:
            # Check if any documents are selected
            if len(self._selected_documents) == 0:
                return """No documents are currently selected for search. 

To use document Q&A:
1. Upload documents using the upload feature
2. Select documents in the sidebar  
3. Ask questions about the document content

The document Q&A tool will then search through your selected documents to find relevant information."""
            
            from services.document_service import doc_processor
            
            # Perform async document search
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            search_results = await doc_processor.search_documents(
                query, 
                self._user_id, 
                limit=3,
                selected_documents=selected_docs
            )
            
            if not search_results:
                return f"""I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s) for your query: "{query}"

This could mean:
- The information isn't in the selected documents
- The documents are still being processed
- Try rephrasing your question with different keywords

You can try asking about different topics or selecting different documents."""
            
            # Format response with relevant document excerpts
            response_parts = ["Based on your uploaded documents, here's what I found:\n"]
            
            for i, result in enumerate(search_results, 1):
                similarity_score = result.get('similarity', 0)
                
                # Determine relevance level
                if similarity_score > 0.7:
                    relevance = "highly relevant"
                elif similarity_score > 0.5:
                    relevance = "moderately relevant"
                else:
                    relevance = "somewhat relevant"
                
                # Format each result with clear source attribution
                content_preview = result['content'][:500]
                if len(result['content']) > 500:
                    content_preview += "..."
                
                response_parts.append(
                    f"**{i}. From '{result['document_name']}' (section {result['chunk_index'] + 1}) - {relevance}:**\n"
                    f"{content_preview}\n"
                )
            
            # Add summary footer
            unique_documents = len(set(r['document_name'] for r in search_results))
            response_parts.append(
                f"\n*Found {len(search_results)} relevant passages from {unique_documents} document(s). "
                f"Results ranked by relevance to your query.*"
            )
            
            logger.info(f"Document Q&A tool found {len(search_results)} results for query: {query}")
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error in document Q&A tool: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}\n\nPlease try again or contact support if the issue persists."
