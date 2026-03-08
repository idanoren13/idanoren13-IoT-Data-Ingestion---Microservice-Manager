"""Part 2 – Throughput metrics endpoint."""

import logging

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.config import settings
from app.models.metrics import ThroughputMetrics
from app.redis_client import get_redis
from app.utils import calculate_throughput

logger = logging.getLogger("iot_platform")

router = APIRouter(prefix="/api/v1/metrics", tags=["Metrics"])

# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("/throughput", response_model=ThroughputMetrics)
async def get_throughput(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Get current ingestion throughput metrics."""
    rate, total = await calculate_throughput(redis)
    logger.debug("Throughput: %.2f msg/s (%d in window)", rate, total)
    return ThroughputMetrics(
        current_throughput=round(rate, 2),
        window_seconds=settings.throughput_window_seconds,
        messages_in_window=total,
    )
