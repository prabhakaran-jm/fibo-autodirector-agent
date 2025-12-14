"""FastAPI application entry point."""

import time
from fastapi import FastAPI

from .routes import router
from .worker import start_worker

# Track startup time for uptime calculation
_start_time = time.time()

app = FastAPI(
    title="FIBO AutoDirector Agent API",
    description="Backend API for FIBO AutoDirector Agent",
    version="0.1.0",
)

app.include_router(router)

# Start worker on startup
start_worker(app)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FIBO AutoDirector Agent API",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """Health check endpoint with system status."""
    from .storage import (
        _shot_versions,
        _jobs,
        _artifacts_by_hash,
    )
    from .config import FIBO_PROVIDER

    uptime = int(time.time() - _start_time)
    shots_count = len(_shot_versions)
    jobs_count = len(_jobs)
    artifacts_count = len(_artifacts_by_hash)

    return {
        "status": "ok",
        "provider": FIBO_PROVIDER,
        "uptime_seconds": uptime,
        "shots": shots_count,
        "jobs": jobs_count,
        "artifacts": artifacts_count,
    }


@app.get("/metrics")
async def metrics():
    """System metrics endpoint."""
    from .storage import (
        _batches,
        _shot_versions,
        _jobs,
        _artifacts_by_hash,
        _batch_cache_hits,
    )

    # Count shots by status
    shots_total = 0
    shots_done = 0
    shots_failed = 0
    render_times = []

    for versions in _shot_versions.values():
        for version in versions:
            shots_total += 1
            if version["status"] == "done":
                shots_done += 1
                if version.get("duration_ms"):
                    render_times.append(version["duration_ms"])
            elif version["status"] == "failed":
                shots_failed += 1

    # Count cache hits
    cache_hits = sum(_batch_cache_hits.values())

    # Count renders executed (non-cached)
    renders_executed = shots_done - cache_hits

    # Calculate average render time
    avg_render_ms = (
        int(sum(render_times) / len(render_times)) if render_times else 0
    )

    return {
        "batches": len(_batches),
        "shots_total": shots_total,
        "shots_done": shots_done,
        "shots_failed": shots_failed,
        "cache_hits": cache_hits,
        "renders_executed": renders_executed,
        "avg_render_ms": avg_render_ms,
    }
