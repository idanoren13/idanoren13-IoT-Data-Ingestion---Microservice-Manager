"""Pydantic schemas for sensor data – with strict validation."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SensorReading(BaseModel):
    """Payload sent by IoT devices."""

    sensor_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        examples=["sensor-001"],
        description="Unique sensor identifier (alphanumeric, hyphens, underscores only)",
    )
    timestamp: datetime = Field(
        ...,
        examples=["2026-03-13T10:30:00Z"],
        description="Reading timestamp in ISO-8601 format",
    )
    readings: dict[str, float] = Field(
        ...,
        examples=[{"temperature": 23.5, "humidity": 65.2}],
        description="Key-value pairs of sensor measurements",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        examples=[{"location": "warehouse-A", "device_type": "DHT22"}],
        description="Optional key-value metadata about the reading",
    )

    @field_validator("readings")
    @classmethod
    def readings_must_not_be_empty(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("readings must contain at least one measurement")
        return v


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
