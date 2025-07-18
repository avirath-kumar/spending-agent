from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
import os
from sqlalchemy.orm import Session
from database import SessionLocal, User, Conversation
from typing import List
import json
import uuid

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Initialize langchain openai client
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define a Pydantic model for the request / response (including thread_id for continuity)
class ChatRequest(BaseModel):
    request: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str

# Define a function to handle the chat request
@app.post("/chat", response_model=ChatResponse) # define the endpoint

# define function, validate incoming data as a parameter to function
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

        # Build message history
        messages = []
        if conversation and conversation.messages:
            for msg in conversation.messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=request.request))

        # Get LLM response
        response = llm.invoke(messages)

        # Update conversation history
        new_messages = conversation.messages if conversation else []
        new_messages.append({"role": "user", "content": request.request})
        new_messages.append({"role": "assistant", "content": response.content})

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

        # Now return the llm response to the user with the proper thread_id
        return ChatResponse(response=response.content, thread_id=thread_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint for conversation history
@app.get("/conversations/{thread_id}")
async def get_conversation(thread_id: str, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(
        Conversation.thread_id == thread_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"thread_id": thread_id, "messages": conversation.messages}

# only run if script is executed directly, not imported
if __name__ == "__main__":
    import uvicorn
    
    # run app on port 8000, host 0.0.0.0 (all interfaces)
    uvicorn.run(app, host="0.0.0.0", port=8000)