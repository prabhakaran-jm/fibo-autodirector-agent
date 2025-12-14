"""Tests for the explain endpoint."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))  # noqa: E402

from api.main import app  # noqa: E402
from api.storage import (  # noqa: E402
    create_shot_version,
    _shot_versions,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    _shot_versions.clear()
    yield
    _shot_versions.clear()


def test_explain_structured_prompt_mode(client):
    """Test explain endpoint with structured_prompt-only shot."""
    shot_id = "test-structured-prompt-001"
    structured_prompt = {
        "short_description": "A clean product photo",
        "objects": [
            {
                "description": "Test product",
                "location": "center",
            }
        ],
        "background_setting": "Neutral background",
        "lighting": {
            "conditions": "Soft studio lighting",
        },
    }

    # Create shot version with structured_prompt only
    shot_json = {
        "shot_id": shot_id,
        "structured_prompt": structured_prompt,
        "output": {
            "width": 1024,
            "height": 1024,
        },
    }

    create_shot_version(
        shot_id=shot_id,
        json_payload=shot_json,
        parent_hash=None,
        batch_id=None,
        rules_applied=["structured_prompt_mode"],
    )

    # Call explain endpoint
    response = client.get(f"/shots/{shot_id}/explain")

    # Should return 200
    assert response.status_code == 200

    data = response.json()

    # Verify response structure
    assert data["shot_id"] == shot_id
    assert data["mode"] == "structured_prompt"
    assert "hash" in data
    assert isinstance(data["rules_applied"], list)
    assert "structured_prompt_mode" in data["rules_applied"]
    assert isinstance(data["derived_parameters"], dict)
    assert "subject_summary" in data
    assert data["subject_summary"] == "A clean product photo"
    assert "why_this_is_reproducible" in data

    # Verify derived parameters include output dimensions
    assert "output.width" in data["derived_parameters"]
    assert data["derived_parameters"]["output.width"] == 1024
    assert "output.height" in data["derived_parameters"]
    assert data["derived_parameters"]["output.height"] == 1024


def test_explain_structured_prompt_string(client):
    """Test explain endpoint with structured_prompt as JSON string."""
    shot_id = "test-structured-prompt-string-001"
    structured_prompt_str = json.dumps({
        "short_description": "Test product description",
        "objects": [],
    })

    shot_json = {
        "shot_id": shot_id,
        "structured_prompt": structured_prompt_str,
    }

    create_shot_version(
        shot_id=shot_id,
        json_payload=shot_json,
        parent_hash=None,
        batch_id=None,
        rules_applied=["structured_prompt_mode"],
    )

    response = client.get(f"/shots/{shot_id}/explain")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "structured_prompt"
    assert data["subject_summary"] == "Test product description"


def test_explain_structured_prompt_parse_failure(client):
    """Test explain endpoint with unparseable structured_prompt string."""
    shot_id = "test-structured-prompt-parse-fail-001"
    structured_prompt_str = "not valid json {"

    shot_json = {
        "shot_id": shot_id,
        "structured_prompt": structured_prompt_str,
    }

    create_shot_version(
        shot_id=shot_id,
        json_payload=shot_json,
        parent_hash=None,
        batch_id=None,
        rules_applied=["structured_prompt_mode"],
    )

    response = client.get(f"/shots/{shot_id}/explain")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "structured_prompt"
    assert data["subject_summary"] == "structured_prompt (unparsed)"
    assert "structured_prompt_parse_failed" in data["rules_applied"]


def test_explain_internal_shot_mode(client):
    """Test explain endpoint with internal shot format."""
    shot_id = "test-internal-shot-001"

    shot_json = {
        "shot_id": shot_id,
        "subject": "Test product",
        "camera": {
            "fov": 50,
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

    create_shot_version(
        shot_id=shot_id,
        json_payload=shot_json,
        parent_hash=None,
        batch_id=None,
        rules_applied=["manual_shot_payload"],
    )

    response = client.get(f"/shots/{shot_id}/explain")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "internal_shot"
    assert data["subject_summary"] == "Test product"
    assert "camera.fov" in data["derived_parameters"]
    assert data["derived_parameters"]["camera.fov"] == 50
