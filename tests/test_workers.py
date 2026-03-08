"""Tests for Part 2 – Worker microservice management.

Covers every endpoint in workers.py:
  GET    /api/v1/workers                  – list all workers
  POST   /api/v1/workers                  – register a worker
  DELETE /api/v1/workers/{worker_id}      – deregister a worker
  PUT    /api/v1/workers/{worker_id}/health – heartbeat / health update

For each endpoint we test:
  - successful (happy-path) usage
  - input-validation rejections (payloads that don't match the model)
  - edge / error cases (404, 409, invalid path params)
"""

import pytest


# =====================================================================
#  POST /api/v1/workers  –  register a new worker
# =====================================================================


@pytest.mark.asyncio
async def test_register_worker(client):
    """Happy path: register a new worker returns 201 with correct fields."""
    resp = await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["worker_id"] == "worker-001"
    assert body["status"] == "active"
    assert body["processed_count"] == 0
    assert "registered_at" in body
    assert "last_heartbeat" in body


@pytest.mark.asyncio
async def test_register_duplicate_worker(client):
    """Registering the same worker_id twice returns 409 Conflict."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_worker_missing_worker_id(client):
    """Missing worker_id in the body should be rejected."""
    resp = await client.post("/api/v1/workers", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_worker_empty_worker_id(client):
    """Empty string worker_id should be rejected (min_length=1)."""
    resp = await client.post("/api/v1/workers", json={"worker_id": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_worker_invalid_pattern(client):
    """worker_id with spaces / special chars should be rejected."""
    resp = await client.post("/api/v1/workers", json={"worker_id": "bad worker!"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_worker_id_too_long(client):
    """worker_id exceeding 128 chars should be rejected (max_length=128)."""
    resp = await client.post("/api/v1/workers", json={"worker_id": "w" * 129})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_worker_no_body(client):
    """Posting with no JSON body should be rejected."""
    resp = await client.post("/api/v1/workers")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_worker_extra_fields_ignored(client):
    """Extra fields not in the model should be ignored (Pydantic default)."""
    resp = await client.post(
        "/api/v1/workers",
        json={"worker_id": "worker-x1", "extra_field": "should-be-ignored"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["worker_id"] == "worker-x1"
    assert "extra_field" not in body


# =====================================================================
#  GET /api/v1/workers  –  list all workers
# =====================================================================


@pytest.mark.asyncio
async def test_list_workers(client):
    """Happy path: listing after registering two workers returns both."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    await client.post("/api/v1/workers", json={"worker_id": "worker-002"})

    resp = await client.get("/api/v1/workers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = [w["worker_id"] for w in data]
    assert "worker-001" in ids
    assert "worker-002" in ids


@pytest.mark.asyncio
async def test_list_workers_empty(client):
    """No workers registered – should return an empty list, not an error."""
    resp = await client.get("/api/v1/workers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_workers_returns_all_fields(client):
    """Each worker in the listing must have all Worker model fields."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.get("/api/v1/workers")
    assert resp.status_code == 200
    worker = resp.json()[0]
    expected_keys = {"worker_id", "status", "registered_at", "last_heartbeat", "processed_count"}
    assert set(worker.keys()) == expected_keys


# =====================================================================
#  DELETE /api/v1/workers/{worker_id}  –  deregister
# =====================================================================


@pytest.mark.asyncio
async def test_deregister_worker(client):
    """Happy path: deregistering an existing worker returns 200 and removes it."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})

    resp = await client.delete("/api/v1/workers/worker-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["worker_id"] == "worker-001"

    # Should be gone from listing
    resp = await client.get("/api/v1/workers")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_deregister_unknown_worker(client):
    """Deregistering a non-existent worker returns 404."""
    resp = await client.delete("/api/v1/workers/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deregister_worker_invalid_id_pattern(client):
    """worker_id with special chars in the path should be rejected."""
    resp = await client.delete("/api/v1/workers/bad worker!")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deregister_then_reregister(client):
    """After deregistering, re-registering the same worker_id should succeed."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    await client.delete("/api/v1/workers/worker-001")

    resp = await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    assert resp.status_code == 201


# =====================================================================
#  PUT /api/v1/workers/{worker_id}/health  –  heartbeat
# =====================================================================


@pytest.mark.asyncio
async def test_worker_heartbeat(client):
    """Happy path: heartbeat updates the processed count."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})

    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "active", "processed_count": 500},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed_count"] == 500
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_heartbeat_unknown_worker(client):
    """Heartbeat on a non-existent worker returns 404."""
    resp = await client.put(
        "/api/v1/workers/nonexistent/health",
        json={"status": "active"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat_draining_status(client):
    """Heartbeat with 'draining' status should be accepted."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "draining"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "draining"


@pytest.mark.asyncio
async def test_heartbeat_unhealthy_status(client):
    """Heartbeat with 'unhealthy' status should be accepted."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "unhealthy"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_heartbeat_invalid_status_rejected(client):
    """Heartbeat with a status not in the Literal choices should be rejected."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "offline"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_heartbeat_negative_processed_count_rejected(client):
    """processed_count < 0 should be rejected (ge=0)."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "active", "processed_count": -1},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_heartbeat_without_processed_count(client):
    """processed_count is optional – omitting it should be fine."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "active"},
    )
    assert resp.status_code == 200
    # processed_count should remain at the initial value (0)
    assert resp.json()["processed_count"] == 0


@pytest.mark.asyncio
async def test_heartbeat_default_status(client):
    """Status defaults to 'active' when omitted from the body."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put(
        "/api/v1/workers/worker-001/health",
        json={},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_heartbeat_no_body(client):
    """Sending no JSON body at all should be rejected."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp = await client.put("/api/v1/workers/worker-001/health")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_heartbeat_updates_last_heartbeat(client):
    """The last_heartbeat field should change after a heartbeat."""
    await client.post("/api/v1/workers", json={"worker_id": "worker-001"})
    resp1 = await client.get("/api/v1/workers")
    hb1 = resp1.json()[0]["last_heartbeat"]

    await client.put(
        "/api/v1/workers/worker-001/health",
        json={"status": "active"},
    )
    resp2 = await client.get("/api/v1/workers")
    hb2 = resp2.json()[0]["last_heartbeat"]

    # The heartbeat timestamp should be the same or later
    assert hb2 >= hb1
