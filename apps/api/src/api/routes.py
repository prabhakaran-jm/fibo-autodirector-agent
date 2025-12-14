"""API routes for FIBO AutoDirector Agent."""

import csv
import io
import time
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel

from .storage import (
    create_batch,
    get_batch,
    save_shots,
    list_shots,
    get_shot,
    create_job,
    get_job,
)
from .rules import expand_record_to_shot
from .hashutil import hash_shot
from .models import (
    RenderRequest,
    RenderJobResponse,
    JobProgressResponse,
    RenderResponseItem,
)
from .worker import enqueue_render_job
from .fibo_provider import get_provider
from .hashutil import hash_shot as compute_hash


router = APIRouter()


class IngestResponse(BaseModel):
    batch_id: str
    count: int


class PlanResponse(BaseModel):
    planned: int


class ShotListItem(BaseModel):
    shot_id: str
    hash: str
    subject: str
    status: Optional[str] = None
    artifact_url: Optional[str] = None


class ShotListResponse(BaseModel):
    shots: List[ShotListItem]


@router.post("/ingest/csv", response_model=IngestResponse)
async def ingest_csv(file: UploadFile = File(...)):
    """Ingest a CSV file and return batch_id and count."""
    contents = await file.read()
    text = contents.decode("utf-8")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        raise HTTPException(
            status_code=400, detail="CSV file is empty or has no data rows"
        )

    batch_id = create_batch(rows)

    return IngestResponse(batch_id=batch_id, count=len(rows))


@router.post("/plan", response_model=PlanResponse)
async def plan(
    batch_id: str = Query(..., description="Batch ID from ingest"),
    preset_id: Optional[str] = Query(
        None, description="Optional preset ID"
    ),
):
    """Expand batch rows into shots and save them."""
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=404, detail=f"Batch {batch_id} not found"
        )

    shots = []
    for row in batch["rows"]:
        shot = expand_record_to_shot(row, preset_id)
        shot["hash"] = hash_shot(shot)
        shots.append(shot)

    save_shots(shots)

    return PlanResponse(planned=len(shots))


@router.get("/shots", response_model=ShotListResponse)
async def get_shots():
    """List all shots with minimal info including status and artifact_url."""
    shots = list_shots()
    return ShotListResponse(shots=shots)


@router.get("/shots/{shot_id}")
async def get_shot_by_id(shot_id: str):
    """Get full shot JSON by ID."""
    shot = get_shot(shot_id)
    if not shot:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )
    return shot


@router.post("/render", response_model=RenderJobResponse)
async def render(request: RenderRequest):
    """
    Enqueue a render job and return immediately.
    Use GET /jobs/{job_id} to check progress.
    """
    if not request.shot_ids:
        # If no shot_ids provided, render all shots
        all_shots = list_shots()
        shot_ids = [s["shot_id"] for s in all_shots]
    else:
        shot_ids = request.shot_ids

    job_id = create_job(shot_ids)
    await enqueue_render_job(job_id)

    return RenderJobResponse(job_id=job_id, queued=len(shot_ids))


@router.get("/jobs/{job_id}", response_model=JobProgressResponse)
async def get_job_status(job_id: str):
    """Get job status and progress."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Job {job_id} not found"
        )

    # Convert results to RenderResponseItem
    results = [
        RenderResponseItem(**r) for r in job.get("results", [])
    ]

    return JobProgressResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        results=results,
    )


@router.post("/render/sync")
async def render_sync(request: RenderRequest):
    """
    Synchronous render endpoint for small demos.
    Renders in the request thread but still uses cache.
    """
    if not request.shot_ids:
        all_shots = list_shots()
        shot_ids = [s["shot_id"] for s in all_shots]
    else:
        shot_ids = request.shot_ids

    provider = get_provider()
    results = []

    for shot_id in shot_ids:
        shot = get_shot(shot_id)
        if not shot:
            results.append(
                RenderResponseItem(
                    shot_id=shot_id,
                    cached=False,
                    status="failed",
                    error=f"Shot {shot_id} not found",
                    hash="",
                )
            )
            continue

        shot_hash = shot.get("hash") or compute_hash(shot)
        start_time = time.time()

        # Check cache
        from .storage import get_artifact_by_hash, save_artifact_by_hash
        from .storage import update_shot_status

        cached_artifact = get_artifact_by_hash(shot_hash)
        if cached_artifact:
            duration_ms = int((time.time() - start_time) * 1000)
            update_shot_status(
                shot_id,
                "done",
                artifact_url=cached_artifact["url"],
                duration_ms=duration_ms,
            )
            results.append(
                RenderResponseItem(
                    shot_id=shot_id,
                    cached=True,
                    status="done",
                    url=cached_artifact["url"],
                    hash=shot_hash,
                )
            )
            continue

        # Render
        try:
            update_shot_status(shot_id, "running")
            result = provider.render(shot)
            url = result["url"]
            raw = result.get("raw", {})

            provider_name = "mock" if "mock://" in url else "bria"
            save_artifact_by_hash(shot_hash, url, provider_name, raw)

            duration_ms = int((time.time() - start_time) * 1000)
            update_shot_status(
                shot_id, "done", artifact_url=url, duration_ms=duration_ms
            )

            results.append(
                RenderResponseItem(
                    shot_id=shot_id,
                    cached=False,
                    status="done",
                    url=url,
                    hash=shot_hash,
                )
            )
        except Exception as e:
            error_msg = str(e)
            duration_ms = int((time.time() - start_time) * 1000)
            update_shot_status(
                shot_id,
                "failed",
                last_error=error_msg,
                duration_ms=duration_ms,
            )
            results.append(
                RenderResponseItem(
                    shot_id=shot_id,
                    cached=False,
                    status="failed",
                    error=error_msg,
                    hash=shot_hash,
                )
            )

    return {"renders": results}
