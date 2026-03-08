"""Tests for Part 1 – Sensor data ingestion & retrieval.

Covers every endpoint in sensors.py:
  POST /api/v1/sensors/data          – ingest a sensor reading
  GET  /api/v1/sensors/{id}/data     – latest readings for a sensor
  GET  /api/v1/sensors/{id}/data/range – readings in a time window
  GET  /api/v1/sensors               – list all sensors

For each endpoint we test:
  - successful (happy-path) usage
  - input-validation rejections (payloads that don't match the model)
  - edge / error cases (404, bad ranges, boundary limits)
"""

import pytest


# ── Valid reference payload ───────────────────────────────────────────
SENSOR_PAYLOAD = {
    "sensor_id": "sensor-001",
    "timestamp": "2024-01-15T10:30:00Z",
    "readings": {"temperature": 23.5, "humidity": 65.2},
    "metadata": {"location": "warehouse-A", "device_type": "DHT22"},
}


# =====================================================================
#  POST /api/v1/sensors/data  –  ingest sensor data
# =====================================================================


@pytest.mark.asyncio
async def test_ingest_sensor_data(client):
    """Happy path: valid payload returns 201."""
    resp = await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sensor_id"] == "sensor-001"


@pytest.mark.asyncio
async def test_ingest_without_optional_metadata(client):
    """metadata is optional – omitting it should still succeed."""
    payload = {
        "sensor_id": "sensor-002",
        "timestamp": "2024-01-15T10:30:00Z",
        "readings": {"temperature": 20.0},
    }
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 201
    assert resp.json()["sensor_id"] == "sensor-002"


@pytest.mark.asyncio
async def test_ingest_empty_readings_rejected(client):
    """readings dict must not be empty (model validator)."""
    payload = {**SENSOR_PAYLOAD, "readings": {}}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_missing_required_field_sensor_id(client):
    """Missing sensor_id must be rejected."""
    payload = {
        "timestamp": "2024-01-15T10:30:00Z",
        "readings": {"temperature": 23.5},
    }
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_missing_required_field_timestamp(client):
    """Missing timestamp must be rejected."""
    payload = {
        "sensor_id": "sensor-001",
        "readings": {"temperature": 23.5},
    }
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_missing_required_field_readings(client):
    """Missing readings must be rejected."""
    payload = {
        "sensor_id": "sensor-001",
        "timestamp": "2024-01-15T10:30:00Z",
    }
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_invalid_sensor_id_pattern(client):
    """sensor_id with spaces / special chars should be rejected."""
    payload = {**SENSOR_PAYLOAD, "sensor_id": "bad sensor!"}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_empty_sensor_id(client):
    """sensor_id with empty string should be rejected (min_length=1)."""
    payload = {**SENSOR_PAYLOAD, "sensor_id": ""}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_sensor_id_too_long(client):
    """sensor_id exceeding 128 chars should be rejected (max_length=128)."""
    payload = {**SENSOR_PAYLOAD, "sensor_id": "a" * 129}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_invalid_timestamp_format(client):
    """Non-ISO-8601 timestamps should be rejected."""
    payload = {**SENSOR_PAYLOAD, "timestamp": "not-a-date"}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_readings_wrong_value_type(client):
    """readings values must be floats – string values should be rejected."""
    payload = {**SENSOR_PAYLOAD, "readings": {"temperature": "hot"}}
    resp = await client.post("/api/v1/sensors/data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_completely_empty_body(client):
    """Posting an empty JSON object should be rejected."""
    resp = await client.post("/api/v1/sensors/data", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_no_body(client):
    """Posting with no JSON body at all should be rejected."""
    resp = await client.post("/api/v1/sensors/data")
    assert resp.status_code == 422


# =====================================================================
#  GET /api/v1/sensors/{sensor_id}/data  –  latest readings
# =====================================================================


@pytest.mark.asyncio
async def test_get_latest_readings(client):
    """Happy path: ingest two readings, retrieve them sorted latest-first."""
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    payload2 = {**SENSOR_PAYLOAD, "timestamp": "2024-01-15T11:00:00Z"}
    await client.post("/api/v1/sensors/data", json=payload2)

    resp = await client.get("/api/v1/sensors/sensor-001/data")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Should return only readings + timestamp (not full sensor objects)
    for entry in data:
        assert "readings" in entry
        assert "timestamp" in entry
        assert "sensor_id" not in entry
        assert "metadata" not in entry
    # Latest first
    # Pydantic may normalise the TZ suffix; accept either format
    assert "2024-01-15T11:00:00" in data[0]["timestamp"]
    assert data[0]["readings"] == {"temperature": 23.5, "humidity": 65.2}


@pytest.mark.asyncio
async def test_get_latest_readings_not_found(client):
    """Querying a sensor with no data returns 404."""
    resp = await client.get("/api/v1/sensors/nonexistent/data")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_readings_invalid_sensor_id(client):
    """sensor_id with special chars in the path should be rejected (422)."""
    resp = await client.get("/api/v1/sensors/bad sensor!/data")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_latest_readings_with_limit(client):
    """The ?limit= query parameter should cap the number of results."""
    for i in range(5):
        payload = {**SENSOR_PAYLOAD, "timestamp": f"2024-01-15T1{i}:00:00Z"}
        await client.post("/api/v1/sensors/data", json=payload)

    resp = await client.get("/api/v1/sensors/sensor-001/data", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_latest_readings_limit_zero_rejected(client):
    """limit=0 should be rejected (ge=1)."""
    resp = await client.get("/api/v1/sensors/sensor-001/data", params={"limit": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_latest_readings_limit_exceeds_max_rejected(client):
    """limit=1001 should be rejected (le=1000)."""
    resp = await client.get("/api/v1/sensors/sensor-001/data", params={"limit": 1001})
    assert resp.status_code == 422


# =====================================================================
#  GET /api/v1/sensors/{sensor_id}/data/range  –  time-range query
# =====================================================================


@pytest.mark.asyncio
async def test_get_readings_range(client):
    """Happy path: range that includes one of two ingested readings."""
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    payload2 = {**SENSOR_PAYLOAD, "timestamp": "2024-01-15T12:00:00Z"}
    await client.post("/api/v1/sensors/data", json=payload2)

    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "2024-01-15T10:00:00Z", "end": "2024-01-15T10:45:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "2024-01-15T10:30:00" in data[0]["timestamp"]


@pytest.mark.asyncio
async def test_get_readings_range_start_after_end(client):
    """start >= end should be rejected with 400."""
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "2024-01-15T12:00:00Z", "end": "2024-01-15T10:00:00Z"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_readings_range_start_equals_end(client):
    """start == end should be rejected with 400."""
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "2024-01-15T10:00:00Z", "end": "2024-01-15T10:00:00Z"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_readings_range_no_data_in_window(client):
    """Valid range but no data inside it returns 404."""
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "2025-01-01T00:00:00Z", "end": "2025-01-02T00:00:00Z"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_readings_range_missing_start(client):
    """Missing the required 'start' param should be rejected."""
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"end": "2024-01-15T12:00:00Z"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_readings_range_missing_end(client):
    """Missing the required 'end' param should be rejected."""
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "2024-01-15T10:00:00Z"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_readings_range_invalid_date_format(client):
    """Non-ISO date strings for start/end should be rejected."""
    resp = await client.get(
        "/api/v1/sensors/sensor-001/data/range",
        params={"start": "last-week", "end": "today"},
    )
    assert resp.status_code == 422


# =====================================================================
#  GET /api/v1/sensors  –  list all sensors
# =====================================================================


@pytest.mark.asyncio
async def test_list_sensors(client):
    """Happy path: two ingested sensors appear in the listing."""
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    payload2 = {**SENSOR_PAYLOAD, "sensor_id": "sensor-002"}
    await client.post("/api/v1/sensors/data", json=payload2)

    resp = await client.get("/api/v1/sensors")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = [s["sensor_id"] for s in data]
    assert "sensor-001" in ids
    assert "sensor-002" in ids
    # Each entry must include reading_count
    for sensor in data:
        assert "reading_count" in sensor
        assert sensor["reading_count"] >= 1


@pytest.mark.asyncio
async def test_list_sensors_empty(client):
    """No sensors ingested yet – should return an empty list, not an error."""
    resp = await client.get("/api/v1/sensors")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_sensors_reading_count_increments(client):
    """Ingesting multiple readings for one sensor should increase reading_count."""
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    payload2 = {**SENSOR_PAYLOAD, "timestamp": "2024-01-15T11:00:00Z"}
    await client.post("/api/v1/sensors/data", json=payload2)

    resp = await client.get("/api/v1/sensors")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reading_count"] == 2
