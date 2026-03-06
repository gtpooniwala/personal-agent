"""
Document processing service for PDF text extraction and chunking.
"""

import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from pypdf import PdfReader
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.database.models import Document, DocumentChunk
from backend.database.operations import db_ops
from backend.llm import (
    create_chat_model,
    create_embeddings_model,
    predict_text,
    MissingProviderKeyError,
    MissingModelDependencyError,
)

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Service for processing PDF documents and managing embeddings."""
    
    def __init__(self):
        self.embeddings = None
        self.llm = None
        self.initialization_error: Optional[str] = None
        try:
            self.embeddings = create_embeddings_model()
            self.llm = create_chat_model(
                "document_qa",
                temperature=0.1,
                max_tokens=150,  # For concise summaries
            )
        except (MissingProviderKeyError, MissingModelDependencyError) as exc:
            self.initialization_error = str(exc)
            logger.warning(f"Document processor initialized without embeddings/LLM: {self.initialization_error}")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        self.upload_dir = Path("data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _require_embeddings_model(self) -> None:
        if self.embeddings is None:
            raise RuntimeError(
                self.initialization_error
                or "Document search requires configured embeddings."
            )

    def _require_processing_models(self) -> None:
        self._require_embeddings_model()
        if self.llm is None:
            raise RuntimeError(
                self.initialization_error
                or "Document processing requires a configured chat model."
            )
    
    async def process_pdf_upload(self, file_content: bytes, filename: str, user_id: str = "default") -> str:
        """
        Process uploaded PDF file and store document with embeddings.
        
        Args:
            file_content: PDF file content as bytes
            filename: Original filename
            user_id: User ID for document ownership
            
        Returns:
            str: Document ID
        """
        document_id: Optional[str] = None
        try:
            self._require_processing_models()
            # Generate unique filename and save file
            file_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix
            stored_filename = f"{file_id}{file_extension}"
            file_path = self.upload_dir / stored_filename
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Create document record
            session = db_ops.get_session()
            try:
                document = Document(
                    filename=stored_filename,
                    original_filename=filename,
                    file_size=len(file_content),
                    content_type="application/pdf",
                    user_id=user_id,
                    processed="processing"
                )
                session.add(document)
                session.commit()
                document_id = document.id
            finally:
                session.close()
            
            # Process document content
            await self._process_document_content(document_id, file_path)
            
            return document_id
            
        except Exception as e:
            logger.error(f"Error processing PDF upload: {str(e)}")
            # Update document status to failed
            if document_id:
                session = db_ops.get_session()
                try:
                    document = session.query(Document).filter(Document.id == document_id).first()
                    if document:
                        document.processed = "failed"
                        session.commit()
                except Exception:
                    pass
                finally:
                    session.close()
            raise
    
    async def _process_document_content(self, document_id: str, file_path: Path):
        """Extract text from PDF, generate summary, and create embeddings."""
        try:
            self._require_processing_models()
            # Extract text from PDF
            text_content = self._extract_pdf_text(file_path)
            
            # Generate document summary
            summary = await self._generate_document_summary(text_content)
            
            # Split text into chunks
            chunks = self.text_splitter.split_text(text_content)
            
            # Create embeddings for chunks
            embeddings_list = await self.embeddings.aembed_documents(chunks)
            
            # Store chunks with embeddings
            session = db_ops.get_session()
            try:
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings_list)):
                    # Convert embedding to bytes for storage
                    import pickle
                    embedding_bytes = pickle.dumps(embedding)
                    
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=i,
                        content=chunk_text,
                        embedding=embedding_bytes,
                        embedding_model=getattr(self.embeddings, "model", "configured-embedding-model")
                    )
                    session.add(chunk)
                
                # Update document status and summary
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processed = "completed"
                    document.total_chunks = len(chunks)
                    document.summary = summary
                
                session.commit()
                
            finally:
                session.close()
            
            logger.info(f"Successfully processed document {document_id} with {len(chunks)} chunks and summary: {summary}")
            
        except Exception as e:
            logger.error(f"Error processing document content: {str(e)}")
            # Update document status to failed
            session = db_ops.get_session()
            try:
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processed = "failed"
                    session.commit()
            finally:
                session.close()
            raise
    
    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text content from PDF file."""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(f"[Page {page_num + 1}]\n{page_text}")
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {str(e)}")
                        continue
            
            return "\n\n".join(text_content)
            
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise

    async def _generate_document_summary(self, text_content: str) -> str:
        """
        Generate a concise one-sentence summary of the document content.
        
        Args:
            text_content: Full text content of the document
            
        Returns:
            str: One-sentence summary of the document
        """
        try:
            # Truncate text if too long (to avoid token limits)
            max_chars = 8000  # Roughly 2000 tokens
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars] + "..."
            
            summary_prompt = f"""Analyze the following document content and generate a single, concise sentence that summarizes what this document is about. Focus on the main topic, purpose, or subject matter.

Document content:
{text_content}

Generate only one clear, informative sentence that captures the essence of this document. Do not include any additional text, quotes, or explanations.

Summary:"""
            summary = await predict_text(self.llm, summary_prompt)
            
            # Clean up the summary
            summary = summary.strip().strip('"\'').strip()
            
            # Ensure it's a single sentence
            if '.' in summary:
                summary = summary.split('.')[0] + '.'
            
            # Limit length
            if len(summary) > 200:
                summary = summary[:197] + "..."
            
            return summary
            
        except Exception as e:
            logger.warning(f"Error generating document summary: {str(e)}")
            return "Document content available for search"

    async def search_documents(self, query: str, user_id: str = "default", limit: int = 5, selected_documents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity.
        
        Args:
            query: Search query
            user_id: User ID for filtering documents
            limit: Maximum number of results
            selected_documents: List of document IDs to search within (None means search all)
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            self._require_embeddings_model()
            # Generate embedding for query
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Get all document chunks for user
            session = db_ops.get_session()
            try:
                # Build query with optional document filtering
                query_filter = session.query(DocumentChunk).join(Document).filter(
                    Document.user_id == user_id,
                    Document.processed == "completed"
                )
                
                # Filter by selected documents if provided
                if selected_documents:
                    query_filter = query_filter.filter(Document.id.in_(selected_documents))
                
                chunks = query_filter.all()
                
                if not chunks:
                    return []
                
                # Calculate similarities
                similarities = []
                import pickle
                import numpy as np
                
                for chunk in chunks:
                    if chunk.embedding:
                        chunk_embedding = pickle.loads(chunk.embedding)
                        # Calculate cosine similarity
                        similarity = np.dot(query_embedding, chunk_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                        )
                        similarities.append((chunk, similarity))
                
                # Sort by similarity and return top results
                similarities.sort(key=lambda x: x[1], reverse=True)
                
                results = []
                for chunk, similarity in similarities[:limit]:
                    document = session.query(Document).filter(Document.id == chunk.document_id).first()
                    results.append({
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_name": document.original_filename if document else "Unknown",
                        "content": chunk.content,
                        "similarity": float(similarity),
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number
                    })
                
                return results
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
    
    def search_documents_sync(self, query: str, user_id: str = "default", limit: int = 5, selected_documents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity (synchronous version).
        
        Args:
            query: Search query
            user_id: User ID for filtering documents
            limit: Maximum number of results
            selected_documents: List of document IDs to search within (None means search all)
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            self._require_embeddings_model()
            # Generate embedding for query (synchronous)
            query_embedding = self.embeddings.embed_query(query)
            
            # Get all document chunks for user
            session = db_ops.get_session()
            try:
                # Build query with optional document filtering
                query_filter = session.query(DocumentChunk).join(Document).filter(
                    Document.user_id == user_id,
                    Document.processed == "completed"
                )
                
                # Filter by selected documents if provided
                if selected_documents:
                    query_filter = query_filter.filter(Document.id.in_(selected_documents))
                
                chunks = query_filter.all()
                
                if not chunks:
                    return []
                
                # Calculate similarities
                similarities = []
                import pickle
                import numpy as np
                
                for chunk in chunks:
                    if chunk.embedding:
                        chunk_embedding = pickle.loads(chunk.embedding)
                        # Calculate cosine similarity
                        similarity = np.dot(query_embedding, chunk_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                        )
                        similarities.append((chunk, similarity))
                
                # Sort by similarity and return top results
                similarities.sort(key=lambda x: x[1], reverse=True)
                
                results = []
                for chunk, similarity in similarities[:limit]:
                    document = session.query(Document).filter(Document.id == chunk.document_id).first()
                    results.append({
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_name": document.original_filename if document else "Unknown",
                        "content": chunk.content,
                        "similarity": float(similarity),
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number
                    })
                
                return results
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error searching documents (sync): {str(e)}")
            return []

    def get_documents(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """Get all documents for a user."""
        session = db_ops.get_session()
        try:
            documents = session.query(Document).filter(Document.user_id == user_id).order_by(Document.upload_date.desc()).all()
            
            return [{
                "id": doc.id,
                "filename": doc.original_filename,
                "file_size": doc.file_size,
                "upload_date": doc.upload_date.isoformat(),
                "processed": doc.processed,
                "total_chunks": doc.total_chunks,
                "summary": doc.summary or "Document content available for search"
            } for doc in documents]
            
        finally:
            session.close()
    
    def delete_document(self, document_id: str, user_id: str = "default") -> bool:
        """Delete a document and its associated chunks."""
        session = db_ops.get_session()
        try:
            document = session.query(Document).filter(
                Document.id == document_id,
                Document.user_id == user_id
            ).first()
            
            if not document:
                return False
            
            # Delete file from disk
            try:
                file_path = self.upload_dir / document.filename
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"Error deleting file {document.filename}: {str(e)}")
            
            # Delete from database (chunks will be deleted via cascade)
            session.delete(document)
            session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return False
        finally:
            session.close()

    def get_document_context(self, user_id: str = "default", selected_documents: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get document context information for the orchestrator.
        
        Args:
            user_id: User ID for filtering documents
            selected_documents: List of document IDs to get context for (None means all user documents)
            
        Returns:
            Dict containing document summaries, counts, and metadata for orchestrator context
        """
        try:
            session = db_ops.get_session()
            try:
                # Build query for user documents
                query_filter = session.query(Document).filter(
                    Document.user_id == user_id,
                    Document.processed == "completed"
                )
                
                # Filter by selected documents if provided
                if selected_documents:
                    query_filter = query_filter.filter(Document.id.in_(selected_documents))
                
                documents = query_filter.all()
                
                if not documents:
                    return {
                        "has_documents": False,
                        "document_count": 0,
                        "total_chunks": 0,
                        "document_summaries": [],
                        "context_message": "No documents are currently available for search."
                    }
                
                # Collect document information
                document_summaries = []
                total_chunks = 0
                
                for doc in documents:
                    total_chunks += doc.total_chunks or 0
                    document_summaries.append({
                        "id": doc.id,
                        "filename": doc.original_filename,
                        "summary": doc.summary or "Document content available for search",
                        "chunks": doc.total_chunks or 0,
                        "upload_date": doc.upload_date.strftime("%Y-%m-%d") if doc.upload_date else "Unknown"
                    })
                
                # Create context message
                if len(documents) == 1:
                    context_message = f"📄 1 document available: '{documents[0].original_filename}' ({documents[0].total_chunks} searchable sections)"
                else:
                    context_message = f"📄 {len(documents)} documents available ({total_chunks} total searchable sections)"
                
                return {
                    "has_documents": True,
                    "document_count": len(documents),
                    "total_chunks": total_chunks,
                    "document_summaries": document_summaries,
                    "context_message": context_message
                }
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error getting document context: {str(e)}")
            return {
                "has_documents": False,
                "document_count": 0,
                "total_chunks": 0,
                "document_summaries": [],
                "context_message": "Error retrieving document information."
            }


# Global document processor instance
doc_processor = DocumentProcessor()
