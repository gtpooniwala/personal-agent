#!/usr/bin/env python3
"""
Final comprehensive test for the Document Q&A feature
"""
import requests
import json
import time

# Configuration
API_BASE = "http://127.0.0.1:8000/api/v1"
TEST_PDF = "test_document.pdf"

def comprehensive_test():
    """Run comprehensive end-to-end test"""
    print("🚀 FINAL COMPREHENSIVE TEST")
    print("=" * 60)
    
    results = []
    
    # Test 1: API Health
    print("1️⃣  Testing API Health...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy")
            results.append(True)
        else:
            print(f"❌ API health check failed: {response.status_code}")
            results.append(False)
    except Exception as e:
        print(f"❌ API health check error: {e}")
        results.append(False)
    
    # Test 2: Document Upload
    print("\n2️⃣  Testing Document Upload...")
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
    
    # Test 3: Document Processing (wait and verify)
    print("\n3️⃣  Testing Document Processing...")
    if document_id:
        try:
            response = requests.get(f"{API_BASE}/documents", timeout=10)
            if response.status_code == 200:
                docs = response.json()['documents']
                uploaded_doc = next((d for d in docs if d['id'] == document_id), None)
                
                if uploaded_doc and uploaded_doc['processed'] == 'completed':
                    print(f"✅ Document processed: {uploaded_doc['total_chunks']} chunks")
                    results.append(True)
                else:
                    print(f"❌ Document not processed: {uploaded_doc}")
                    results.append(False)
            else:
                print(f"❌ Failed to check processing status: {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"❌ Processing check error: {e}")
            results.append(False)
    else:
        print("❌ No document ID available")
        results.append(False)
    
    # Test 4: Document Q&A
    print("\n4️⃣  Testing Document Q&A...")
    try:
        # Create conversation
        conv_response = requests.post(f"{API_BASE}/conversations", json={}, timeout=10)
        if conv_response.status_code == 200:
            conversation_id = conv_response.json()['id']
            
            # Ask about the document
            chat_payload = {
                "message": "What are the key features of the Personal Agent mentioned in the document?",
                "conversation_id": conversation_id
            }
            
            chat_response = requests.post(f"{API_BASE}/chat", json=chat_payload, timeout=30)
            if chat_response.status_code == 200:
                chat_result = chat_response.json()
                
                # Check if document_qa tool was used
                tools_used = []
                if chat_result.get('agent_actions'):
                    tools_used = [action['tool'] for action in chat_result['agent_actions']]
                
                if 'document_qa' in tools_used:
                    print("✅ Document Q&A working successfully!")
                    print(f"💬 Response preview: {chat_result['response'][:150]}...")
                    results.append(True)
                else:
                    print(f"❌ Document Q&A tool not used. Tools: {tools_used}")
                    results.append(False)
            else:
                print(f"❌ Chat failed: {chat_response.status_code}")
                results.append(False)
        else:
            print(f"❌ Conversation creation failed: {conv_response.status_code}")
            results.append(False)
    except Exception as e:
        print(f"❌ Q&A test error: {e}")
        results.append(False)
    
    # Test 5: Complex Q&A
    print("\n5️⃣  Testing Complex Document Query...")
    try:
        if document_id:
            chat_payload = {
                "message": "Based on the uploaded document, what technical stack is used and what kind of calculations can the agent perform?",
                "conversation_id": conversation_id
            }
            
            chat_response = requests.post(f"{API_BASE}/chat", json=chat_payload, timeout=30)
            if chat_response.status_code == 200:
                chat_result = chat_response.json()
                response_text = chat_result.get('response', '').lower()
                
                # Check if response contains relevant information
                if any(term in response_text for term in ['technical', 'stack', 'calculation', 'mathematical']):
                    print("✅ Complex query answered correctly!")
                    results.append(True)
                else:
                    print(f"❌ Complex query response seems incomplete")
                    results.append(False)
            else:
                print(f"❌ Complex query failed: {chat_response.status_code}")
                results.append(False)
        else:
            print("❌ No document available for complex query")
            results.append(False)
    except Exception as e:
        print(f"❌ Complex query error: {e}")
        results.append(False)
    
    # Cleanup
    print("\n6️⃣  Cleaning up...")
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
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    test_names = [
        "API Health Check",
        "Document Upload", 
        "Document Processing",
        "Basic Document Q&A",
        "Complex Document Query"
    ]
    
    passed = sum(results)
    total = len(results)
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 DOCUMENT Q&A FEATURE IS FULLY FUNCTIONAL! 🎉")
        print("✨ Ready for production use!")
        print("\n🚀 Next Steps:")
        print("   • Use the frontend at http://localhost:8000")
        print("   • Upload PDF documents via drag & drop")
        print("   • Ask questions about your documents in the chat")
        print("   • Enjoy NotebookLM-style Q&A functionality!")
    else:
        print(f"\n⚠️  {total-passed} test(s) failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = comprehensive_test()
    exit(0 if success else 1)
