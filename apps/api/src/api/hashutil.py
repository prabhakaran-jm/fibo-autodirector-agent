"""JSON normalization and deterministic hashing."""

import json
import hashlib
from typing import Any, Dict


def normalize_json(obj: Any) -> str:
    """Normalize JSON to a stable string representation."""
    # Sort keys and use consistent formatting
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def hash_shot(shot: Dict) -> str:
    """Generate a deterministic SHA256 hash for a shot (first 16 chars)."""
    normalized = normalize_json(shot)
    hash_obj = hashlib.sha256(normalized.encode("utf-8"))
    return hash_obj.hexdigest()[:16]

