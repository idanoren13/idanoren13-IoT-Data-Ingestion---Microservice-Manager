"""Part 3 – Throughput metrics & scaling recommendation endpoints."""

import math
import time

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

from app.config import settings
from app.redis_client import get_redis

router = APIRouter(prefix="/api/v1", tags=["Scaling"])

WORKER_REGISTRY = "workers:registry"


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class ThroughputMetrics(BaseModel):
    current_throughput: float
    window_seconds: int
    messages_in_window: int


class ScalingRecommendation(BaseModel):
    current_throughput: float
    active_workers: int
    recommended_action: str
    recommended_workers: int
    reason: str


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


async def _calculate_throughput(redis: Redis) -> tuple[float, int]:
    """Return (messages_per_second, total_messages_in_window)."""
    now = int(time.time())
    window = settings.throughput_window_seconds

    # Gather per-second bucket keys
    keys = [f"throughput:{now - i}" for i in range(window)]
    values = await redis.mget(*keys)

    total = sum(int(v) for v in values if v is not None)
    rate = total / window
    return rate, total


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("/metrics/throughput", response_model=ThroughputMetrics)
async def get_throughput(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Get current ingestion throughput metrics."""
    rate, total = await _calculate_throughput(redis)
    return ThroughputMetrics(
        current_throughput=round(rate, 2),
        window_seconds=settings.throughput_window_seconds,
        messages_in_window=total,
    )


@router.get("/scaling/recommendation", response_model=ScalingRecommendation)
async def get_scaling_recommendation(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Return a scaling recommendation based on current throughput and active workers."""
    rate, _ = await _calculate_throughput(redis)
    active_workers = await redis.scard(WORKER_REGISTRY)

    # Edge case: no workers registered yet
    if active_workers == 0:
        return ScalingRecommendation(
            current_throughput=round(rate, 2),
            active_workers=0,
            recommended_action="SCALE_UP",
            recommended_workers=max(settings.min_workers, math.ceil(rate / settings.worker_capacity)) if rate > 0 else settings.min_workers,
            reason="No active workers registered",
        )

    capacity = settings.worker_capacity
    scale_down = settings.scale_down_threshold

    if rate > active_workers * capacity:
        needed = math.ceil(rate / capacity)
        recommended = min(needed, settings.max_workers)
        return ScalingRecommendation(
            current_throughput=round(rate, 2),
            active_workers=active_workers,
            recommended_action="SCALE_UP",
            recommended_workers=recommended,
            reason=f"Throughput ({rate:.0f} msg/s) exceeds {capacity} msg/s per worker",
        )

    if rate < active_workers * scale_down:
        needed = max(math.ceil(rate / capacity), settings.min_workers)
        recommended = max(needed, settings.min_workers)
        return ScalingRecommendation(
            current_throughput=round(rate, 2),
            active_workers=active_workers,
            recommended_action="SCALE_DOWN",
            recommended_workers=recommended,
            reason=f"Throughput ({rate:.0f} msg/s) below {scale_down} msg/s per worker threshold",
        )

    return ScalingRecommendation(
        current_throughput=round(rate, 2),
        active_workers=active_workers,
        recommended_action="NO_CHANGE",
        recommended_workers=active_workers,
        reason="Throughput is within acceptable range",
    )
