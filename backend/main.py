from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Initialize langchain openai client
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# Define a Pydantic model for the request
class ChatRequest(BaseModel):
    request: str

# Define a Pydantic model for the response
class ChatResponse(BaseModel):
    response: str

# Define a function to handle the chat request
@app.post("/chat", response_model=ChatResponse) # define the endpoint

# define function, validate incoming data as a parameter to function
async def chat_endpoint(request: ChatRequest):
    try:
        # get message string from incoming request, wrap in langchain format, put in list
        messages = [HumanMessage(content=request.request)]
        
        # call llm with messages list
        response = llm.invoke(messages)
        
        # response.content gets content from langchain response object, validate with pydantic model
        return ChatResponse(response=response.content)

    # if error, raise HTTPException with status code 500 and detail as error message
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# only run if script is executed directly, not imported
if __name__ == "__main__":
    import uvicorn
    
    # run app on port 8000, host 0.0.0.0 (all interfaces)
    uvicorn.run(app, host="0.0.0.0", port=8000)