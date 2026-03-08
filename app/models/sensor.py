"""Pydantic schemas for sensor data."""

from datetime import datetime

from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    """Payload sent by IoT devices."""

    sensor_id: str = Field(..., examples=["sensor-001"])
    timestamp: datetime = Field(..., examples=["2024-01-15T10:30:00Z"])
    readings: dict[str, float] = Field(
        ..., examples=[{"temperature": 23.5, "humidity": 65.2}]
    )
    metadata: dict[str, str] = Field(
        ..., examples=[{"location": "warehouse-A", "device_type": "DHT22"}]
    )


class SensorReadingOut(BaseModel):
    """A single stored reading returned to the client."""

    sensor_id: str
    timestamp: datetime
    readings: dict[str, float]
    metadata: dict[str, str]


class SensorInfo(BaseModel):
    """Minimal sensor descriptor for listing."""

    sensor_id: str
    reading_count: int
