"""FIBO provider interface and implementations."""

import time
from typing import Dict, Protocol
import requests
from .config import (
    FIBO_PROVIDER,
    FIBO_API_BASE,
    FIBO_API_KEY,
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
        self.timeout = FIBO_TIMEOUT_SECONDS

    def render(self, shot_json: Dict) -> Dict:
        """
        Call Bria FIBO API to render a shot.

        TODO: Verify exact endpoint path and request/response format
        from Bria FIBO API documentation.
        """
        if not self.api_key:
            raise ValueError("FIBO_API_KEY is required for Bria provider")

        # TODO: Update endpoint path based on actual FIBO API docs
        endpoint = f"{self.api_base}/v2/fibo/render"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                endpoint,
                json=shot_json,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Parse response - try multiple possible formats
            url = None
            if "output_url" in data:
                url = data["output_url"]
            elif "data" in data and isinstance(data["data"], list):
                if len(data["data"]) > 0 and "url" in data["data"][0]:
                    url = data["data"][0]["url"]
            elif "url" in data:
                url = data["url"]

            if not url:
                # Store entire response in raw for debugging
                raise ValueError(
                    f"Could not find URL in response: {data}"
                )

            return {
                "url": url,
                "raw": data,
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"FIBO API request failed: {str(e)}")


def get_provider() -> FiboProvider:
    """Get the configured FIBO provider."""
    if FIBO_PROVIDER == "bria":
        return BriaFiboProvider()
    return MockProvider()

