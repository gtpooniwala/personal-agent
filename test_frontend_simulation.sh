#!/bin/bash

# Test script to verify title generation works like the frontend should

API_BASE="http://localhost:8000/api/v1"
echo "🧪 Frontend Title Generation Test"
echo "=================================="

# 1. Create new conversation (simulating "New Chat" click)
echo "1. Creating new conversation..."
CONV_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
    $API_BASE/conversations -d '{"title": "New Conversation"}')
CONV_ID=$(echo $CONV_RESPONSE | jq -r '.id')
echo "   ✅ Created conversation: $CONV_ID"

# 2. Send messages (simulating user typing and sending)
echo "2. Sending messages to trigger title generation..."

echo "   📤 Sending message 1..."
MSG1_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
    $API_BASE/chat -d "{\"message\": \"What is machine learning?\", \"conversation_id\": \"$CONV_ID\"}")

echo "   📤 Sending message 2..."
MSG2_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
    $API_BASE/chat -d "{\"message\": \"Can you explain neural networks?\", \"conversation_id\": \"$CONV_ID\"}")

echo "   📤 Sending message 3..."
MSG3_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
    $API_BASE/chat -d "{\"message\": \"What are practical applications?\", \"conversation_id\": \"$CONV_ID\"}")

# 3. Check conversation status
echo "3. Checking conversation status..."
CONV_STATUS=$(curl -s $API_BASE/conversations | jq ".[] | select(.id == \"$CONV_ID\")")
MESSAGE_COUNT=$(echo $CONV_STATUS | jq -r '.message_count')
CURRENT_TITLE=$(echo $CONV_STATUS | jq -r '.title')

echo "   📊 Message count: $MESSAGE_COUNT"
echo "   📝 Current title: '$CURRENT_TITLE'"

# 4. Simulate frontend title generation (what should happen automatically)
if [ "$MESSAGE_COUNT" -ge 3 ]; then
    echo "4. Message count >= 3, simulating automatic title generation..."
    
    # Wait 1 second (like the frontend setTimeout)
    sleep 1
    
    # Call title generation API
    echo "   🔄 Calling title generation API..."
    TITLE_RESPONSE=$(curl -s -X POST $API_BASE/conversations/$CONV_ID/generate-title)
    GENERATED_TITLE=$(echo $TITLE_RESPONSE | jq -r '.title')
    
    echo "   ✅ Generated title: '$GENERATED_TITLE'"
    
    # Verify title was saved
    echo "5. Verifying title was saved..."
    UPDATED_CONV=$(curl -s $API_BASE/conversations | jq ".[] | select(.id == \"$CONV_ID\")")
    FINAL_TITLE=$(echo $UPDATED_CONV | jq -r '.title')
    
    if [ "$FINAL_TITLE" = "$GENERATED_TITLE" ]; then
        echo "   ✅ SUCCESS: Title was updated correctly!"
        echo "   🏆 Final title: '$FINAL_TITLE'"
    else
        echo "   ❌ FAILED: Title was not updated correctly"
        echo "   Expected: '$GENERATED_TITLE'"
        echo "   Actual: '$FINAL_TITLE'"
    fi
else
    echo "4. ❌ Not enough messages ($MESSAGE_COUNT < 3) for title generation"
fi

echo ""
echo "📋 Test Summary:"
echo "   - Conversation ID: $CONV_ID"
echo "   - Message count: $MESSAGE_COUNT"
echo "   - Final title: '$FINAL_TITLE'"
echo "   - Title generation: $([ "$FINAL_TITLE" != "New Conversation" ] && echo "✅ Working" || echo "❌ Not working")"
