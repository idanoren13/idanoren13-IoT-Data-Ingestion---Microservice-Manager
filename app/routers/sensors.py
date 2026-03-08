"""Part 1 – Sensor data ingestion & retrieval endpoints."""

import json
import logging
import time

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from redis.asyncio import Redis

from app.config import settings
from app.models.sensor import SensorInfo, SensorReading, SensorReadingOut
from app.redis_client import get_redis

logger = logging.getLogger("iot_platform")

router = APIRouter(prefix="/api/v1/sensors", tags=["Sensors"])

# ──────────────────────────────────────────────
# Redis key helpers
# ──────────────────────────────────────────────
SENSOR_REGISTRY = "sensors:registry"


def _data_key(sensor_id: str) -> str:
    return f"sensor:{sensor_id}:data"


def _throughput_key() -> str:
    """Per-second bucket key for throughput tracking."""
    return f"throughput:{int(time.time())}"


async def _calculate_throughput(redis: Redis) -> tuple[float, int]:
    """Return (messages_per_second, total_messages_in_window)."""
    now = int(time.time())
    window = settings.throughput_window_seconds

    keys = [f"throughput:{now - i}" for i in range(window)]
    values = await redis.mget(*keys)

    total = sum(int(v) for v in values if v is not None)
    rate = total / window
    return rate, total


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────


class ThroughputMetrics(BaseModel):
    current_throughput: float
    window_seconds: int
    messages_in_window: int


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.post("/data", status_code=201, response_model=dict)
async def ingest_sensor_data(
    reading: SensorReading,
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Ingest a single sensor reading and store it in Redis."""
    score = reading.timestamp.timestamp()
    value = json.dumps(
        {
            "sensor_id": reading.sensor_id,
            "timestamp": reading.timestamp.isoformat(),
            "readings": reading.readings,
            "metadata": reading.metadata,
        }
    )

    pipe = redis.pipeline()
    pipe.zadd(_data_key(reading.sensor_id), {value: score})
    pipe.sadd(SENSOR_REGISTRY, reading.sensor_id)

    tp_key = _throughput_key()
    pipe.incr(tp_key)
    pipe.expire(tp_key, 60)

    await pipe.execute()

    logger.info("Ingested reading for sensor=%s", reading.sensor_id)
    return {"status": "ok", "sensor_id": reading.sensor_id}


@router.get("/{sensor_id}/data", response_model=list[SensorReadingOut])
async def get_latest_readings(
    sensor_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")],
    redis: Annotated[Redis, Depends(get_redis)],
    limit: Annotated[int, Query(ge=1, le=1000, description="Number of latest readings")] = 10,
):
    """Retrieve the latest N readings for a given sensor."""
    raw = await redis.zrevrange(_data_key(sensor_id), 0, limit - 1)
    if not raw:
        raise HTTPException(404, detail=f"No data found for sensor '{sensor_id}'")
    return [json.loads(item) for item in raw]


@router.get("/{sensor_id}/data/range", response_model=list[SensorReadingOut])
async def get_readings_in_range(
    sensor_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")],
    redis: Annotated[Redis, Depends(get_redis)],
    start: Annotated[datetime, Query(description="Range start (ISO-8601)")],
    end: Annotated[datetime, Query(description="Range end (ISO-8601)")],
):
    """Retrieve readings within a time range for a given sensor."""
    if start >= end:
        raise HTTPException(400, detail="'start' must be before 'end'")

    raw = await redis.zrangebyscore(
        _data_key(sensor_id),
        min=start.timestamp(),
        max=end.timestamp(),
    )
    if not raw:
        raise HTTPException(
            404,
            detail=f"No data found for sensor '{sensor_id}' in the given range",
        )
    return [json.loads(item) for item in raw]


@router.get("", response_model=list[SensorInfo])
async def list_sensors(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """List all registered sensors with their reading counts."""
    sensor_ids = await redis.smembers(SENSOR_REGISTRY)
    sensors: list[SensorInfo] = []
    for sid in sorted(sensor_ids):
        count = await redis.zcard(_data_key(sid))
        sensors.append(SensorInfo(sensor_id=sid, reading_count=count))
    logger.debug("Listed %d sensors", len(sensors))
    return sensors


@router.get("/metrics/throughput", response_model=ThroughputMetrics)
async def get_throughput(
    redis: Annotated[Redis, Depends(get_redis)],
):
    """Get current ingestion throughput metrics."""
    rate, total = await _calculate_throughput(redis)
    logger.debug("Throughput: %.2f msg/s (%d in window)", rate, total)
    return ThroughputMetrics(
        current_throughput=round(rate, 2),
        window_seconds=settings.throughput_window_seconds,
        messages_in_window=total,
    )
