"""Async Redis connection manager using the FastAPI lifespan pattern."""

import redis.asyncio as aioredis

from app.config import settings

# Module-level reference; initialised during app lifespan.
_redis: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Create and return an async Redis connection."""
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    # Verify connectivity
    await _redis.ping()
    return _redis


async def close_redis() -> None:
    """Gracefully close the Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def get_redis() -> aioredis.Redis:
    """Return the active Redis connection (for use as a FastAPI dependency)."""
    if _redis is None:
        raise RuntimeError("Redis connection not initialised. Is the app running?")
    return _redis
