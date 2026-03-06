from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, List, Type
import logging

logger = logging.getLogger(__name__)


class SearchDocumentsInput(BaseModel):
    """Structured input for searching user-uploaded documents.
    
    Fields:
        query (str): The question or search query about the uploaded documents.
        max_results (int): Maximum number of document chunks to retrieve (1-5).
    """
    
    query: str = Field(
        description="The question or search query about the uploaded documents. Should be clear and specific."
    )
    
    max_results: Optional[int] = Field(
        default=3,
        description="Maximum number of document chunks to retrieve (1-5). Use more for complex queries that may need multiple sources."
    )


class SearchDocumentsTool(BaseTool):
    """
    Tool: search_documents
    Purpose: Answer questions or retrieve information from ALL user-selected documents using semantic search (RAG).
    
    Features:
    - Semantic search (RAG) over all selected documents
    - File summaries to help decide if a search is worthwhile
    - Used for any query that may be answered by uploaded documents
    - Not used for general knowledge, math, or time queries

    When to use:
    - Use this tool whenever you think relevant information may be found in the user's uploaded or selected documents, even if the user does not explicitly mention them.
    - The tool will search through ALL selected documents to find the answer.
    - File summaries are available to help you decide if a search is worthwhile.
    - Do not use for general knowledge, math, time, or conversation unless you believe the answer may be in the documents.

    Example triggers:
    - "What does my contract say about termination?"
    - "Search my uploaded files for pricing information."
    - "Summarize my selected documents."
    - "Find AI references in my PDFs."
    - "What is the project deadline?" (if you think it may be in the docs)

    Example non-triggers:
    - "Hi", "Hello", "How are you?", "What can you do?", "What's the weather?"
    - Any question where you are confident the answer is not in the user's documents.
    """
    
    name: str = "search_documents"
    description: str = (
        "Answer questions or retrieve information from user-uploaded documents. "
        "Use this tool whenever you think relevant information may be found in the user's uploaded or selected documents. "
        "Explicitly use this tool if you think relevant information may be in one of the included files, or if the user asks about the uploaded file(s). "
        "File summaries are available to help you decide if a search is worthwhile. "
        "Do not use for general knowledge, math, time, or conversation unless you believe the answer may be in the documents. "
        "Examples: 'What does my contract say?', 'Find pricing info in my files', 'Summarize my uploaded documents', 'What is the project deadline?'"
    )
    
    args_schema: Type[BaseModel] = SearchDocumentsInput
    
    def __init__(self, user_id: str = "default", selected_documents: Optional[List[str]] = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation for internal attributes
        object.__setattr__(self, '_user_id', user_id)
        object.__setattr__(self, '_selected_documents', selected_documents or [])
    
    def _format_document_summaries(self, documents):
        if not documents:
            return "No documents are available."
        summary_lines = ["\n---\n**Here is a list of all Documents available and their Summaries:**"]
        for doc in documents:
            summary = doc.get("summary") or "No summary available."
            summary_lines.append(f"- **{doc.get('filename', 'Untitled')}**: {summary}")
        return "\n".join(summary_lines)

    def _run(self, query: str, max_results: int = 3) -> str:
        """
        Search ALL selected documents and provide answers based on content.
        
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
                return "No documents are currently selected. Please select one or more documents to enable document search."
            
            # Import here to avoid circular imports
            from backend.services.document_service import doc_processor
            if getattr(doc_processor, "initialization_error", None):
                return doc_processor.initialization_error
            
            # Perform document search with dynamic chunk limit
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            search_results = doc_processor.search_documents_sync(
                query, 
                self._user_id, 
                limit=max_results, 
                selected_documents=selected_docs
            )
            
            # Append all available document summaries 
            all_docs = doc_processor.get_documents(self._user_id)
            response = self._format_document_summaries(all_docs)
            if not search_results:
                response += f"""I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s) for your query: \"{query}\"\n\nThis could mean:\n- The information isn't in the selected documents\n- The documents are still being processed\n- Try rephrasing your question with different keywords\n\nYou can try asking about different topics or selecting different documents."""
            else:
                # Format response with relevant document excerpts
                response_parts = ["Based on your the uploaded documents, here's what I found relevant to the query:\n"]
                
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
                
                response += "\n".join(response_parts)

            logger.info(f"Document Q&A tool found {len(search_results) if search_results else 0} results for query: {query} (max_results: {max_results})")
            return response
        except Exception as e:
            logger.error(f"Error in search documents tool: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}\n\nPlease try again or contact support if the issue persists."
    
    async def _arun(self, query: str) -> str:
        """
        Async version of the document search tool. Searches ALL selected documents for relevant information.
        
        This version uses the async document service for better performance
        in async contexts.
        """
        try:
            # Check if any documents are selected
            if len(self._selected_documents) == 0:
                return "No documents are currently selected. Please select one or more documents to enable document search."
            
            from backend.services.document_service import doc_processor
            if getattr(doc_processor, "initialization_error", None):
                return doc_processor.initialization_error
            
            # Perform async document search
            selected_docs = self._selected_documents if len(self._selected_documents) > 0 else None
            search_results = await doc_processor.search_documents(
                query, 
                self._user_id, 
                limit=3,
                selected_documents=selected_docs
            )
            
            if not search_results:
                response = f"""I couldn't find any relevant information in the {len(self._selected_documents)} selected document(s) for your query: \"{query}\"\n\nThis could mean:\n- The information isn't in the selected documents\n- The documents are still being processed\n- Try rephrasing your question with different keywords\n\nYou can try asking about different topics or selecting different documents."""
            else:
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
                
                response = "\n".join(response_parts)
            # Append all available document summaries (sync call is fine for metadata)
            all_docs = doc_processor.get_documents(self._user_id)
            response += self._format_document_summaries(all_docs)
            logger.info(f"Document Q&A tool found {len(search_results) if search_results else 0} results for query: {query}")
            return response
        except Exception as e:
            logger.error(f"Error in search documents tool: {str(e)}")
            return f"I encountered an error while searching your documents: {str(e)}\n\nPlease try again or contact support if the issue persists."
