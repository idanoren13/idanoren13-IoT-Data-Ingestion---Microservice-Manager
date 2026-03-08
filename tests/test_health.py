"""Tests for the /health liveness probe endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /health should return {"status": "ok"} with 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_method_not_allowed(client):
    """POST /health should be rejected (method not allowed)."""
    resp = await client.post("/health")
    assert resp.status_code == 405
