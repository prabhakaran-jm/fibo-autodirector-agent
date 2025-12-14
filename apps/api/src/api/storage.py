"""In-memory storage for batches, shots, and artifacts."""

from typing import Dict, List, Optional
from datetime import datetime
import uuid


# In-memory storage
_batches: Dict[str, Dict] = {}
_shots: Dict[str, Dict] = {}
_artifacts: Dict[str, Dict] = {}


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
            _shots[shot_id] = shot


def list_shots() -> List[Dict]:
    """List all shots with minimal info."""
    return [
        {
            "shot_id": shot.get("shot_id"),
            "hash": shot.get("hash"),
            "subject": shot.get("subject"),
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

