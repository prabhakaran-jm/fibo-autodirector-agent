"""Async worker for processing render jobs."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from fastapi import FastAPI

from .storage import (
    get_shot_latest_version,
    get_artifact_by_hash,
    save_artifact_by_hash,
    update_shot_status,
    update_shot_version_status,
    get_job,
    update_job,
    increment_batch_cache_hits,
)
from .fibo_provider import get_provider
from .config import FIBO_CONCURRENCY
from .hashutil import hash_shot

# Global job queue
_job_queue: asyncio.Queue = asyncio.Queue()

# Semaphore for concurrency control
_semaphore = asyncio.Semaphore(FIBO_CONCURRENCY)

# Thread pool executor for blocking I/O (provider.render calls)
_executor = ThreadPoolExecutor(max_workers=FIBO_CONCURRENCY)


async def enqueue_render_job(job_id: str) -> None:
    """Add a job to the render queue."""
    await _job_queue.put(job_id)


async def _render_shot(
    shot_id: str, provider, version: Optional[int] = None
) -> Dict:
    """Render a single shot (or specific version)."""
    # Get shot - use version if specified, otherwise latest
    if version:
        from .storage import get_shot_version as get_version
        version_obj = get_version(shot_id, version)
        if not version_obj:
            return {
                "shot_id": shot_id,
                "cached": False,
                "status": "failed",
                "error": f"Shot {shot_id} version {version} not found",
                "hash": "",
            }
        shot = version_obj["json_payload"]
        batch_id = version_obj.get("batch_id")
    else:
        shot = get_shot_latest_version(shot_id)
        if not shot:
            return {
                "shot_id": shot_id,
                "cached": False,
                "status": "failed",
                "error": f"Shot {shot_id} not found",
                "hash": "",
            }
        # Get batch_id from latest version
        from .storage import get_shot_versions
        versions = get_shot_versions(shot_id)
        batch_id = None
        if versions:
            latest_v = max(versions, key=lambda v: v["version"])
            batch_id = latest_v.get("batch_id")

    shot_hash = shot.get("hash") or hash_shot(shot)
    start_time = time.time()

    # Check cache first
    cached_artifact = get_artifact_by_hash(shot_hash)
    if cached_artifact:
        duration_ms = int((time.time() - start_time) * 1000)
        if version:
            update_shot_version_status(
                shot_id,
                version,
                "done",
                artifact_url=cached_artifact["url"],
                duration_ms=duration_ms,
            )
        else:
            update_shot_status(
                shot_id,
                "done",
                artifact_url=cached_artifact["url"],
                duration_ms=duration_ms,
            )
        
        # Track cache hit
        if batch_id:
            increment_batch_cache_hits(batch_id)
        
        return {
            "shot_id": shot_id,
            "cached": True,
            "status": "done",
            "url": cached_artifact["url"],
            "hash": shot_hash,
        }

    # Render with provider (run in executor to avoid blocking event loop)
    try:
        if version:
            update_shot_version_status(shot_id, version, "running")
        else:
            update_shot_status(shot_id, "running")
        
        # Run blocking provider.render in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, provider.render, shot)
        url = result["url"]
        raw = result.get("raw", {})

        # Save to cache
        provider_name = "mock" if "mock://" in url else "bria"
        save_artifact_by_hash(shot_hash, url, provider_name, raw)

        duration_ms = int((time.time() - start_time) * 1000)
        if version:
            update_shot_version_status(
                shot_id, version, "done", artifact_url=url, duration_ms=duration_ms
            )
        else:
            update_shot_status(
                shot_id, "done", artifact_url=url, duration_ms=duration_ms
            )

        return {
            "shot_id": shot_id,
            "cached": False,
            "status": "done",
            "url": url,
            "hash": shot_hash,
        }
    except Exception as e:
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        if version:
            update_shot_version_status(
                shot_id,
                version,
                "failed",
                last_error=error_msg,
                duration_ms=duration_ms,
            )
        else:
            update_shot_status(
                shot_id,
                "failed",
                last_error=error_msg,
                duration_ms=duration_ms,
            )
        return {
            "shot_id": shot_id,
            "cached": False,
            "status": "failed",
            "error": error_msg,
            "hash": shot_hash,
        }


async def _process_job(job_id: str) -> None:
    """Process a single render job."""
    job = get_job(job_id)
    if not job:
        return

    update_job(job_id, status="running")
    shot_ids = job["shot_ids"]
    shot_versions = job.get("shot_versions", {})
    provider = get_provider()
    results: List[Dict] = []

    # Process shots with concurrency control
    async def render_with_semaphore(shot_id: str):
        async with _semaphore:
            version = shot_versions.get(shot_id)
            return await _render_shot(shot_id, provider, version=version)

    tasks = [render_with_semaphore(shot_id) for shot_id in shot_ids]
    results = await asyncio.gather(*tasks)

    # Update job with results
    update_job(
        job_id,
        status="done",
        progress={"completed": len(results), "total": len(shot_ids)},
        results=results,
    )


async def _worker_loop() -> None:
    """Main worker loop that processes jobs from the queue."""
    while True:
        try:
            job_id = await _job_queue.get()
            await _process_job(job_id)
            _job_queue.task_done()
        except Exception as e:
            # Log error but continue processing
            print(f"Worker error processing job: {e}")


def start_worker(app: FastAPI) -> None:
    """Start the worker on FastAPI startup."""

    @app.on_event("startup")
    async def startup_event():
        """Start worker loop on startup."""
        asyncio.create_task(_worker_loop())

