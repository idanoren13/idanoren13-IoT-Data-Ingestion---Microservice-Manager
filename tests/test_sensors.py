"""Tests for Part 1 – Sensor data ingestion & retrieval."""

import pytest


SENSOR_PAYLOAD = {
    "sensor_id": "sensor-001",
    "timestamp": "2024-01-15T10:30:00Z",
    "readings": {"temperature": 23.5, "humidity": 65.2},
    "metadata": {"location": "warehouse-A", "device_type": "DHT22"},
}


@pytest.mark.asyncio
async def test_ingest_sensor_data(client):
    resp = await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sensor_id"] == "sensor-001"


@pytest.mark.asyncio
async def test_get_latest_readings(client):
    # Ingest two readings
    await client.post("/api/v1/sensors/data", json=SENSOR_PAYLOAD)
    payload2 = {**SENSOR_PAYLOAD, "timestamp": "2024-01-15T11:00:00Z"}
    await client.post("/api/v1/sensors/data", json=payload2)

    resp = await client.get("/api/v1/sensors/sensor-001/data")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Should return only readings + timestamp, not full sensor objects
    for entry in data:
        assert "readings" in entry
        assert "timestamp" in entry
        assert "sensor_id" not in entry
        assert "metadata" not in entry
    # Latest first
    assert data[0]["timestamp"] == "2024-01-15T11:00:00+00:00"
    assert data[0]["readings"] == {"temperature": 23.5, "humidity": 65.2}


@pytest.mark.asyncio
async def test_get_latest_readings_not_found(client):
    resp = await client.get("/api/v1/sensors/nonexistent/data")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_readings_range(client):
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
    assert data[0]["timestamp"] == "2024-01-15T10:30:00+00:00"


@pytest.mark.asyncio
async def test_list_sensors(client):
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
