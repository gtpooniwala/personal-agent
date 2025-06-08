from fastapi import APIRouter, HTTPException
from agent import PersonalAgent
from api.models import (
    ChatRequest, ChatResponse, ConversationCreate, ConversationResponse,
    MessageResponse, ToolInfo, HealthResponse
)
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize personal agent
agent = PersonalAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message through the LangChain agent."""
    try:
        conversation_id = request.conversation_id
        
        # Create new conversation if not provided
        if not conversation_id:
            conversation_id = agent.create_conversation()
        
        # Process message with agent
        result = await agent.process_message(request.message, conversation_id)
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations():
    """Get all conversations for the user."""
    try:
        conversations = agent.get_conversations()
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    try:
        conversation_id = agent.create_conversation(request.title)
        
        # Get the created conversation details
        conversations = agent.get_conversations()
        conversation = next((c for c in conversations if c["id"] == conversation_id), None)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Failed to create conversation")
        
        return ConversationResponse(**conversation)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(conversation_id: str):
    """Get messages for a specific conversation."""
    try:
        messages = agent.get_conversation_history(conversation_id)
        return [MessageResponse(**msg) for msg in messages]
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools():
    """Get list of available tools."""
    try:
        tools = agent.get_available_tools()
        return [ToolInfo(**tool) for tool in tools]
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )
