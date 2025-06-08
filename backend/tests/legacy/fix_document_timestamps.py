#!/usr/bin/env python3
"""
Script to fix null upload_date timestamps in existing documents.
"""

from datetime import datetime
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.operations import db_ops
from database.models import Document

def fix_document_timestamps():
    """Fix documents with null upload_date timestamps."""
    session = db_ops.get_session()
    
    try:
        # Find documents with null upload_date
        documents_with_null_dates = session.query(Document).filter(Document.upload_date.is_(None)).all()
        
        print(f"Found {len(documents_with_null_dates)} documents with null upload_date")
        
        if not documents_with_null_dates:
            print("No documents need fixing.")
            return
        
        # Set current timestamp for documents with null upload_date
        current_time = datetime.utcnow()
        
        for doc in documents_with_null_dates:
            print(f"Fixing document: {doc.original_filename} (ID: {doc.id})")
            doc.upload_date = current_time
        
        session.commit()
        print(f"Successfully updated {len(documents_with_null_dates)} documents")
        
    except Exception as e:
        print(f"Error fixing document timestamps: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    fix_document_timestamps()
