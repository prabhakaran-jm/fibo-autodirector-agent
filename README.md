# FIBO AutoDirector Agent

FIBO AutoDirector Agent turns structured inputs (CSV, storyboards, specs)
into deterministic, controllable visual outputs using Bria FIBO’s
JSON-native generation.

Instead of prompt engineering, every image is generated from explicit,
reproducible parameters: camera, lens, lighting, color, and composition.

## Why this exists
Creative teams need scale and consistency.
Text prompts drift.
AutoDirector makes visual generation predictable and repeatable.

## What it does
- Ingests structured inputs (CSV or JSON)
- Expands them into FIBO-compliant JSON
- Generates images with strict parameter control
- Caches outputs by JSON hash for reproducibility
- Allows selective re-rendering with parameter diffs

## Built with
- Bria FIBO (JSON-native generation)
- Agent-based planning layer
- FastAPI backend
- Web UI for review and comparison

## References
- FIBO API Docs: https://docs.bria.ai/
- FIBO Platform Console: https://platform.bria.ai/
- FIBO Overview: https://bria.ai/fibo

## Status
Early scaffold – core ingestion and planning in progress.

## Backend Quickstart

### Prerequisites

- Python 3.10+
- pip or uv

### Setup

1. Install dependencies:
   ```bash
   cd apps/api
   pip install -e .
   ```

2. Create `.env` file in project root:
   ```
   FIBO_API_KEY=your_key_here
   FIBO_API_BASE=https://api.bria.ai
   ```

3. Run the API server:
   ```bash
   cd apps/api
   # After pip install -e ., you can use:
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   # Or without installation:
   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Test the API:
   ```bash
   curl http://localhost:8000/health
   ```

### Smoke Test

See [docs/smoke-test.md](docs/smoke-test.md) for complete curl-based smoke test commands.

Quick test flow:
```bash
# Ingest CSV
curl -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv"

# Plan (use batch_id from above)
curl -X POST "http://localhost:8000/plan?batch_id=<BATCH_ID>"

# List shots
curl http://localhost:8000/shots

# Get a shot
curl http://localhost:8000/shots/PROD-001

# Render (stub)
curl -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001"]}'
```