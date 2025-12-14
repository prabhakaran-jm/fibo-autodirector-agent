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

2. Ensure you have a `.env` file in the project root (or `apps/api`) with:
   ```
   FIBO_API_KEY=your_key_here
   FIBO_API_BASE=https://api.bria.ai
   ```

## Test Commands

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
  -F "file=@../../data/samples/products.csv"
```

Expected response:
```json
{"batch_id":"<uuid>","count":3}
```

Save the `batch_id` for the next step.

### 3. Plan (Expand to Shots)
```bash
# Without preset
curl -X POST "http://localhost:8000/plan?batch_id=<BATCH_ID>"

# With preset
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
    {"shot_id": "PROD-001", "hash": "<hash>", "subject": "Wireless Headphones"},
    {"shot_id": "PROD-002", "hash": "<hash>", "subject": "Macro Camera Lens"},
    {"shot_id": "PROD-003", "hash": "<hash>", "subject": "Ceramic Coffee Mug"}
  ]
}
```

### 5. Get Full Shot
```bash
curl http://localhost:8000/shots/PROD-001
```

Expected response: Full shot JSON with all fields.

### 6. Render (Stub)
```bash
curl -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '["PROD-001", "PROD-002"]'
```

Expected response:
```json
{
  "renders": [
    {"shot_id": "PROD-001", "cached": false, "url": "mock://render/PROD-001"},
    {"shot_id": "PROD-002", "cached": false, "url": "mock://render/PROD-002"}
  ]
}
```

## Complete Test Flow

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Ingest
BATCH_ID=$(curl -s -X POST "http://localhost:8000/ingest/csv" \
  -F "file=@../../data/samples/products.csv" | jq -r '.batch_id')

# 3. Plan
curl -X POST "http://localhost:8000/plan?batch_id=$BATCH_ID&preset_id=brand_neutral_cool"

# 4. List shots
curl http://localhost:8000/shots

# 5. Get one shot
curl http://localhost:8000/shots/PROD-001

# 6. Render
curl -X POST "http://localhost:8000/render" \
  -H "Content-Type: application/json" \
  -d '["PROD-001", "PROD-002", "PROD-003"]'
```

