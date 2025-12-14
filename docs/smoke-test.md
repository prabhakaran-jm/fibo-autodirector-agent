# Smoke Test Guide

This document provides curl commands to test the FIBO AutoDirector Agent API.

## Prerequisites

1. Start the API server:
   ```bash
   cd apps/api
   # After pip install -e ., you can use:
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   # Or without installation:
   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Ensure you have a `.env` file in the project root with:
   ```
   FIBO_PROVIDER=mock
   FIBO_API_KEY=your_key_here
   FIBO_API_BASE=https://api.bria.ai
   ```

## Flow 1: Mock Provider (Default - No External API Required)

### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### 2. Ingest CSV
```bash
curl -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv"
```

Expected response:
```json
{"batch_id":"<uuid>","count":3}
```

Save the `batch_id` for the next step.

### 3. Plan (Expand to Shots)
```bash
curl -X POST "http://localhost:8000/plan?batch_id=<BATCH_ID>&preset_id=brand_neutral_cool"
```

Expected response:
```json
{"planned":3}
```

### 4. List Shots
```bash
curl http://localhost:8000/shots
```

Expected response:
```json
{
  "shots": [
    {
      "shot_id": "PROD-001",
      "hash": "<hash>",
      "subject": "Wireless Headphones",
      "status": "queued",
      "artifact_url": null
    },
    ...
  ]
}
```

### 5. Render Async (Enqueue Job)
```bash
curl -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001", "PROD-002", "PROD-003"]}'
```

Expected response:
```json
{"job_id":"<uuid>","queued":3}
```

Save the `job_id` for the next step.

### 6. Poll Job Status
```bash
curl http://localhost:8000/jobs/<JOB_ID>
```

Expected response (while running):
```json
{
  "job_id": "<uuid>",
  "status": "running",
  "progress": {"completed": 1, "total": 3},
  "results": [
    {
      "shot_id": "PROD-001",
      "cached": false,
      "status": "done",
      "url": "mock://PROD-001/<hash>.png",
      "hash": "<hash>"
    }
  ]
}
```

Expected response (when done):
```json
{
  "job_id": "<uuid>",
  "status": "done",
  "progress": {"completed": 3, "total": 3},
  "results": [
    {
      "shot_id": "PROD-001",
      "cached": false,
      "status": "done",
      "url": "mock://PROD-001/<hash>.png",
      "hash": "<hash>"
    },
    ...
  ]
}
```

### 7. Verify Shot Artifact URL
```bash
curl http://localhost:8000/shots/PROD-001
```

Expected response should include:
```json
{
  "shot_id": "PROD-001",
  "status": "done",
  "artifact_url": "mock://PROD-001/<hash>.png",
  "duration_ms": <number>,
  ...
}
```

### 8. Render Sync (Alternative for Small Demos)
```bash
curl -X POST "http://localhost:8000/render/sync" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001"]}'
```

Expected response:
```json
{
  "renders": [
    {
      "shot_id": "PROD-001",
      "cached": true,
      "status": "done",
      "url": "mock://PROD-001/<hash>.png",
      "hash": "<hash>"
    }
  ]
}
```

## Flow 2: Bria Provider (Real FIBO API)

### Setup
1. Update `.env` file:
   ```
   FIBO_PROVIDER=bria
   FIBO_API_KEY=your_actual_bria_api_key
   FIBO_API_BASE=https://api.bria.ai
   ```

2. Restart the API server.

### Test with Sync Render (Single Shot)
```bash
# 1. Ingest and plan (same as Flow 1)
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv" | jq -r '.batch_id')

curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID"

# 2. Render one shot synchronously
curl -X POST "http://localhost:8000/render/sync" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001"]}'
```

Expected response (if API key is valid):
```json
{
  "renders": [
    {
      "shot_id": "PROD-001",
      "cached": false,
      "status": "done",
      "url": "https://...",
      "hash": "<hash>"
    }
  ]
}
```

## Complete Mock Flow (Copy-Paste Ready)

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Ingest
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv" | jq -r '.batch_id')
echo "Batch ID: $BATCH_ID"

# 3. Plan
curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID&preset_id=brand_neutral_cool"

# 4. List shots
curl http://localhost:8000/shots

# 5. Render async
JOB_ID=$(curl -s -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001", "PROD-002", "PROD-003"]}' | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 6. Poll job (wait a moment, then check)
sleep 2
curl http://localhost:8000/jobs/$JOB_ID

# 7. Verify shot has artifact_url
curl http://localhost:8000/shots/PROD-001 | jq '.artifact_url'
```

## Notes

- Mock provider works without any external API access
- Cached renders return immediately with `cached: true`
- Job status can be `queued`, `running`, `done`, or `failed`
- Shot status tracks: `queued`, `running`, `done`, `failed`
- Artifact URLs are cached by hash for reproducibility
