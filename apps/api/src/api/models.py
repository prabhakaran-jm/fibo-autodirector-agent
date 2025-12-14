"""Pydantic models for API requests and responses."""

from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class RenderRequest(BaseModel):
    """Request to render shots."""

    shot_ids: Optional[List[str]] = None


class RenderResponseItem(BaseModel):
    """Single render result."""

    shot_id: str
    cached: bool
    status: str
    url: Optional[str] = None
    error: Optional[str] = None
    hash: str


class RenderJobResponse(BaseModel):
    """Response when creating a render job."""

    job_id: str
    queued: int


class JobProgressResponse(BaseModel):
    """Job progress information."""

    job_id: str
    status: str
    progress: dict  # {"completed": int, "total": int}
    results: List[RenderResponseItem]

