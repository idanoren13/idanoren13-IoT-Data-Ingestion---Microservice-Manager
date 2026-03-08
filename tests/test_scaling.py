"""Tests for Part 3 – Throughput metrics & scaling recommendations.

Covers:
  GET /api/v1/metrics/throughput         – throughput metrics
  GET /api/v1/scaling/recommendation     – scaling advice

For each endpoint we test:
  - successful (happy-path) usage with different throughput/worker combos
  - response-shape validation (all model fields present)
  - edge cases (zero throughput, no workers, boundary thresholds)
"""

import time

import pytest

from app.config import settings


# =====================================================================
#  GET /api/v1/metrics/throughput
# =====================================================================


@pytest.mark.asyncio
async def test_throughput_zero(client):
    """No ingestion at all – throughput should be 0."""
    resp = await client.get("/api/v1/metrics/throughput")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_throughput"] == 0.0
    assert body["messages_in_window"] == 0
    assert body["window_seconds"] == settings.throughput_window_seconds


@pytest.mark.asyncio
async def test_throughput_after_ingestion(client, redis):
    """Manually seed throughput counters and verify the computed rate."""
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
async def test_throughput_response_shape(client):
    """The response must include exactly the ThroughputMetrics fields."""
    resp = await client.get("/api/v1/metrics/throughput")
    body = resp.json()
    expected_keys = {"current_throughput", "window_seconds", "messages_in_window"}
    assert set(body.keys()) == expected_keys


@pytest.mark.asyncio
async def test_throughput_full_window(client, redis):
    """Fill the entire window and verify the rate equals the per-second count."""
    now = int(time.time())
    window = settings.throughput_window_seconds
    for i in range(window):
        await redis.set(f"throughput:{now - i}", 200)

    resp = await client.get("/api/v1/metrics/throughput")
    body = resp.json()
    assert body["current_throughput"] == 200.0
    assert body["messages_in_window"] == 200 * window


@pytest.mark.asyncio
async def test_throughput_partial_window(client, redis):
    """Only a subset of seconds in the window have data."""
    now = int(time.time())
    # Only 2 out of 10 seconds have data
    await redis.set(f"throughput:{now}", 300)
    await redis.set(f"throughput:{now - 1}", 300)

    resp = await client.get("/api/v1/metrics/throughput")
    body = resp.json()
    # 600 / 10 = 60
    assert body["current_throughput"] == 60.0
    assert body["messages_in_window"] == 600


# =====================================================================
#  GET /api/v1/scaling/recommendation
# =====================================================================


@pytest.mark.asyncio
async def test_scaling_no_workers_no_throughput(client):
    """No workers and no throughput – should recommend SCALE_UP to min_workers."""
    resp = await client.get("/api/v1/scaling/recommendation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommended_action"] == "SCALE_UP"
    assert body["active_workers"] == 0
    assert body["recommended_workers"] == settings.min_workers
    assert body["reason"] == "No active workers registered"


@pytest.mark.asyncio
async def test_scaling_no_workers_with_throughput(client, redis):
    """Throughput exists but no workers – should SCALE_UP."""
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 200)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] == "SCALE_UP"
    assert body["active_workers"] == 0
    assert body["recommended_workers"] >= settings.min_workers


@pytest.mark.asyncio
async def test_scaling_scale_up(client, redis):
    """Throughput exceeds worker capacity – should recommend SCALE_UP."""
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
    """Throughput is far below capacity – should recommend SCALE_DOWN."""
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
    """Throughput is within acceptable range – should recommend NO_CHANGE."""
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


@pytest.mark.asyncio
async def test_scaling_response_shape(client):
    """The response must include exactly the ScalingRecommendation fields."""
    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    expected_keys = {
        "current_throughput",
        "active_workers",
        "recommended_action",
        "recommended_workers",
        "reason",
    }
    assert set(body.keys()) == expected_keys


@pytest.mark.asyncio
async def test_scaling_recommended_workers_never_exceeds_max(client, redis):
    """Even with massive throughput, recommended_workers should not exceed max_workers."""
    await client.post("/api/v1/workers", json={"worker_id": "w1"})

    # Simulate extremely high throughput
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 999_999)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] == "SCALE_UP"
    assert body["recommended_workers"] <= settings.max_workers


@pytest.mark.asyncio
async def test_scaling_recommended_workers_never_below_min(client, redis):
    """Even with near-zero throughput, recommended_workers >= min_workers."""
    for i in range(3):
        await client.post("/api/v1/workers", json={"worker_id": f"w{i}"})

    # Simulate extremely low throughput (just 1 msg total in the window)
    now = int(time.time())
    await redis.set(f"throughput:{now}", 1)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_workers"] >= settings.min_workers


@pytest.mark.asyncio
async def test_scaling_scale_up_exact_boundary(client, redis):
    """Throughput exactly at capacity boundary should be NO_CHANGE (not SCALE_UP).

    With 2 workers and capacity 1500, the threshold is 3000.
    rate == 3000 does NOT exceed (rate > active * capacity), so it should be NO_CHANGE.
    """
    await client.post("/api/v1/workers", json={"worker_id": "w1"})
    await client.post("/api/v1/workers", json={"worker_id": "w2"})

    # Throughput exactly at the capacity boundary: 3000 msg/s (2 * 1500)
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 3000)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    # Exactly at capacity → NOT scale-up (strict >)
    assert body["recommended_action"] != "SCALE_UP"


@pytest.mark.asyncio
async def test_scaling_scale_down_exact_boundary(client, redis):
    """Throughput exactly at scale_down boundary should be NO_CHANGE.

    With 2 workers and scale_down=1000, the threshold is 2000.
    rate == 2000 does NOT go below (rate < active * scale_down), so NO_CHANGE.
    """
    await client.post("/api/v1/workers", json={"worker_id": "w1"})
    await client.post("/api/v1/workers", json={"worker_id": "w2"})

    # Throughput exactly at the scale-down threshold: 2000 msg/s (2 * 1000)
    now = int(time.time())
    for i in range(10):
        await redis.set(f"throughput:{now - i}", 2000)

    resp = await client.get("/api/v1/scaling/recommendation")
    body = resp.json()
    assert body["recommended_action"] != "SCALE_DOWN"
