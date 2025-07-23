from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from database import get_db, User, Conversation
import json
import uuid
from agent_graph import process_query

# Create a router instead of using the app directly - then you can group related endpoints, then mount them in main.py
router = APIRouter(prefix="/chat", tags=["chat"])

# Define a Pydantic model for the request / response (including thread_id for continuity)
class ChatRequest(BaseModel):
    request: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str

# Adding pydantic model for conversation response
class ConversationResponse(BaseModel):
    thread_id: str
    messages: List[dict]

# Define a function to handle the chat request
@router.post("", response_model=ChatResponse) # define the endpoint, define function, validate incoming data as a parameter to function
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        # Generate thread_id if not provided
        thread_id = request.thread_id or str(uuid.uuid4())

        # Get or create user (simplified, no auth)
        user = db.query(User).filter(User.email == "demo@example.com").first()
        if not user:
            user = User(email="demo@example.com")
            db.add(user)
            db.commit()
        
        # Get conversation history for this thread
        conversation = db.query(Conversation).filter(
            Conversation.user_id == user.id,
            Conversation.thread_id == thread_id
        ).first()

        # Build conversation history for agent
        conversation_history = []
        if conversation and conversation.messages:
            conversation_history = conversation.messages
        
        # Get agent response
        response_content = await process_query(
            user_query=request.request,
            conversation_history=conversation_history
        )

        # Update conversation history
        new_messages = conversation.messages if conversation else []
        new_messages.append({"role": "user", "content": request.request})
        new_messages.append({"role": "assistant", "content": response_content})

        if conversation:
            conversation.messages = new_messages
        else:
            conversation = Conversation(
                user_id=user.id,
                thread_id=thread_id,
                messages=new_messages
            )
            db.add(conversation)

        db.commit()

        # Now return the agent response to the user with the proper thread_id
        return ChatResponse(response=response_content, thread_id=thread_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint for conversation history
@router.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(thread_id: str, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(
        Conversation.thread_id == thread_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        thread_id=thread.id,
        messages=conversation.messages
    )

# New endpoint to list all conversations for a user
@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        return []
    
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user.id
    ).order_by(Conversation.updated_at.desc()).all()

    return[
        ConversationResponse(
            thread_id=conv.thread_id,
            messages=conv.messages
        ) for conv in conversations
    ]

# New endpoint to clear conversation
@router.delete("/conversations/{thread_id}")
async def delete_conversation(thread_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == :"demo@example.com").first()

    conversation = db.query(Conversation).filter(
        Conversation.user_id == user.id,
        Conversation.thread_id == thread_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted successfully"}