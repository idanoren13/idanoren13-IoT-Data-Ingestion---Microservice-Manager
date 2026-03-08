"""Tests for Part 2 – Worker microservice management."""

import pytest


@pytest.mark.asyncio
async def test_register_worker(client):
    resp = await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["worker_id"] == "worker-001"
    assert body["status"] == "active"
    assert body["processed_count"] == 0


@pytest.mark.asyncio
async def test_register_duplicate_worker(client):
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_workers(client):
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    await client.post("/api/v1/workers", json={"worker_id": "worker-002"})

    resp = await client.get("/api/v1/workers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_worker_heartbeat(client):
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})

    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "active", "processed_count": 500},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed_count"] == 500


@pytest.mark.asyncio
async def test_heartbeat_unknown_worker(client):
    resp = await client.put(
        "/api/v1/workers/nonexistent/health",
        json={"status": "active"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deregister_worker(client):
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})

    resp = await client.delete("/api/v1/workers/worker-001")
    assert resp.status_code == 200

    # Should be gone
    resp = await client.get("/api/v1/workers")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_deregister_unknown_worker(client):
    resp = await client.delete("/api/v1/workers/nonexistent")
    assert resp.status_code == 404
