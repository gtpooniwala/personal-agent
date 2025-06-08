#!/usr/bin/env python3
"""
Test script to verify title generation works end-to-end
"""
import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def test_title_generation():
    print("🧪 Testing Title Generation System")
    print("=" * 50)
    
    try:
        # 1. Create new conversation
        print("1. Creating new conversation...")
        response = requests.post(f"{API_BASE}/conversations", 
                               json={"title": "Test Conversation"})
        response.raise_for_status()
        conversation = response.json()
        conversation_id = conversation["id"]
        print(f"   ✅ Created conversation: {conversation_id}")
        print(f"   📝 Initial title: '{conversation['title']}'")
        
        # 2. Send multiple messages
        messages = [
            "What is machine learning and how does it work?",
            "Can you explain the difference between supervised and unsupervised learning?",
            "What are some practical applications of machine learning in everyday life?"
        ]
        
        print(f"\n2. Sending {len(messages)} messages...")
        for i, message in enumerate(messages, 1):
            print(f"   Sending message {i}: '{message[:50]}...'")
            response = requests.post(f"{API_BASE}/chat", 
                                   json={
                                       "message": message,
                                       "conversation_id": conversation_id
                                   })
            response.raise_for_status()
            result = response.json()
            print(f"   ✅ Response received (conversation_id: {result['conversation_id']})")
            time.sleep(0.5)  # Small delay between messages
        
        # 3. Test title generation
        print(f"\n3. Generating title for conversation...")
        response = requests.post(f"{API_BASE}/conversations/{conversation_id}/generate-title")
        response.raise_for_status()
        title_result = response.json()
        generated_title = title_result["title"]
        print(f"   ✅ Generated title: '{generated_title}'")
        
        # 4. Verify title was saved
        print(f"\n4. Verifying title was saved...")
        response = requests.get(f"{API_BASE}/conversations")
        response.raise_for_status()
        conversations = response.json()
        
        updated_conv = next((c for c in conversations if c["id"] == conversation_id), None)
        if updated_conv:
            current_title = updated_conv["title"]
            message_count = updated_conv["message_count"]
            print(f"   📊 Current title: '{current_title}'")
            print(f"   📊 Message count: {message_count}")
            
            if current_title == generated_title:
                print(f"   ✅ SUCCESS: Title was updated correctly!")
            else:
                print(f"   ❌ FAILED: Title mismatch!")
                print(f"      Expected: '{generated_title}'")
                print(f"      Actual: '{current_title}'")
        else:
            print(f"   ❌ FAILED: Could not find conversation after update")
            
        print(f"\n🎯 Test Summary:")
        print(f"   - Conversation ID: {conversation_id}")
        print(f"   - Messages sent: {len(messages)}")
        print(f"   - Generated title: '{generated_title}'")
        print(f"   - Title saved: {'✅' if current_title == generated_title else '❌'}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_title_generation()
