"""FIBO provider interface and implementations."""

import json
from typing import Dict, Protocol
import requests
from .config import (
    FIBO_PROVIDER,
    FIBO_API_BASE,
    FIBO_API_KEY,
    FIBO_API_ENDPOINT,
    FIBO_TIMEOUT_SECONDS,
)
from .hashutil import hash_shot


class FiboProvider(Protocol):
    """Protocol for FIBO providers."""

    def render(self, shot_json: Dict) -> Dict:
        """
        Render a shot and return result.

        Returns:
            dict with keys: "url" (str), "raw" (dict)
        """
        ...


class MockProvider:
    """Mock provider that returns deterministic mock URLs."""

    def render(self, shot_json: Dict) -> Dict:
        """Return a deterministic mock URL based on shot hash."""
        shot_id = shot_json.get("shot_id", "unknown")
        shot_hash = hash_shot(shot_json)
        url = f"mock://{shot_id}/{shot_hash}.png"
        return {
            "url": url,
            "raw": {"provider": "mock", "shot_id": shot_id, "hash": shot_hash},
        }


class BriaFiboProvider:
    """Bria FIBO API provider."""

    def __init__(self):
        self.api_base = FIBO_API_BASE.rstrip("/")
        self.api_key = FIBO_API_KEY
        self.api_endpoint = FIBO_API_ENDPOINT
        self.timeout = FIBO_TIMEOUT_SECONDS

    def render(self, shot_json: Dict) -> Dict:
        """
        Call Bria FIBO API to render a shot.

        TODO: Verify exact endpoint path and request/response format
        from Bria FIBO API documentation at https://docs.bria.ai/
        """
        if not self.api_key:
            raise ValueError("FIBO_API_KEY is required for Bria provider")

        # Use configured endpoint, or try multiple possible patterns
        if self.api_endpoint:
            # Use the configured endpoint from env var
            endpoints_to_try = [f"{self.api_base}{self.api_endpoint}"]
        else:
            # Fallback: try multiple possible endpoint patterns
            endpoints_to_try = [
                f"{self.api_base}/v2/image/generate",  # Standard FIBO endpoint
                f"{self.api_base}/v2/generate",
                f"{self.api_base}/v2/render",
                f"{self.api_base}/api/v2/render",
                f"{self.api_base}/v2/fibo/render",
            ]

        # Use api_token header (per Bria docs: "api_token: <your_api_token>")
        # Try api_token first, then fallback to other formats
        auth_headers = [
            {"api_token": self.api_key},  # Primary format per Bria docs
            {"Authorization": f"Bearer {self.api_key}"},
            {"x-api-key": self.api_key},
        ]

        errors_tried = []
        for endpoint in endpoints_to_try:
            for headers_variant in auth_headers:
                headers = {
                    **headers_variant,
                    "Content-Type": "application/json",
                }
                auth_type = list(headers_variant.keys())[0]

                try:
                    # Build Bria FIBO API request
                    # structured_prompt must be a JSON string
                    structured_prompt_str = None

                    # Check if structured_prompt is provided directly
                    if "structured_prompt" in shot_json:
                        sp = shot_json["structured_prompt"]
                        if isinstance(sp, str):
                            structured_prompt_str = sp
                        elif isinstance(sp, dict):
                            structured_prompt_str = json.dumps(
                                sp, separators=(",", ":")
                            )
                    else:
                        # If no structured_prompt, use shot JSON itself
                        # (user might be passing structured_prompt format)
                        structured_prompt_str = json.dumps(
                            shot_json, separators=(",", ":")
                        )

                    # Build Bria API request payload
                    payload = {
                        "model_version": "FIBO",
                        "structured_prompt": structured_prompt_str,
                        "sync": True,
                    }

                    # Add aspect_ratio if provided in shot_json
                    if "output" in shot_json:
                        width = shot_json["output"].get("width", 1024)
                        height = shot_json["output"].get("height", 1024)
                        if width == height:
                            payload["aspect_ratio"] = "1:1"
                        elif width > height:
                            payload["aspect_ratio"] = f"{width//height}:1"
                        else:
                            payload["aspect_ratio"] = f"1:{height//width}"
                    else:
                        # Default to 1:1 if not specified
                        payload["aspect_ratio"] = "1:1"

                    response = requests.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Handle async response (request_id + status_url)
                    if "request_id" in data and "status_url" in data:
                        # Async response - for now, raise helpful error
                        raise ValueError(
                            f"Async response received. "
                            f"Request ID: {data.get('request_id')}, "
                            f"Status URL: {data.get('status_url')}. "
                            f"Async polling not yet implemented. "
                            f"Response: {data}"
                        )

                    # Parse sync response - Bria returns result.image_url
                    url = None
                    if "result" in data and "image_url" in data.get(
                        "result", {}
                    ):
                        url = data["result"]["image_url"]
                    elif "output_url" in data:
                        url = data["output_url"]
                    elif "data" in data and isinstance(data["data"], list):
                        if len(data["data"]) > 0 and "url" in data["data"][0]:
                            url = data["data"][0]["url"]
                    elif "url" in data:
                        url = data["url"]
                    elif "image_url" in data:
                        url = data["image_url"]

                    if not url:
                        # Store entire response in raw for debugging
                        raise ValueError(
                            f"Could not find URL in response: {data}"
                        )

                    return {
                        "url": url,
                        "raw": data,
                    }
                except requests.exceptions.HTTPError as e:
                    error_msg = (
                        f"{endpoint} (auth: {auth_type}) → "
                        f"HTTP {e.response.status_code}"
                    )
                    if e.response.status_code == 404:
                        errors_tried.append(error_msg)
                        continue
                    else:
                        # Other HTTP error, might be auth or format issue
                        errors_tried.append(
                            f"{error_msg}: {e.response.text[:200]}"
                        )
                        continue
                except requests.exceptions.RequestException as e:
                    errors_tried.append(
                        f"{endpoint} (auth: {auth_type}) → {str(e)[:200]}"
                    )
                    continue

        # If we get here, all attempts failed
        error_summary = (
            "\n  - ".join(errors_tried)
            if errors_tried
            else "No endpoints tried"
        )
        raise ValueError(
            f"FIBO API request failed. Tried:\n  - {error_summary}\n\n"
            f"Please set FIBO_API_ENDPOINT in .env to the correct path.\n"
            f"Check https://docs.bria.ai/ for the FIBO-specific endpoint."
        )


def get_provider() -> FiboProvider:
    """Get the configured FIBO provider."""
    if FIBO_PROVIDER == "bria":
        return BriaFiboProvider()
    return MockProvider()
