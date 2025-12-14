"""FastAPI application entry point."""

from pathlib import Path
from fastapi import FastAPI
from dotenv import load_dotenv

from .routes import router

# Load environment variables from project root
project_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(project_root / ".env")

app = FastAPI(
    title="FIBO AutoDirector Agent API",
    description="Backend API for FIBO AutoDirector Agent",
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FIBO AutoDirector Agent API",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

