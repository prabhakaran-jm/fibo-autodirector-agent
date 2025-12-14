"""Configuration from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from project root
project_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(project_root / ".env")

# FIBO Provider selection
FIBO_PROVIDER = os.getenv("FIBO_PROVIDER", "mock")

# Bria FIBO API configuration
FIBO_API_BASE = os.getenv("FIBO_API_BASE", "https://engine.prod.bria-api.com")
FIBO_API_KEY = os.getenv("FIBO_API_KEY", "")
FIBO_API_ENDPOINT = os.getenv(
    "FIBO_API_ENDPOINT", "/v2/image/generate"
)  # Default: /v2/image/generate (FIBO endpoint)

# Timeout and concurrency
FIBO_TIMEOUT_SECONDS = int(os.getenv("FIBO_TIMEOUT_SECONDS", "120"))
FIBO_CONCURRENCY = int(os.getenv("FIBO_CONCURRENCY", "2"))
