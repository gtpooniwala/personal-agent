"""
Document processing service for PDF text extraction and chunking.
"""

import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import PyPDF2
from io import BytesIO
import logging

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from database.models import Document, DocumentChunk
from database.operations import db_ops
from config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Service for processing PDF documents and managing embeddings."""
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.openai_api_key,
            model="text-embedding-ada-002"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        self.upload_dir = Path("data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
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
        try:
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
            session = db_ops.get_session()
            try:
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processed = "failed"
                    session.commit()
            except:
                pass
            finally:
                session.close()
            raise
    
    async def _process_document_content(self, document_id: str, file_path: Path):
        """Extract text from PDF and create embeddings."""
        try:
            # Extract text from PDF
            text_content = self._extract_pdf_text(file_path)
            
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
                        embedding_model="text-embedding-ada-002"
                    )
                    session.add(chunk)
                
                # Update document status
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processed = "completed"
                    document.total_chunks = len(chunks)
                
                session.commit()
                
            finally:
                session.close()
            
            logger.info(f"Successfully processed document {document_id} with {len(chunks)} chunks")
            
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
                pdf_reader = PyPDF2.PdfReader(file)
                
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
    
    async def search_documents(self, query: str, user_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity.
        
        Args:
            query: Search query
            user_id: User ID for filtering documents
            limit: Maximum number of results
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            # Generate embedding for query
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Get all document chunks for user
            session = db_ops.get_session()
            try:
                # Get chunks from completed documents only
                chunks = session.query(DocumentChunk).join(Document).filter(
                    Document.user_id == user_id,
                    Document.processed == "completed"
                ).all()
                
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
    
    def search_documents_sync(self, query: str, user_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity (synchronous version).
        
        Args:
            query: Search query
            user_id: User ID for filtering documents
            limit: Maximum number of results
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            # Generate embedding for query (synchronous)
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            
            response = client.embeddings.create(
                input=query,
                model="text-embedding-ada-002"
            )
            query_embedding = response.data[0].embedding
            
            # Get all document chunks for user
            session = db_ops.get_session()
            try:
                # Get chunks from completed documents only
                chunks = session.query(DocumentChunk).join(Document).filter(
                    Document.user_id == user_id,
                    Document.processed == "completed"
                ).all()
                
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
                "total_chunks": doc.total_chunks
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


# Global document processor instance
doc_processor = DocumentProcessor()
