#!/usr/bin/env python3
"""
Test script for selective RAG functionality
"""
import requests
import json
import time

# Configuration
API_BASE = "http://127.0.0.1:8000/api/v1"
TEST_PDF = "test_document.pdf"

def test_selective_rag():
    """Test selective RAG with document selection"""
    print("🔍 SELECTIVE RAG TEST")
    print("=" * 50)
    
    results = []
    
    # Test 1: Upload a document
    print("1️⃣  Uploading test document...")
    document_id = None
    try:
        with open(TEST_PDF, 'rb') as f:
            files = {'file': (TEST_PDF, f, 'application/pdf')}
            response = requests.post(f"{API_BASE}/documents/upload", files=files, timeout=30)
            
        if response.status_code == 200:
            upload_result = response.json()
            document_id = upload_result['document_id']
            print(f"✅ Document uploaded: {document_id}")
            results.append(True)
        else:
            print(f"❌ Upload failed: {response.status_code}")
            results.append(False)
    except Exception as e:
        print(f"❌ Upload error: {e}")
        results.append(False)
    
    # Wait for processing
    time.sleep(2)
    
    # Test 2: Test Q&A with selected documents
    print("\n2️⃣  Testing Q&A with selected documents...")
    try:
        # Create conversation
        conv_response = requests.post(f"{API_BASE}/conversations", json={}, timeout=10)
        if conv_response.status_code == 200:
            conversation_id = conv_response.json()['id']
            
            # Test with selected documents
            chat_payload = {
                "message": "What are the key features mentioned in the document?",
                "conversation_id": conversation_id,
                "selected_documents": [document_id] if document_id else []
            }
            
            chat_response = requests.post(f"{API_BASE}/chat", json=chat_payload, timeout=30)
            if chat_response.status_code == 200:
                chat_result = chat_response.json()
                print("✅ Q&A with selected documents successful!")
                print(f"💬 Response preview: {chat_result['response'][:100]}...")
                results.append(True)
            else:
                print(f"❌ Chat with selected docs failed: {chat_response.status_code}")
                results.append(False)
        else:
            print(f"❌ Conversation creation failed: {conv_response.status_code}")
            results.append(False)
    except Exception as e:
        print(f"❌ Selected documents test error: {e}")
        results.append(False)
    
    # Test 3: Test Q&A with no selected documents
    print("\n3️⃣  Testing Q&A with no selected documents...")
    try:
        chat_payload = {
            "message": "What can you tell me about the documents?",
            "conversation_id": conversation_id,
            "selected_documents": []
        }
        
        chat_response = requests.post(f"{API_BASE}/chat", json=chat_payload, timeout=30)
        if chat_response.status_code == 200:
            chat_result = chat_response.json()
            print("✅ Q&A with no selected documents successful!")
            print(f"💬 Response preview: {chat_result['response'][:100]}...")
            results.append(True)
        else:
            print(f"❌ Chat with no selected docs failed: {chat_response.status_code}")
            results.append(False)
    except Exception as e:
        print(f"❌ No selected documents test error: {e}")
        results.append(False)
    
    # Cleanup
    print("\n4️⃣  Cleaning up...")
    if document_id:
        try:
            response = requests.delete(f"{API_BASE}/documents/{document_id}", timeout=10)
            if response.status_code == 200:
                print("✅ Document cleaned up successfully")
            else:
                print(f"⚠️  Cleanup warning: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    # Results Summary
    print("\n" + "=" * 50)
    print("📊 SELECTIVE RAG TEST RESULTS")
    print("=" * 50)
    
    test_names = [
        "Document Upload",
        "Q&A with Selected Documents", 
        "Q&A with No Selected Documents"
    ]
    
    passed = sum(results)
    total = len(results)
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 SELECTIVE RAG FUNCTIONALITY IS WORKING! 🎉")
    else:
        print(f"\n⚠️  {total-passed} test(s) failed.")
    
    return passed == total

if __name__ == "__main__":
    success = test_selective_rag()
    exit(0 if success else 1)
