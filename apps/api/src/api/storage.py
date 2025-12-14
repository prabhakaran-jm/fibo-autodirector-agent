"""In-memory storage for batches, shots, and artifacts."""

from typing import Dict, List, Optional
from datetime import datetime
import uuid


# In-memory storage
_batches: Dict[str, Dict] = {}
_shots: Dict[str, Dict] = {}
_artifacts: Dict[str, Dict] = {}  # keyed by artifact_id
_artifacts_by_hash: Dict[str, Dict] = {}  # keyed by hash
_jobs: Dict[str, Dict] = {}  # keyed by job_id


def create_batch(rows: List[Dict]) -> str:
    """Create a new batch from CSV rows and return batch_id."""
    batch_id = str(uuid.uuid4())
    _batches[batch_id] = {
        "batch_id": batch_id,
        "rows": rows,
        "created_at": datetime.utcnow().isoformat(),
        "count": len(rows),
    }
    return batch_id


def get_batch(batch_id: str) -> Optional[Dict]:
    """Get batch by ID."""
    return _batches.get(batch_id)


def save_shots(shots: List[Dict]) -> None:
    """Save multiple shots to storage."""
    for shot in shots:
        shot_id = shot.get("shot_id")
        if shot_id:
            # Initialize status fields if not present
            if "status" not in shot:
                shot["status"] = "queued"
            if "last_error" not in shot:
                shot["last_error"] = None
            if "artifact_url" not in shot:
                shot["artifact_url"] = None
            if "duration_ms" not in shot:
                shot["duration_ms"] = None
            _shots[shot_id] = shot


def list_shots() -> List[Dict]:
    """List all shots with minimal info."""
    return [
        {
            "shot_id": shot.get("shot_id"),
            "hash": shot.get("hash"),
            "subject": shot.get("subject"),
            "status": shot.get("status", "queued"),
            "artifact_url": shot.get("artifact_url"),
        }
        for shot in _shots.values()
    ]


def get_shot(shot_id: str) -> Optional[Dict]:
    """Get full shot by ID."""
    return _shots.get(shot_id)


def get_artifact(artifact_id: str) -> Optional[Dict]:
    """Get artifact by ID."""
    return _artifacts.get(artifact_id)


def save_artifact(artifact_id: str, artifact: Dict) -> None:
    """Save an artifact."""
    _artifacts[artifact_id] = artifact


def save_artifact_by_hash(
    hash: str, url: str, provider: str, raw: Dict
) -> None:
    """Save an artifact keyed by hash."""
    _artifacts_by_hash[hash] = {
        "hash": hash,
        "url": url,
        "provider": provider,
        "raw": raw,
        "created_at": datetime.utcnow().isoformat(),
    }


def get_artifact_by_hash(hash: str) -> Optional[Dict]:
    """Get artifact by hash."""
    return _artifacts_by_hash.get(hash)


def update_shot_status(
    shot_id: str,
    status: str,
    artifact_url: Optional[str] = None,
    last_error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Update shot status and related fields."""
    shot = _shots.get(shot_id)
    if shot:
        shot["status"] = status
        if artifact_url is not None:
            shot["artifact_url"] = artifact_url
        if last_error is not None:
            shot["last_error"] = last_error
        if duration_ms is not None:
            shot["duration_ms"] = duration_ms


def create_job(shot_ids: List[str]) -> str:
    """Create a new render job and return job_id."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "shot_ids": shot_ids,
        "status": "queued",
        "progress": {"completed": 0, "total": len(shot_ids)},
        "results": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    """Get job by ID."""
    return _jobs.get(job_id)


def update_job(
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[Dict] = None,
    results: Optional[List[Dict]] = None,
) -> None:
    """Update job status, progress, and results."""
    job = _jobs.get(job_id)
    if job:
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"].update(progress)
        if results is not None:
            job["results"] = results
