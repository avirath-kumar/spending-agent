from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# import database models and engine
from database import engine, Base

# Import all routers from files
from api.chat_routes import router as chat_router
from api.plaid_routes import router as plaid_router

# Load environment variables from .env file
load_dotenv()

# Lifespan context manager for startup/shutdown events - replaces @app.on_event

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle, handle startup tasks and cleanup"""
    # Startup
    print("Starting up PennyWise API...")
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified")
    
    yield  # Application runs
    
    # Shutdown
    print("Shutting down PennyWise API...")    

# Create FastAPI app with config to centralize all app config in one place
app = FastAPI(
    title="PennyWise API",
    description="AI-powered spending analysis assistant",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS to allow frontend to communicate with the api
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",     # Streamlit default
        "http://localhost:3000",     # If you add a React frontend later
        "https://your-domain.com"   # Production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - makes the app modular
app.include_router(chat_router) # all chat endpoints will be under /chat
app.include_router(plaid_router) # all plaid endpoints will be under /plaid

# Root endpoint for health checks - helpful for monitoring / debugging
@app.get("/")
async def root():
    return {
        "message": "Welcome to PennyWise API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/chat",
            "plaid": "/plaid",
            "docs": "/docs"  # FastAPI auto-generates documentation
        }
    }

# Claude included a detailed health check - omitting for now

# only run if script is executed directly, not imported
if __name__ == "__main__":
    import uvicorn
    
    # run app on port 8000, host 0.0.0.0 (all interfaces)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True, # Auto reload on code changes
        log_level="info"
    )