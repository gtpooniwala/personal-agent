# Document Upload and AI Summary System

## Overview

The Personal Agent now features an advanced document upload system that automatically processes documents and provides intelligent context to the AI assistant.

## Features

### 📄 **Automatic Document Summarization**
- When a document is uploaded, the system automatically generates a concise one-sentence summary
- Summaries help the AI understand document content at a glance
- Stored in the database for quick reference

### 🔍 **Smart Document Context**
- AI assistant is automatically informed about available documents
- System provides document summaries and chunk counts in the AI's context
- Dynamic prompting based on document availability

### ⚡ **Dynamic Search Results**
- The `search_documents` tool honors `max_results` in both sync and async execution paths
- Requests are clamped to 1-5 results before calling document search
- AI can choose how many chunks to retrieve based on query complexity
- Optimized for both simple and complex queries

### 🎯 **Context-Aware AI Behavior**
- When documents are available: AI proactively uses document search
- When no documents available: AI explains that documents need to be uploaded first
- Clear distinction between document search and general note-taking

## Architecture

### Database Schema
```sql
-- Enhanced Document table with summary column
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    content_type TEXT DEFAULT 'application/pdf',
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT DEFAULT 'default',
    processed TEXT DEFAULT 'pending',
    total_chunks INTEGER DEFAULT 0,
    summary TEXT,  -- AI-generated document summary
    -- ... other fields
);
```

### Document Processing Pipeline
1. **Upload** → File saved to storage
2. **Text Extraction** → PDF content extracted
3. **Summary Generation** → AI creates one-sentence summary
4. **Chunking** → Text split into searchable chunks
5. **Embedding** → Vector embeddings generated
6. **Storage** → Chunks and metadata saved to database

### AI Context Integration
- System checks available documents before each request
- Context section dynamically inserted into AI prompt
- Document summaries and chunk counts provided
- AI behavior adapts based on document availability

## API Changes

### Document Service Enhancements
```python
# New method for getting document context
doc_processor.get_document_context(user_id, selected_documents)

# Enhanced search with dynamic results
doc_processor.search_documents(query, user_id, limit=max_results, selected_documents)
```

### Document QA Tool Updates
```python
# The tool contract supports dynamic chunk selection in both sync and async use
SearchDocumentsInput(
    query="What are the key points?",
    max_results=3  # 1-5 chunks based on complexity
)
```

## Usage Examples

### For Users
1. **Upload a document** → System automatically processes and summarizes
2. **Ask questions** → AI searches through document content
3. **Complex queries** → AI retrieves more chunks for comprehensive answers
4. **No documents** → AI clearly explains next steps

### For Developers
```python
# Check document context
context = doc_processor.get_document_context(user_id)
print(f"Documents available: {context['document_count']}")
print(f"Context: {context['context_message']}")

# Search with dynamic results
results = await doc_processor.search_documents(
    query="pricing information",
    limit=5,  # More results for complex query
    selected_documents=selected_doc_ids
)
```

## Benefits

### 🚀 **Improved User Experience**
- Clear understanding of document availability
- Automatic summarization saves time
- Context-aware responses

### 🎯 **Better AI Performance**
- Dynamic result selection optimizes relevance
- Clear context prevents tool misuse
- Improved response accuracy

### 📈 **Scalable Architecture**
- Efficient document processing pipeline
- Optimized vector search
- Clean separation of concerns

## Migration

The system includes automatic database migration for existing installations:

```bash
# Run migration to add summary column
python backend/migrate_add_summary.py
```

## Testing

Document functionality is covered by comprehensive tests:

```bash
# Run full test suite
python tests/test_comprehensive.py

# Current success rate: 95.5% (21/22 tests passing)
```

## Future Enhancements

- **Multi-format support** (Word, Excel, PowerPoint)
- **Document versioning** and change tracking
- **Advanced summarization** with key topics extraction
- **Document relationships** and cross-references
- **Collaborative document sharing**
