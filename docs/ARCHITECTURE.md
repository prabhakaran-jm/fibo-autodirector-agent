# Architecture

## Overview

FIBO AutoDirector Agent is a JSON-first, deterministic image generation pipeline built on Bria FIBO. Instead of prompt engineering, every image is generated from explicit, reproducible parameters: camera, lens, lighting, color, and composition.

## Flow

```
CSV / Storyboard
  → Planning Agent (expand_record_to_shot)
  → FIBO JSON
  → Hash & Cache (deterministic SHA256)
  → Render Provider (mock or bria)
  → Review (approve/reject)
  → Export Bundle (manifest, report, images)
```

## Key Design Choices

### JSON-Native Generation
- **No prompts**: Every parameter is an explicit JSON field
- **No drift**: Same JSON → same hash → same output
- **Versioned**: Track changes with parent_hash lineage

### Deterministic Hashing
- SHA256 hash of normalized JSON (sorted keys, consistent formatting)
- Cache by hash for reproducibility
- Same shot JSON always produces same artifact URL

### Provider Abstraction
- **Mock Provider**: Deterministic mock URLs for testing (no external API)
- **Bria Provider**: Real FIBO API integration
- Switch via `FIBO_PROVIDER` environment variable

### Async Job Queue
- In-memory asyncio.Queue for render jobs
- Background worker with configurable concurrency
- Non-blocking API responses

### Versioned Shots
- Multiple versions per shot_id
- Track parent_hash for lineage
- Store rules_applied for explainability
- Review workflow (approve/reject) per version

## Why This Matters

This architecture enables:
- **Enterprise-scale**: Batch processing with async jobs
- **Auditable**: Every decision tracked in version history
- **Reproducible**: Deterministic hashing ensures consistency
- **Controllable**: JSON parameters instead of unpredictable prompts
- **Explainable**: Rules and patches tracked for transparency

## Storage

All data is stored in-memory (dicts) for simplicity:
- `_batches`: CSV ingestion batches
- `_shot_versions`: Versioned shot storage
- `_artifacts_by_hash`: Cache by hash
- `_jobs`: Render job queue state

Export functionality writes to disk under `artifacts/{batch_id}/` for persistence.

## API Endpoints

### Core Workflow
- `POST /ingest/csv` - Upload CSV, get batch_id
- `POST /plan` - Expand rows to FIBO JSON shots
- `POST /render` - Enqueue render job (async)
- `GET /jobs/{job_id}` - Check job progress

### Review & Iteration
- `POST /shots/{shot_id}/approve` - Approve version
- `POST /shots/{shot_id}/rerender` - Create new version with patch
- `GET /shots/{shot_id}/versions` - List all versions
- `GET /shots/{shot_id}/compare` - Compare two versions
- `GET /shots/{shot_id}/explain` - Explain how shot was generated

### Export
- `POST /export/batch/{batch_id}` - Write manifest and report
- `GET /export/batch/{batch_id}/download` - Download zip bundle

### Observability
- `GET /health` - System status
- `GET /metrics` - Performance metrics

