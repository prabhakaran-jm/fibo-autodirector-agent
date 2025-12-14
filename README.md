# FIBO AutoDirector Agent

FIBO AutoDirector Agent turns structured inputs (CSV, storyboards, specs)
into deterministic, controllable visual outputs using Bria FIBO’s
JSON-native generation.

Instead of prompt engineering, every image is generated from explicit,
reproducible parameters: camera, lens, lighting, color, and composition.

## Why FIBO

FIBO (Functional Image Block Object) is Bria's JSON-native image generation format. Instead of text prompts, FIBO uses explicit, structured parameters:

- **Camera**: position, rotation, field of view
- **Lens**: aperture, focal length
- **Lighting**: key light, rim light, intensity, position
- **Color**: palette, background hex
- **Output**: width, height

This enables **deterministic, reproducible, controllable** image generation.

## Why JSON Beats Prompts

| Prompts | JSON |
|---------|------|
| "A glossy product shot" | `{"lighting": {"key_light": {"intensity": 0.7}}}` |
| Drifts between runs | Same JSON → same hash → same output |
| Unpredictable | Explicit parameters |
| Hard to version | Easy to patch and compare |
| Not auditable | Full lineage tracking |

**Result**: Enterprise-scale, auditable, reproducible creative workflows.

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

## Judge Quick Start (3 Commands)

Try these first to see the core value:

```bash
# 1. Health check - see system status
curl http://localhost:8000/health

# 2. Explain a shot - see how it was generated (no prompts!)
curl "http://localhost:8000/shots/PROD-001/explain"

# 3. Metrics - see system performance
curl http://localhost:8000/metrics
```

Then run the full workflow from [Judge Workflow](#judge-workflow) below.

## Hackathon Category Fit

**Best JSON-Native or Agentic Workflow**
- JSON-first architecture (no prompts)
- Deterministic hashing for reproducibility
- Versioned creative decisions with lineage
- Explainable generation (rules tracking)

**Best Controllability**
- Explicit parameter control (camera, lens, lighting)
- JSON patch rerendering
- Version comparison
- Exportable, auditable bundles

## Status
Production-ready backend with full workflow support.

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
   FIBO_API_BASE=https://engine.prod.bria-api.com
   FIBO_API_ENDPOINT=/v2/image/generate
   
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

The API supports a complete review and iteration workflow. This demonstrates the core value proposition: **deterministic, versioned, explainable image generation**.

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

### Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - System design and key decisions
- **[Smoke Test](docs/smoke-test.md)** - Complete curl-based test commands

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

## Real Bria FIBO Output (Proof)

See `docs/real-fibo-example/` for:
- the exact request/response
- the structured prompt used
- the downloaded output image

