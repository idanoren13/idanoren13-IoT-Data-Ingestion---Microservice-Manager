"""Part 2 – Worker microservice management endpoints."""

import logging

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from redis.asyncio import Redis

from app.models.worker import Worker, WorkerHealthUpdate, WorkerRegister, WorkerGetResponse
from app.redis_client import get_redis

logger = logging.getLogger("iot_platform")

router = APIRouter(prefix="/api/v1/workers", tags=["Workers"])

# ──────────────────────────────────────────────
# Redis key helpers
# ──────────────────────────────────────────────
WORKER_REGISTRY = "workers:registry"


def _worker_key(worker_id: str) -> str:
    return f"worker:{worker_id}"


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("", response_model=list[WorkerGetResponse])
async def list_workers(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """List all registered workers and their current status."""
    worker_ids = await redis.smembers(WORKER_REGISTRY)
    workers: list[Worker] = []
    for wid in sorted(worker_ids):
        data = await redis.hgetall(_worker_key(wid))
        if data:
            workers.append(
                Worker(
                    worker_id=data["worker_id"],
                    status=data["status"],
                    registered_at=data["registered_at"],
                    last_heartbeat=data["last_heartbeat"],
                    processed_count=int(data.get("processed_count", 0)),
                )
            )
    logger.debug("Listed %d workers", len(workers))
    return workers


@router.post("", status_code=201, response_model=Worker)
async def register_worker(
    body: WorkerRegister,
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Register a new worker microservice."""
    if await redis.sismember(WORKER_REGISTRY, body.worker_id):
        raise HTTPException(409, detail=f"Worker '{body.worker_id}' already registered")

    now = datetime.now(timezone.utc).isoformat()
    worker_data = {
        "worker_id": body.worker_id,
        "status": "active",
        "registered_at": now,
        "last_heartbeat": now,
        "processed_count": 0,
    }

    pipe = redis.pipeline()
    pipe.sadd(WORKER_REGISTRY, body.worker_id)
    pipe.hset(_worker_key(body.worker_id), mapping=worker_data)
    await pipe.execute()

    logger.info("Registered worker=%s", body.worker_id)
    return Worker(**{**worker_data, "registered_at": now, "last_heartbeat": now})


@router.delete("/{worker_id}", status_code=200, response_model=dict)
async def deregister_worker(
    worker_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")],
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Deregister (remove) a worker."""
    if not await redis.sismember(WORKER_REGISTRY, worker_id):
        raise HTTPException(404, detail=f"Worker '{worker_id}' not found")

    pipe = redis.pipeline()
    pipe.srem(WORKER_REGISTRY, worker_id)
    pipe.delete(_worker_key(worker_id))
    await pipe.execute()

    logger.info("Deregistered worker=%s", worker_id)
    return {"status": "ok", "worker_id": worker_id, "message": "Worker deregistered"}


@router.put("/{worker_id}/health", response_model=Worker)
async def worker_heartbeat(
    worker_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")],
    body: WorkerHealthUpdate,
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Update a worker's heartbeat and optionally its status / processed count."""
    if not await redis.sismember(WORKER_REGISTRY, worker_id):
        raise HTTPException(404, detail=f"Worker '{worker_id}' not found")

    now = datetime.now(timezone.utc).isoformat()
    updates: dict[str, str | int] = {
        "last_heartbeat": now,
        "status": body.status,
    }
    if body.processed_count is not None:
        updates["processed_count"] = body.processed_count

    await redis.hset(_worker_key(worker_id), mapping=updates)

    data = await redis.hgetall(_worker_key(worker_id))
    logger.info("Heartbeat received for worker=%s status=%s", worker_id, body.status)
    return Worker(
        worker_id=data["worker_id"],
        status=data["status"],
        registered_at=data["registered_at"],
        last_heartbeat=data["last_heartbeat"],
        processed_count=int(data.get("processed_count", 0)),
    )
