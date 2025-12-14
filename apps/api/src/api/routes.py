"""API routes for FIBO AutoDirector Agent."""

import csv
import io
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel

from .storage import (
    create_batch,
    get_batch,
    save_shots,
    list_shots,
    get_shot,
)
from .rules import expand_record_to_shot
from .hashutil import hash_shot


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


class ShotListResponse(BaseModel):
    shots: List[ShotListItem]


class RenderItem(BaseModel):
    shot_id: str
    cached: bool
    url: str


class RenderRequest(BaseModel):
    shot_ids: List[str]


class RenderResponse(BaseModel):
    renders: List[RenderItem]


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
    """List all shots with minimal info."""
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


@router.post("/render", response_model=RenderResponse)
async def render(request: RenderRequest):
    """
    Render shots (stub - does not call external API).
    Returns mock renders with cached:false and mock:// URLs.
    """
    renders = []
    for shot_id in request.shot_ids:
        shot = get_shot(shot_id)
        if shot:
            renders.append(
                RenderItem(
                    shot_id=shot_id,
                    cached=False,
                    url=f"mock://render/{shot_id}",
                )
            )

    return RenderResponse(renders=renders)
