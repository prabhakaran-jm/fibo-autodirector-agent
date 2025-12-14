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

### Test with Raw Shot JSON (No Planning Required)
```bash
# Render a raw FIBO JSON payload directly (Bria proof)
curl -X POST "http://localhost:8000/render/shot/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "shot": {
      "shot_id": "CUSTOM-001",
      "subject": "Custom Product Shot",
      "camera": {
        "fov": 50,
        "position": {"x": 0, "y": 0, "z": 5},
        "rotation": {"x": 0, "y": 0, "z": 0}
      },
      "lens": {
        "aperture": 2.8,
        "focal_length": 50
      },
      "lighting": {
        "key_light": {
          "intensity": 1.0,
          "position": {"x": 2, "y": 3, "z": 4}
        },
        "rim_light": {
          "intensity": 0.5,
          "position": {"x": -2, "y": 2, "z": 3}
        }
      },
      "color": {
        "palette": ["#ffffff", "#000000"]
      },
      "background": {
        "hex": "#f5f5f5"
      },
      "output": {
        "width": 1024,
        "height": 1024
      }
    },
    "preset_id": "brand_neutral_cool"
  }'
```

Expected response:
```json
{
  "shot_id": "CUSTOM-001",
  "hash": "<hash>",
  "cached": false,
  "url": "https://...",
  "provider": "bria"
}
```

After rendering, you can use standard endpoints:
```bash
# Get the shot
curl "http://localhost:8000/shots/CUSTOM-001"

# Explain how it was generated
curl "http://localhost:8000/shots/CUSTOM-001/explain"
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

## Flow 3: Review and Rerender Workflow

### 1. Approve a Shot
```bash
# Approve latest version (no admin token required if ADMIN_TOKEN not set)
curl -X POST "http://localhost:8000/shots/PROD-001/approve" \
  -H "Content-Type: application/json" \
  -d '{"note": "Looks good!"}'
```

Expected response:
```json
{
  "shot_id": "PROD-001",
  "version": 1,
  "review_status": "approved",
  "review_note": "Looks good!"
}
```

### 2. Patch and Rerender
```bash
# Create new version with JSON patch
curl -X POST "http://localhost:8000/shots/PROD-001/rerender" \
  -H "Content-Type: application/json" \
  -d '{
    "json_patch": {
      "camera": {
        "fov": 60
      },
      "lighting": {
        "key_light": {
          "intensity": 0.8
        }
      }
    }
  }'
```

Expected response:
```json
{
  "job_id": "<uuid>",
  "shot_id": "PROD-001",
  "version": 2,
  "hash": "<new_hash>"
}
```

### 3. Compare Versions
```bash
# Compare version 1 vs version 2
curl "http://localhost:8000/shots/PROD-001/compare?from=1&to=2"
```

Expected response:
```json
{
  "shot_id": "PROD-001",
  "from_version": 1,
  "to_version": 2,
  "changes": [
    {
      "path": "camera.fov",
      "old_value": 45,
      "new_value": 60
    },
    {
      "path": "lighting.key_light.intensity",
      "old_value": 1.0,
      "new_value": 0.8
    }
  ]
}
```

### 4. List Versions
```bash
curl "http://localhost:8000/shots/PROD-001/versions"
```

Expected response:
```json
{
  "shot_id": "PROD-001",
  "versions": [
    {
      "version": 1,
      "hash": "<hash>",
      "status": "done",
      "artifact_url": "mock://...",
      "created_at": "...",
      "parent_hash": null,
      "review_status": "approved"
    },
    {
      "version": 2,
      "hash": "<new_hash>",
      "status": "done",
      "artifact_url": "mock://...",
      "created_at": "...",
      "parent_hash": "<hash>",
      "review_status": "pending"
    }
  ]
}
```

## Flow 4: Export and Download

### 1. Export Batch
```bash
# Export manifest and report to disk
curl -X POST "http://localhost:8000/export/batch/$BATCH_ID"
```

Expected response:
```json
{
  "batch_id": "<batch_id>",
  "paths": {
    "manifest": "artifacts/<batch_id>/manifest.json",
    "report": "artifacts/<batch_id>/report.json"
  },
  "message": "Export completed"
}
```

### 2. Get Manifest
```bash
curl "http://localhost:8000/export/batch/$BATCH_ID/manifest"
```

### 3. Download Zip
```bash
# Download complete bundle as zip
curl "http://localhost:8000/export/batch/$BATCH_ID/download" \
  -o batch_export.zip
```

The zip contains:
- `manifest.json` - shot metadata
- `report.json` - batch statistics
- `images/` - folder with images (mock provider) or `urls.txt` (bria provider)

## Complete Judge Workflow (Copy-Paste Ready)

```bash
# 1. Ingest and plan
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@data/samples/products.csv" | jq -r '.batch_id')

curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID&preset_id=brand_neutral_cool"

# 2. Render
JOB_ID=$(curl -s -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '{"shot_ids": ["PROD-001", "PROD-002", "PROD-003"]}' | jq -r '.job_id')

# 3. Wait for completion
sleep 3
curl "http://localhost:8000/jobs/$JOB_ID"

# 4. Approve a shot
curl -X POST "http://localhost:8000/shots/PROD-001/approve" \
  -H "Content-Type: application/json" \
  -d '{"note": "Approved"}'

# 5. Rerender with patch
curl -X POST "http://localhost:8000/shots/PROD-002/rerender" \
  -H "Content-Type: application/json" \
  -d '{"json_patch": {"camera": {"fov": 60}}}'

# 6. Compare versions
curl "http://localhost:8000/shots/PROD-002/compare?from=1&to=2"

# 7. Export and download
curl -X POST "http://localhost:8000/export/batch/$BATCH_ID"
curl "http://localhost:8000/export/batch/$BATCH_ID/download" -o batch.zip
```

## Notes

- Mock provider works without any external API access
- Cached renders return immediately with `cached: true`
- Job status can be `queued`, `running`, `done`, or `failed`
- Shot status tracks: `queued`, `running`, `done`, `failed`
- Artifact URLs are cached by hash for reproducibility
- Shot versioning allows multiple iterations with JSON patches
- Review workflow supports approve/reject with optional notes
- Export creates downloadable zip with manifest, report, and images
