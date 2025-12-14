"""API routes for FIBO AutoDirector Agent."""

import csv
import io
import time
from typing import List, Optional, Dict
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Query,
    HTTPException,
    Header,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import zipfile

from .storage import (
    create_batch,
    get_batch,
    save_shots,
    list_shots,
    get_shot,
    create_job,
    get_job,
    get_shot_latest_version,
    get_shot_version,
    get_shot_versions,
    create_shot_version,
    update_shot_version_review,
    write_manifest,
)
from .rules import expand_record_to_shot
from .hashutil import hash_shot
from .models import (
    RenderRequest,
    RenderJobResponse,
    JobProgressResponse,
    RenderResponseItem,
    RenderShotSyncRequest,
    RenderShotSyncResponse,
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
        shot, rules_applied = expand_record_to_shot(row, preset_id)
        shot["hash"] = hash_shot(shot)
        shot["_rules_applied"] = rules_applied  # Store for explain endpoint
        shots.append(shot)

    save_shots(shots, batch_id=batch_id)

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


@router.post("/render/shot/sync", response_model=RenderShotSyncResponse)
async def render_shot_sync(request: RenderShotSyncRequest):
    """
    Render a single raw shot JSON payload synchronously.
    No prior planning needed - accepts full FIBO JSON directly.

    Supports two modes:
    - Mode A (internal shot): requires shot_id, subject, camera, lens,
      lighting, output
    - Mode B (structured_prompt): requires shot_id, structured_prompt
      (string or object), optional output
    """
    import json

    shot = request.shot.copy()

    # Always require shot_id
    if "shot_id" not in shot:
        raise HTTPException(
            status_code=400,
            detail="Missing required key: shot_id",
        )

    # Determine mode: structured_prompt mode or internal shot mode
    has_structured_prompt = "structured_prompt" in shot
    has_internal_format = all(
        key in shot
        for key in ["subject", "camera", "lens", "lighting", "output"]
    )

    rules_applied = []

    if has_structured_prompt:
        # Mode B: structured_prompt mode
        rules_applied.append("structured_prompt_mode")

        # Extract subject from structured_prompt if possible
        sp = shot.get("structured_prompt")
        if isinstance(sp, str):
            try:
                sp_obj = json.loads(sp)
                if isinstance(sp_obj, dict) and "short_description" in sp_obj:
                    shot["subject"] = sp_obj["short_description"]
                else:
                    shot["subject"] = "structured_prompt"
            except (json.JSONDecodeError, TypeError):
                shot["subject"] = "structured_prompt"
        elif isinstance(sp, dict) and "short_description" in sp:
            shot["subject"] = sp["short_description"]
        else:
            shot["subject"] = "structured_prompt"

        # Set default output if not provided
        if "output" not in shot:
            shot["output"] = {
                "width": 1024,
                "height": 1024,
                "bit_depth": 16,
                "hdr": False,
            }
    elif has_internal_format:
        # Mode A: internal shot format
        rules_applied.append("manual_shot_payload")
    else:
        # Neither mode satisfied
        if has_structured_prompt:
            # Has structured_prompt but missing other fields - OK
            pass
        else:
            # Missing required keys for internal format
            missing_keys = [
                key
                for key in ["subject", "camera", "lens", "lighting", "output"]
                if key not in shot
            ]
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Missing required keys for internal shot format: "
                    f"{', '.join(missing_keys)}. "
                    f"Alternatively, provide 'structured_prompt' for "
                    f"Bria mode."
                ),
            )

    # Apply preset if provided (only for internal format)
    from .rules import deep_merge, load_preset

    if request.preset_id and not has_structured_prompt:
        preset = load_preset(request.preset_id)
        if preset:
            shot = deep_merge(shot, preset)
            rules_applied.append(f"preset_applied:{request.preset_id}")

    # Compute hash
    shot_hash = compute_hash(shot)
    shot_id = shot["shot_id"]
    start_time = time.time()

    # Check cache
    from .storage import (
        get_artifact_by_hash,
        save_artifact_by_hash,
        create_shot_version,
        update_shot_version_status,
    )

    cached_artifact = get_artifact_by_hash(shot_hash)
    provider = get_provider()

    if cached_artifact:
        # Cache hit
        duration_ms = int((time.time() - start_time) * 1000)
        provider_name = cached_artifact.get("provider", "unknown")

        # Upsert shot into storage
        version_obj = create_shot_version(
            shot_id,
            shot,
            parent_hash=None,
            batch_id=None,
            rules_applied=rules_applied,
        )
        update_shot_version_status(
            shot_id,
            version_obj["version"],
            "done",
            artifact_url=cached_artifact["url"],
            duration_ms=duration_ms,
        )

        return RenderShotSyncResponse(
            shot_id=shot_id,
            hash=shot_hash,
            cached=True,
            url=cached_artifact["url"],
            provider=provider_name,
        )

    # Render with provider
    try:
        result = provider.render(shot)
        url = result["url"]
        raw = result.get("raw", {})

        provider_name = "mock" if "mock://" in url else "bria"
        save_artifact_by_hash(shot_hash, url, provider_name, raw)

        duration_ms = int((time.time() - start_time) * 1000)

        # Upsert shot into storage
        version_obj = create_shot_version(
            shot_id,
            shot,
            parent_hash=None,
            batch_id=None,
            rules_applied=rules_applied,
        )
        update_shot_version_status(
            shot_id,
            version_obj["version"],
            "done",
            artifact_url=url,
            duration_ms=duration_ms,
        )

        return RenderShotSyncResponse(
            shot_id=shot_id,
            hash=shot_hash,
            cached=False,
            url=url,
            provider=provider_name,
        )
    except Exception as e:
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)

        # Still create shot version but mark as failed
        version_obj = create_shot_version(
            shot_id,
            shot,
            parent_hash=None,
            batch_id=None,
            rules_applied=rules_applied,
        )
        update_shot_version_status(
            shot_id,
            version_obj["version"],
            "failed",
            last_error=error_msg,
            duration_ms=duration_ms,
        )

        raise HTTPException(status_code=500, detail=f"Render failed: {error_msg}")


# Version and patch endpoints

class RerenderRequest(BaseModel):
    json_patch: Dict
    preset_id: Optional[str] = None


class RerenderResponse(BaseModel):
    job_id: str
    shot_id: str
    version: int
    hash: str


@router.post("/shots/{shot_id}/rerender", response_model=RerenderResponse)
async def rerender_shot(shot_id: str, request: RerenderRequest):
    """Create a new shot version with JSON patch and enqueue render."""
    latest = get_shot_latest_version(shot_id)
    if not latest:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )
    
    # Deep merge patch
    from .rules import deep_merge

    def _track_changes(old_dict, new_dict, path=""):
        """Recursively track changes between dicts."""
        changes = []
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(_track_changes(old_val, new_val, current_path))
            elif old_val != new_val:
                changes.append(
                    f"rerender patch → {current_path} changed {old_val} → {new_val}"
                )
        return changes

    patched = latest.copy()
    patch_rules = _track_changes(latest, request.json_patch)
    patched = deep_merge(patched, request.json_patch)

    # Apply preset if provided
    if request.preset_id:
        from .rules import load_preset
        preset = load_preset(request.preset_id)
        if preset:
            patched = deep_merge(patched, preset)
            patch_rules.append(f"preset={request.preset_id} → applied preset")

    # Get parent hash
    versions = get_shot_versions(shot_id)
    parent_hash = None
    if versions:
        latest_version = max(versions, key=lambda v: v["version"])
        parent_hash = latest_version["hash"]

    # Get batch_id from latest version
    batch_id = None
    if versions:
        latest_version = max(versions, key=lambda v: v["version"])
        batch_id = latest_version.get("batch_id")

    # Create new version
    new_version = create_shot_version(
        shot_id,
        patched,
        parent_hash=parent_hash,
        batch_id=batch_id,
        rules_applied=patch_rules,
    )
    
    # Enqueue render job
    job_id = create_job([shot_id], shot_versions={shot_id: new_version["version"]})
    await enqueue_render_job(job_id)
    
    return RerenderResponse(
        job_id=job_id,
        shot_id=shot_id,
        version=new_version["version"],
        hash=new_version["hash"],
    )


@router.get("/shots/{shot_id}/versions")
async def get_shot_versions_endpoint(shot_id: str):
    """Get all versions of a shot."""
    versions = get_shot_versions(shot_id)
    if not versions:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )
    
    return {
        "shot_id": shot_id,
        "versions": [
            {
                "version": v["version"],
                "hash": v["hash"],
                "status": v["status"],
                "artifact_url": v["artifact_url"],
                "created_at": v["created_at"],
                "parent_hash": v["parent_hash"],
                "review_status": v["review_status"],
            }
            for v in versions
        ],
    }


def _compare_dicts(old: Dict, new: Dict, path: str = "") -> List[Dict]:
    """Recursive dict comparison, returns list of changes."""
    changes = []
    all_keys = set(old.keys()) | set(new.keys())
    
    for key in all_keys:
        current_path = f"{path}.{key}" if path else key
        old_val = old.get(key)
        new_val = new.get(key)
        
        if key not in old:
            changes.append({
                "path": current_path,
                "old_value": None,
                "new_value": new_val,
            })
        elif key not in new:
            changes.append({
                "path": current_path,
                "old_value": old_val,
                "new_value": None,
            })
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(_compare_dicts(old_val, new_val, current_path))
        elif old_val != new_val:
            changes.append({
                "path": current_path,
                "old_value": old_val,
                "new_value": new_val,
            })
    
    return changes


@router.get("/shots/{shot_id}/compare")
async def compare_versions(
    shot_id: str,
    from_version: int = Query(..., alias="from"),
    to_version: int = Query(..., alias="to"),
):
    """Compare two versions of a shot."""
    v1 = get_shot_version(shot_id, from_version)
    v2 = get_shot_version(shot_id, to_version)

    if not v1 or not v2:
        raise HTTPException(
            status_code=404, detail="One or both versions not found"
        )

    changes = _compare_dicts(v1["json_payload"], v2["json_payload"])

    return {
        "shot_id": shot_id,
        "from_version": from_version,
        "to_version": to_version,
        "changes": changes,
    }


@router.get("/shots/{shot_id}/explain")
async def explain_shot(shot_id: str):
    """Explain how a shot was generated (deterministic explanation)."""
    import json

    versions = get_shot_versions(shot_id)
    if not versions:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )

    latest = max(versions, key=lambda v: v["version"])
    shot_json = latest.get("json_payload", {})
    shot_hash = latest.get("hash", "")

    # Determine mode
    has_structured_prompt = "structured_prompt" in shot_json
    mode = "structured_prompt" if has_structured_prompt else "internal_shot"

    # Get all rules applied across versions (safely)
    all_rules = []
    for version in versions:
        version_rules = version.get("rules_applied", [])
        if isinstance(version_rules, list):
            all_rules.extend(version_rules)

    # Extract subject summary and derived parameters based on mode
    subject_summary = ""
    derived_params = {}

    if mode == "structured_prompt":
        # Structured prompt mode
        sp = shot_json.get("structured_prompt")
        parse_failed = False

        if isinstance(sp, str):
            try:
                sp_obj = json.loads(sp)
                if isinstance(sp_obj, dict) and "short_description" in sp_obj:
                    subject_summary = sp_obj["short_description"]
                else:
                    subject_summary = "structured_prompt (unparsed)"
                    parse_failed = True
            except (json.JSONDecodeError, TypeError):
                subject_summary = "structured_prompt (unparsed)"
                parse_failed = True
        elif isinstance(sp, dict):
            if "short_description" in sp:
                subject_summary = sp["short_description"]
            else:
                subject_summary = "structured_prompt"
        else:
            subject_summary = "structured_prompt (unparsed)"
            parse_failed = True

        if parse_failed:
            all_rules.append("structured_prompt_parse_failed")

        # Add output dimensions if present
        output = shot_json.get("output", {})
        if isinstance(output, dict):
            if "width" in output:
                derived_params["output.width"] = output["width"]
            if "height" in output:
                derived_params["output.height"] = output["height"]
    else:
        # Internal shot mode
        subject_summary = shot_json.get("subject", "unknown")

        # Extract derived parameters (non-default values) - safely
        camera = shot_json.get("camera", {})
        if isinstance(camera, dict) and "fov" in camera:
            fov = camera.get("fov")
            if fov != 45:
                derived_params["camera.fov"] = fov

        lens = shot_json.get("lens", {})
        if isinstance(lens, dict) and "aperture" in lens:
            aperture = lens.get("aperture")
            if aperture != 2.8:
                derived_params["lens.aperture"] = aperture

        lighting = shot_json.get("lighting", {})
        if isinstance(lighting, dict):
            key_light = lighting.get("key_light", {})
            if isinstance(key_light, dict) and "intensity" in key_light:
                intensity = key_light.get("intensity")
                if intensity != 1.0:
                    derived_params["lighting.key_light.intensity"] = intensity

        # Add output dimensions if present
        output = shot_json.get("output", {})
        if isinstance(output, dict):
            if "width" in output:
                derived_params["output.width"] = output["width"]
            if "height" in output:
                derived_params["output.height"] = output["height"]

    return {
        "shot_id": shot_id,
        "version": latest.get("version", 1),
        "hash": shot_hash,
        "mode": mode,
        "rules_applied": all_rules,
        "derived_parameters": derived_params,
        "subject_summary": subject_summary,
        "why_this_is_reproducible": (
            "All parameters are explicit JSON fields. "
            "Re-running this JSON produces the same hash and output. "
            "No prompts, no randomness, no drift."
        ),
    }


# Review endpoints

class ReviewRequest(BaseModel):
    note: Optional[str] = None


def _check_admin_token(x_admin_token: Optional[str] = Header(None)) -> bool:
    """Check admin token if configured."""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        return True  # No token required if not configured
    return x_admin_token == admin_token


@router.post("/shots/{shot_id}/approve")
async def approve_shot(
    shot_id: str,
    request: ReviewRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Approve the latest version of a shot."""
    if not _check_admin_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    versions = get_shot_versions(shot_id)
    if not versions:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )
    
    latest_version = max(versions, key=lambda v: v["version"])
    update_shot_version_review(
        shot_id, latest_version["version"], "approved", request.note
    )
    
    return {
        "shot_id": shot_id,
        "version": latest_version["version"],
        "review_status": "approved",
        "review_note": request.note,
    }


@router.post("/shots/{shot_id}/reject")
async def reject_shot(
    shot_id: str,
    request: ReviewRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Reject the latest version of a shot."""
    if not _check_admin_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    versions = get_shot_versions(shot_id)
    if not versions:
        raise HTTPException(
            status_code=404, detail=f"Shot {shot_id} not found"
        )
    
    latest_version = max(versions, key=lambda v: v["version"])
    update_shot_version_review(
        shot_id, latest_version["version"], "rejected", request.note
    )
    
    return {
        "shot_id": shot_id,
        "version": latest_version["version"],
        "review_status": "rejected",
        "review_note": request.note,
    }


# Export endpoints

@router.post("/export/batch/{batch_id}")
async def export_batch(batch_id: str):
    """Export batch manifest and report to disk."""
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=404, detail=f"Batch {batch_id} not found"
        )
    
    paths = write_manifest(batch_id)
    
    return {
        "batch_id": batch_id,
        "paths": paths,
        "message": "Export completed",
    }


@router.get("/export/batch/{batch_id}/manifest")
async def get_export_manifest(batch_id: str):
    """Get manifest.json content."""
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent.parent
    manifest_path = project_root / "artifacts" / batch_id / "manifest.json"
    
    if not manifest_path.exists():
        raise HTTPException(
            status_code=404, detail="Manifest not found. Run POST /export/batch/{batch_id} first."
        )
    
    import json
    with open(manifest_path, "r") as f:
        return json.load(f)


@router.get("/export/batch/{batch_id}/download")
async def download_batch_zip(batch_id: str):
    """Download batch as zip file with manifest, report, and images."""
    from pathlib import Path
    import tempfile
    from .config import FIBO_PROVIDER
    from .storage import get_shots_by_batch
    
    project_root = Path(__file__).parent.parent.parent.parent.parent
    batch_dir = project_root / "artifacts" / batch_id
    
    if not batch_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Batch export not found. Run POST /export/batch/{batch_id} first.",
        )
    
    # Create temp zip file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_path = Path(tmp.name)
    
    shots = get_shots_by_batch(batch_id)
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add manifest and report
        manifest_path = batch_dir / "manifest.json"
        report_path = batch_dir / "report.json"
        
        if manifest_path.exists():
            zipf.write(manifest_path, "manifest.json")
        if report_path.exists():
            zipf.write(report_path, "report.json")
        
        # Add images
        images_dir = batch_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        if FIBO_PROVIDER == "mock":
            # Generate placeholder images
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                for shot in shots:
                    if shot.get("artifact_url"):
                        shot_id = shot["shot_id"]
                        hash_val = shot["hash"]
                        
                        # Create small placeholder image
                        img = Image.new("RGB", (512, 512), color="white")
                        draw = ImageDraw.Draw(img)
                        
                        # Draw text
                        text = f"{shot_id}\n{hash_val}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 40)
                        except Exception:
                            font = ImageFont.load_default()
                        
                        draw.text((50, 200), text, fill="black", font=font)
                        
                        # Save to zip
                        img_path = images_dir / f"{shot_id}.png"
                        img.save(img_path)
                        zipf.write(img_path, f"images/{shot_id}.png")
            except ImportError:
                # PIL not available, create URLs file instead
                with open(images_dir / "urls.txt", "w") as f:
                    for shot in shots:
                        if shot.get("artifact_url"):
                            f.write(f"{shot['artifact_url']}\n")
                zipf.write(images_dir / "urls.txt", "images/urls.txt")
        else:
            # Bria provider - create URLs file
            download_remote = os.getenv("DOWNLOAD_REMOTE_IMAGES", "false").lower() == "true"
            
            if download_remote:
                # TODO: Download remote images if needed
                pass
            
            with open(images_dir / "urls.txt", "w") as f:
                for shot in shots:
                    if shot.get("artifact_url"):
                        f.write(f"{shot['artifact_url']}\n")
            zipf.write(images_dir / "urls.txt", "images/urls.txt")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"batch_{batch_id}.zip",
    )
