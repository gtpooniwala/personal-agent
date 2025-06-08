#!/usr/bin/env python3
"""
Test script for document Q&A functionality
"""
import sys
import os
import asyncio
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

async def test_document_qa():
    """Test the document Q&A functionality"""
    try:
        # Import after adding to path
        from services.document_service import DocumentService
        from database.operations import DatabaseOperations
        
        print("🔧 Initializing services...")
        doc_service = DocumentService()
        db_ops = DatabaseOperations()
        
        # Test file path
        test_pdf = backend_dir / "test_document.pdf"
        
        if not test_pdf.exists():
            print(f"❌ Test PDF not found at {test_pdf}")
            return False
            
        print(f"📄 Testing with PDF: {test_pdf}")
        
        # Test document upload
        print("\n📤 Testing document upload...")
        try:
            with open(test_pdf, "rb") as f:
                class MockFile:
                    def __init__(self, file_obj, filename):
                        self.file = file_obj
                        self.filename = filename
                        self.content_type = "application/pdf"
                        
                    async def read(self):
                        return self.file.read()
                
                mock_file = MockFile(f, "test_document.pdf")
                result = await doc_service.upload_document(mock_file, "test_user")
                print(f"✅ Upload successful: {result}")
                document_id = result["document_id"]
                
        except Exception as e:
            print(f"❌ Upload failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test document listing
        print("\n📋 Testing document listing...")
        try:
            documents = await doc_service.list_documents("test_user")
            print(f"✅ Found {len(documents)} documents")
            for doc in documents:
                print(f"   - {doc['filename']} ({doc['file_size']} bytes)")
        except Exception as e:
            print(f"❌ Listing failed: {str(e)}")
            return False
        
        # Test document search
        print("\n🔍 Testing document search...")
        try:
            test_queries = [
                "What is the Personal Agent?",
                "What features does it have?",
                "Tell me about document Q&A",
                "What mathematical operations are supported?"
            ]
            
            for query in test_queries:
                print(f"\n   Query: '{query}'")
                results = await doc_service.search_documents(query, "test_user", top_k=3)
                if results:
                    print(f"   ✅ Found {len(results)} relevant chunks")
                    for i, result in enumerate(results, 1):
                        print(f"      {i}. Score: {result['score']:.3f}")
                        print(f"         Text: {result['text'][:100]}...")
                else:
                    print("   ⚠️ No results found")
        except Exception as e:
            print(f"❌ Search failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test document Q&A tool
        print("\n🤖 Testing DocumentQA Tool...")
        try:
            from agent.tools import DocumentQATool
            
            tool = DocumentQATool()
            tool._user_id = "test_user"
            
            test_question = "What is the Personal Agent and what can it do?"
            print(f"   Question: '{test_question}'")
            
            answer = tool._run(test_question)
            print(f"   ✅ Answer: {answer[:200]}...")
            
        except Exception as e:
            print(f"❌ DocumentQA Tool failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        try:
            await doc_service.delete_document(document_id, "test_user")
            print("✅ Cleanup successful")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {str(e)}")
        
        print("\n🎉 All tests passed! Document Q&A feature is working correctly.")
        return True
        
    except Exception as e:
        print(f"💥 Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Document Q&A Feature")
    print("=" * 50)
    
    # Run the async test
    success = asyncio.run(test_document_qa())
    
    if success:
        print("\n✅ Document Q&A feature is ready for production!")
        print("🚀 You can now:")
        print("   1. Start the server: uvicorn main:app --reload --port 8000")
        print("   2. Open frontend: http://localhost:8000 (if serving frontend)")
        print("   3. Upload PDFs and ask questions!")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
    
    sys.exit(0 if success else 1)
