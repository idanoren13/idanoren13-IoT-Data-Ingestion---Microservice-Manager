"""Part 3 – Throughput metrics & scaling recommendation endpoints."""

import logging
import math
import time

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

from app.config import settings
from app.redis_client import get_redis
from app.routers.sensors import _calculate_throughput

logger = logging.getLogger("iot_platform")

router = APIRouter(prefix="/api/v1", tags=["Scaling"])

WORKER_REGISTRY = "workers:registry"


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class ScalingRecommendation(BaseModel):
    current_throughput: float
    active_workers: int
    recommended_action: str
    recommended_workers: int
    reason: str


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("/scaling/recommendation", response_model=ScalingRecommendation)
async def get_scaling_recommendation(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Return a scaling recommendation based on current throughput and active workers."""
    rate, _ = await _calculate_throughput(redis)
    active_workers = await redis.scard(WORKER_REGISTRY)

    # Edge case: no workers registered yet
    if active_workers == 0:
        recommended = (
            max(settings.min_workers, math.ceil(rate / settings.worker_capacity))
            if rate > 0
            else settings.min_workers
        )
        logger.info("Scaling recommendation: SCALE_UP (no active workers), recommended=%d", recommended)
        return ScalingRecommendation(
            current_throughput=round(rate, 2),
            active_workers=0,
            recommended_action="SCALE_UP",
            recommended_workers=recommended,
            reason="No active workers registered",
        )

    capacity = settings.worker_capacity
    scale_down = settings.scale_down_threshold

    if rate > active_workers * capacity:
        needed = math.ceil(rate / capacity)
        recommended = min(needed, settings.max_workers)
        logger.info(
            "Scaling recommendation: SCALE_UP, rate=%.0f, workers=%d, recommended=%d",
            rate, active_workers, recommended,
        )
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
        logger.info(
            "Scaling recommendation: SCALE_DOWN, rate=%.0f, workers=%d, recommended=%d",
            rate, active_workers, recommended,
        )
        return ScalingRecommendation(
            current_throughput=round(rate, 2),
            active_workers=active_workers,
            recommended_action="SCALE_DOWN",
            recommended_workers=recommended,
            reason=f"Throughput ({rate:.0f} msg/s) below {scale_down} msg/s per worker threshold",
        )

    logger.debug("Scaling recommendation: NO_CHANGE, rate=%.0f, workers=%d", rate, active_workers)
    return ScalingRecommendation(
        current_throughput=round(rate, 2),
        active_workers=active_workers,
        recommended_action="NO_CHANGE",
        recommended_workers=active_workers,
        reason="Throughput is within acceptable range",
    )
