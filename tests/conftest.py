"""Shared pytest fixtures – provides a FastAPI test client backed by fakeredis."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import fakeredis.aioredis

from app.main import app
from app import redis_client


@pytest_asyncio.fixture
async def redis():
    """Create a fakeredis instance and inject it into the app."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_client._redis = fake
    yield fake
    await fake.flushall()
    await fake.aclose()
    redis_client._redis = None


@pytest_asyncio.fixture
async def client(redis):
    """Async HTTP test client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
