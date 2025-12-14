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
   # Provider selection: "mock" (default) or "bria"
   FIBO_PROVIDER=mock
   
   # Required only for Bria provider
   FIBO_API_KEY=your_key_here
   FIBO_API_BASE=https://api.bria.ai
   
   # Optional: timeout and concurrency
   FIBO_TIMEOUT_SECONDS=120
   FIBO_CONCURRENCY=2
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

### Provider Selection

The API supports two providers:

- **Mock Provider** (default): Returns deterministic mock URLs without calling external APIs. Perfect for testing and development.
- **Bria Provider**: Calls the real Bria FIBO API. Requires `FIBO_API_KEY` and `FIBO_API_BASE` in `.env`.

Set `FIBO_PROVIDER=mock` or `FIBO_PROVIDER=bria` in your `.env` file.

### Rendering

The API supports two rendering modes:

1. **Async Rendering** (recommended for batches):
   - POST `/render` enqueues a job and returns immediately
   - Use GET `/jobs/{job_id}` to poll for progress
   - Jobs are processed by a background worker with configurable concurrency

2. **Sync Rendering** (for small demos):
   - POST `/render/sync` renders in the request thread
   - Still uses caching for performance
   - Returns results immediately

### Caching

Renders are cached by deterministic JSON hash. Re-rendering the same shot JSON returns the cached artifact URL immediately with `cached: true`.

### Judge Workflow

The API supports a complete review and iteration workflow:

1. **Ingest** → Upload CSV with product data
2. **Plan** → Expand rows into FIBO shot JSON
3. **Render** → Generate images (async or sync)
4. **Approve/Reject** → Review shots with optional notes
5. **Rerender** → Create new version with JSON patch
6. **Compare** → View differences between versions
7. **Export** → Download bundle (manifest, report, images)

Example workflow:
```bash
# Ingest and plan
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv" | jq -r '.batch_id')
curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID"

# Render
JOB_ID=$(curl -s -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001"]}' | jq -r '.job_id')

# Approve
curl -X POST "http://localhost:8000/shots/PROD-001/approve" \
  -H "Content-Type: application/json" \
  -d '{"note": "Approved"}'

# Rerender with patch
curl -X POST "http://localhost:8000/shots/PROD-001/rerender" \
  -H "Content-Type: application/json" \
  -d '{"json_patch": {"camera": {"fov": 60}}}'

# Export
curl -X POST "http://localhost:8000/export/batch/$BATCH_ID"
curl "http://localhost:8000/export/batch/$BATCH_ID/download" -o batch.zip
```

### Smoke Test

See [docs/smoke-test.md](docs/smoke-test.md) for complete curl-based smoke test commands.

Quick test flow (Mock Provider - no API key required):
```bash
# Ingest CSV
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv" | jq -r '.batch_id')

# Plan
curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID&preset_id=brand_neutral_cool"

# List shots
curl http://localhost:8000/shots

# Render async
JOB_ID=$(curl -s -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001", "PROD-002", "PROD-003"]}' | jq -r '.job_id')

# Poll job status
curl http://localhost:8000/jobs/$JOB_ID

# Verify shot has artifact_url
curl http://localhost:8000/shots/PROD-001
```