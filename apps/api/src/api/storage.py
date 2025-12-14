"""In-memory storage for batches, shots, and artifacts."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import uuid


# In-memory storage
_batches: Dict[str, Dict] = {}
_shots: Dict[str, Dict] = {}  # Legacy: kept for backward compatibility
_shot_versions: Dict[str, List[Dict]] = {}  # keyed by shot_id, list of versions
_artifacts: Dict[str, Dict] = {}  # keyed by artifact_id
_artifacts_by_hash: Dict[str, Dict] = {}  # keyed by hash
_jobs: Dict[str, Dict] = {}  # keyed by job_id
_batch_cache_hits: Dict[str, int] = {}  # batch_id -> cache hit count


def _ensure_artifacts_dir():
    """Ensure artifacts directory exists at repo root."""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    artifacts_dir = project_root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return artifacts_dir


def create_batch(rows: List[Dict]) -> str:
    """Create a new batch from CSV rows and return batch_id."""
    batch_id = str(uuid.uuid4())
    _batches[batch_id] = {
        "batch_id": batch_id,
        "rows": rows,
        "created_at": datetime.utcnow().isoformat(),
        "count": len(rows),
    }
    _batch_cache_hits[batch_id] = 0
    return batch_id


def get_batch(batch_id: str) -> Optional[Dict]:
    """Get batch by ID."""
    return _batches.get(batch_id)


def save_shots(shots: List[Dict], batch_id: Optional[str] = None) -> None:
    """Save multiple shots to storage with versioning."""
    for shot in shots:
        shot_id = shot.get("shot_id")
        if shot_id:
            # Create version 1
            version = {
                "version": 1,
                "parent_hash": None,
                "json_payload": shot.copy(),
                "hash": shot.get("hash") or "",
                "artifact_url": None,
                "status": "queued",
                "duration_ms": None,
                "last_error": None,
                "batch_id": batch_id,
                "review_status": "pending",
                "review_note": None,
                "reviewed_at": None,
                "created_at": datetime.utcnow().isoformat(),
            }
            
            # Initialize versions list if needed
            if shot_id not in _shot_versions:
                _shot_versions[shot_id] = []
            
            _shot_versions[shot_id].append(version)
            
            # Keep legacy _shots for backward compatibility (latest version)
            _shots[shot_id] = {
                **shot,
                "status": "queued",
                "last_error": None,
                "artifact_url": None,
                "duration_ms": None,
            }


def get_shot_latest_version(shot_id: str) -> Optional[Dict]:
    """Get the latest version of a shot."""
    versions = _shot_versions.get(shot_id)
    if not versions:
        # Fallback to legacy storage
        return _shots.get(shot_id)
    # Return version with highest version number
    latest = max(versions, key=lambda v: v["version"])
    return latest["json_payload"].copy()


def get_shot_version(shot_id: str, version: int) -> Optional[Dict]:
    """Get a specific version of a shot."""
    versions = _shot_versions.get(shot_id)
    if not versions:
        return None
    for v in versions:
        if v["version"] == version:
            return v
    return None


def get_shot_versions(shot_id: str) -> List[Dict]:
    """Get all versions of a shot."""
    return _shot_versions.get(shot_id, [])


def create_shot_version(
    shot_id: str,
    json_payload: Dict,
    parent_hash: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Dict:
    """Create a new version of a shot."""
    versions = _shot_versions.get(shot_id, [])
    next_version = max([v["version"] for v in versions], default=0) + 1
    
    from .hashutil import hash_shot
    shot_hash = hash_shot(json_payload)
    
    version = {
        "version": next_version,
        "parent_hash": parent_hash,
        "json_payload": json_payload.copy(),
        "hash": shot_hash,
        "artifact_url": None,
        "status": "queued",
        "duration_ms": None,
        "last_error": None,
        "batch_id": batch_id,
        "review_status": "pending",
        "review_note": None,
        "reviewed_at": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    if shot_id not in _shot_versions:
        _shot_versions[shot_id] = []
    _shot_versions[shot_id].append(version)
    
    # Update legacy storage with latest
    _shots[shot_id] = {
        **json_payload,
        "status": "queued",
        "last_error": None,
        "artifact_url": None,
        "duration_ms": None,
    }
    
    return version


def update_shot_version_status(
    shot_id: str,
    version: int,
    status: str,
    artifact_url: Optional[str] = None,
    last_error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Update a specific shot version's status."""
    version_obj = get_shot_version(shot_id, version)
    if version_obj:
        version_obj["status"] = status
        if artifact_url is not None:
            version_obj["artifact_url"] = artifact_url
        if last_error is not None:
            version_obj["last_error"] = last_error
        if duration_ms is not None:
            version_obj["duration_ms"] = duration_ms
        
        # Update legacy storage if this is latest version
        latest = get_shot_latest_version(shot_id)
        if latest and version_obj["version"] == max(
            [v["version"] for v in _shot_versions.get(shot_id, [])]
        ):
            _shots[shot_id] = {
                **latest,
                "status": status,
                "artifact_url": artifact_url or _shots[shot_id].get("artifact_url"),
                "last_error": last_error or _shots[shot_id].get("last_error"),
                "duration_ms": duration_ms or _shots[shot_id].get("duration_ms"),
            }


def update_shot_version_review(
    shot_id: str,
    version: int,
    review_status: str,
    review_note: Optional[str] = None,
) -> None:
    """Update review status for a shot version."""
    version_obj = get_shot_version(shot_id, version)
    if version_obj:
        version_obj["review_status"] = review_status
        version_obj["review_note"] = review_note
        version_obj["reviewed_at"] = datetime.utcnow().isoformat()


def list_shots() -> List[Dict]:
    """List all shots with minimal info (latest version)."""
    result = []
    for shot_id, versions in _shot_versions.items():
        if not versions:
            continue
        latest = max(versions, key=lambda v: v["version"])
        result.append({
            "shot_id": shot_id,
            "hash": latest["hash"],
            "subject": latest["json_payload"].get("subject", ""),
            "status": latest["status"],
            "artifact_url": latest["artifact_url"],
            "review_status": latest["review_status"],
        })
    
    # Also include legacy shots not in versions
    for shot_id, shot in _shots.items():
        if shot_id not in _shot_versions:
            result.append({
                "shot_id": shot_id,
                "hash": shot.get("hash", ""),
                "subject": shot.get("subject", ""),
                "status": shot.get("status", "queued"),
                "artifact_url": shot.get("artifact_url"),
                "review_status": "pending",
            })
    
    return result


def get_shot(shot_id: str) -> Optional[Dict]:
    """Get full shot by ID (latest version, backward compatible)."""
    latest = get_shot_latest_version(shot_id)
    if latest:
        return latest
    return _shots.get(shot_id)


def get_shots_by_batch(batch_id: str) -> List[Dict]:
    """Get all shot versions for a batch."""
    result = []
    for shot_id, versions in _shot_versions.items():
        for version in versions:
            if version.get("batch_id") == batch_id:
                result.append({
                    "shot_id": shot_id,
                    "version": version["version"],
                    "hash": version["hash"],
                    "status": version["status"],
                    "artifact_url": version["artifact_url"],
                    "review_status": version["review_status"],
                    "json_payload": version["json_payload"],
                })
    return result


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
    """Update shot status (legacy, updates latest version)."""
    versions = _shot_versions.get(shot_id)
    if versions:
        latest_version = max(versions, key=lambda v: v["version"])
        update_shot_version_status(
            shot_id,
            latest_version["version"],
            status,
            artifact_url,
            last_error,
            duration_ms,
        )
    else:
        # Legacy path
        shot = _shots.get(shot_id)
        if shot:
            shot["status"] = status
            if artifact_url is not None:
                shot["artifact_url"] = artifact_url
            if last_error is not None:
                shot["last_error"] = last_error
            if duration_ms is not None:
                shot["duration_ms"] = duration_ms


def increment_batch_cache_hits(batch_id: str) -> None:
    """Increment cache hit count for a batch."""
    _batch_cache_hits[batch_id] = _batch_cache_hits.get(batch_id, 0) + 1


def create_job(shot_ids: List[str], shot_versions: Optional[Dict[str, int]] = None) -> str:
    """Create a new render job and return job_id.
    
    Args:
        shot_ids: List of shot IDs to render
        shot_versions: Optional dict mapping shot_id to version number
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "shot_ids": shot_ids,
        "shot_versions": shot_versions or {},
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


def write_manifest(batch_id: str) -> Dict[str, str]:
    """Write manifest.json and report.json for a batch.
    
    Returns:
        dict with paths to manifest and report files
    """
    artifacts_dir = _ensure_artifacts_dir()
    batch_dir = artifacts_dir / batch_id
    batch_dir.mkdir(exist_ok=True)
    
    shots = get_shots_by_batch(batch_id)
    
    # Build manifest
    manifest = {
        "batch_id": batch_id,
        "created_at": _batches.get(batch_id, {}).get("created_at"),
        "shots": [],
    }
    
    planned = len(shots)
    rendered_done = 0
    failed = 0
    approved = 0
    rejected = 0
    cache_hits = _batch_cache_hits.get(batch_id, 0)
    
    for shot in shots:
        manifest["shots"].append({
            "shot_id": shot["shot_id"],
            "version": shot["version"],
            "hash": shot["hash"],
            "artifact_url": shot["artifact_url"],
            "status": shot["status"],
            "review_status": shot["review_status"],
        })
        
        if shot["status"] == "done":
            rendered_done += 1
        elif shot["status"] == "failed":
            failed += 1
        
        if shot["review_status"] == "approved":
            approved += 1
        elif shot["review_status"] == "rejected":
            rejected += 1
    
    # Build report
    report = {
        "batch_id": batch_id,
        "created_at": _batches.get(batch_id, {}).get("created_at"),
        "counts": {
            "planned": planned,
            "rendered_done": rendered_done,
            "failed": failed,
            "approved": approved,
            "rejected": rejected,
            "cache_hits": cache_hits,
        },
    }
    
    # Write files
    manifest_path = batch_dir / "manifest.json"
    report_path = batch_dir / "report.json"
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    return {
        "manifest": str(manifest_path),
        "report": str(report_path),
    }
