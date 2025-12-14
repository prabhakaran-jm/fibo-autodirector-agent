"""Rules for expanding CSV records into FIBO-style shot JSON."""

import json
import os
from pathlib import Path
from typing import Dict, Optional


def deep_merge(base: Dict, overlay: Dict) -> Dict:
    """Deep merge overlay into base dict."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_preset(preset_id: str) -> Optional[Dict]:
    """Load preset JSON from packages/presets/presets/{preset_id}.json."""
    # Get the project root (assuming we're in apps/api/src/api)
    project_root = Path(__file__).parent.parent.parent.parent.parent
    preset_path = project_root / "packages" / "presets" / "presets" / f"{preset_id}.json"
    
    if preset_path.exists():
        with open(preset_path, "r") as f:
            return json.load(f)
    return None


def expand_record_to_shot(record: Dict, preset_id: Optional[str] = None) -> Dict:
    """
    Expand a CSV record into a FIBO-style shot JSON.
    
    Args:
        record: CSV row as dict (e.g., {sku, product_name, category, material, finish})
        preset_id: Optional preset ID to load and merge
    
    Returns:
        Shot JSON with shot_id, subject, camera, lens, lighting, color, background, output
    """
    # Base shot structure
    shot = {
        "shot_id": record.get("sku", "unknown"),
        "subject": record.get("product_name", "Unknown Product"),
        "camera": {
            "fov": 45,
            "position": {"x": 0, "y": 0, "z": 5},
            "rotation": {"x": 0, "y": 0, "z": 0},
        },
        "lens": {
            "aperture": 2.8,
            "focal_length": 50,
        },
        "lighting": {
            "key_light": {
                "intensity": 1.0,
                "position": {"x": 2, "y": 3, "z": 4},
            },
            "rim_light": {
                "intensity": 0.5,
                "position": {"x": -2, "y": 2, "z": 3},
            },
        },
        "color": {
            "palette": ["#ffffff", "#000000"],
        },
        "background": {
            "hex": "#f5f5f5",
        },
        "output": {
            "width": 1024,
            "height": 1024,
        },
    }
    
    # Apply rules based on record fields
    finish = record.get("finish", "").lower()
    category = record.get("category", "").lower()
    
    # Rule: if finish == glossy, reduce key light intensity and add rim light
    if finish == "glossy":
        shot["lighting"]["key_light"]["intensity"] = 0.7
        shot["lighting"]["rim_light"]["intensity"] = 0.8
    
    # Rule: if category == macro, increase fov and aperture
    if category == "macro":
        shot["camera"]["fov"] = 60
        shot["lens"]["aperture"] = 1.4
    
    # Load and merge preset if provided
    if preset_id:
        preset = load_preset(preset_id)
        if preset:
            shot = deep_merge(shot, preset)
    
    return shot

