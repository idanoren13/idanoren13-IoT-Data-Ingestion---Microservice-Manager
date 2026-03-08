"""Tests for Part 3 – Throughput metrics & scaling recommendations."""

import time

import pytest


@pytest.mark.asyncio
async def test_throughput_zero(client):
    resp = await client.get("/api/v1/metrics/throughput")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_throughput"] == 0.0


@pytest.mark.asyncio
async def test_throughput_after_ingestion(client, redis):
    # Simulate throughput by setting per-second counters directly
    now = int(time.time())
    for i in range(5):
        await redis.set(f"throughput:{now - i}", 100)

    resp = await client.get("/api/v1/metrics/throughput")
    assert resp.status_code == 200
    body = resp.json()
    # 500 messages in 10-second window = 50 msg/s
    assert body["current_throughput"] == 50.0
    assert body["messages_in_window"] == 500


@pytest.mark.asyncio
async def test_scaling_no_workers(client, redis):
    # Some throughput, no workers
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 200)

    resp = await client.get("/api/v1/scaling/recommendation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommended_action"] == "SCALE_UP"
    assert body["active_workers"] == 0


@pytest.mark.asyncio
async def test_scaling_scale_up(client, redis):
    # Register 2 workers
    await client.post("/api/v1/workers", json={"worker_id": "w1"})
    await client.post("/api/v1/workers", json={"worker_id": "w2"})

    # Simulate throughput of 4000 msg/s (exceeds 2 * 1500 = 3000)
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 4000)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] == "SCALE_UP"
    assert body["active_workers"] == 2
    assert body["recommended_workers"] >= 3


@pytest.mark.asyncio
async def test_scaling_scale_down(client, redis):
    # Register 5 workers
    for i in range(5):
        await client.post("/api/v1/workers", json={"worker_id": f"w{i}"})

    # Simulate throughput of 100 msg/s (below 5 * 1000 = 5000)
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 100)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] == "SCALE_DOWN"
    assert body["active_workers"] == 5


@pytest.mark.asyncio
async def test_scaling_no_change(client, redis):
    # Register 3 workers
    for i in range(3):
        await client.post("/api/v1/workers", json={"worker_id": f"w{i}"})

    # Simulate throughput of 3600 msg/s (between 3*1000=3000 and 3*1500=4500)
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 3600)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] == "NO_CHANGE"
    assert body["recommended_workers"] == 3
