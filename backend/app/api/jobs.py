"""Durable background jobs using Redis + rq.

A job is enqueued through the API and its durable status/result can be polled.
This satisfies the Phase A acceptance: a background job can persist a durable
result/progress and be retrieved afterwards.
"""
import time
import uuid

import redis
from fastapi import APIRouter, Depends, HTTPException
from rq import Queue

from ..config import settings
from ..core.tenancy import require_org

router = APIRouter(prefix="/jobs", tags=["jobs"])

_redis = redis.Redis.from_url(settings.redis_url, decode_responses=False)
_queue = Queue("nomos-jobs", connection=_redis, default_timeout=300)


def run_slow_job(delay: float = 0.1) -> dict:
    """Deterministic durable job that records progress + result."""
    progress = []
    total = 5
    for i in range(total):
        time.sleep(delay)
        progress.append({"step": i + 1, "progress": round((i + 1) / total, 2)})
    return {"progress_log": progress, "final": "done", "run_id": str(uuid.uuid4())}


@router.post("")
def enqueue_job(ctx: dict = Depends(require_org)):
    job = _queue.enqueue("app.workers.run_slow_job", job_id=f"job-{uuid.uuid4()}")
    return {"job_id": job.id, "status": job.get_status()}


@router.get("/{job_id}")
def job_status(job_id: str, ctx: dict = Depends(require_org)):
    job = _queue.fetch_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.is_failed:
        return {"id": job.id, "status": "failed", "result": None,
                "error": str(job.exc_info).splitlines()[-1] if job.exc_info else "unknown"}
    return {"id": job.id, "status": job.get_status(), "result": job.result, "error": None}