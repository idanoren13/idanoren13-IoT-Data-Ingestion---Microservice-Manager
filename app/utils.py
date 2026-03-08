"""Shared utility functions for the IoT platform."""

import time

from redis.asyncio import Redis

from app.config import settings


async def calculate_throughput(redis: Redis) -> tuple[float, int]:
    """Return (messages_per_second, total_messages_in_window)."""
    now = int(time.time())
    window = settings.throughput_window_seconds

    keys = [f"throughput:{now - i}" for i in range(window)]
    values = await redis.mget(*keys)

    total = sum(int(v) for v in values if v is not None)
    rate = total / window
    return rate, total
