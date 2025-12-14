"""FastAPI application entry point."""

from fastapi import FastAPI

from .routes import router
from .worker import start_worker

app = FastAPI(
    title="FIBO AutoDirector Agent API",
    description="Backend API for FIBO AutoDirector Agent",
    version="0.1.0",
)

app.include_router(router)

# Start worker on startup
start_worker(app)


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
