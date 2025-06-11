#!/usr/bin/env python3
"""
Database migration to add summary column to documents table.
"""

import sqlite3
import os
from pathlib import Path
from backend.database.operations import db_ops
from backend.database.models import Document

def add_summary_column():
    """Add summary column to documents table."""
    
    # Database paths to check
    db_paths = [
        "data/agent.db",
        "backend/data/agent.db"
    ]
    
    success_count = 0
    
    for db_path in db_paths:
        if not os.path.exists(db_path):
            print(f"⚠️  Database not found: {db_path}")
            continue
            
        print(f"🔄 Processing database: {db_path}")
        
        try:
            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if summary column already exists
            cursor.execute("PRAGMA table_info(documents)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'summary' in columns:
                print(f"✅ Summary column already exists in {db_path}")
                success_count += 1
                continue
            
            # Add summary column
            cursor.execute("""
                ALTER TABLE documents 
                ADD COLUMN summary TEXT
            """)
            
            conn.commit()
            print(f"✅ Successfully added summary column to {db_path}")
            
            # Verify the column was added
            cursor.execute("PRAGMA table_info(documents)")
            new_columns = [row[1] for row in cursor.fetchall()]
            
            if 'summary' in new_columns:
                print(f"✅ Migration verified for {db_path}")
                success_count += 1
            else:
                print(f"❌ Migration failed for {db_path}")
                
        except Exception as e:
            print(f"❌ Error migrating {db_path}: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()
    
    return success_count > 0

if __name__ == "__main__":
    print("🔄 Running database migration to add summary column...")
    success = add_summary_column()
    
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        exit(1)
