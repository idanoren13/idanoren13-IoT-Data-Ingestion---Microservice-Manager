"""Pydantic schemas for worker microservices – with strict validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkerRegister(BaseModel):
    """Payload to register a new worker."""

    worker_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        examples=["worker-001"],
        description="Unique worker identifier (alphanumeric, hyphens, underscores only)",
    )


class WorkerHealthUpdate(BaseModel):
    """Payload for worker heartbeat / health update."""

    status: Literal["active", "draining", "unhealthy"] = Field(
        "active",
        examples=["active", "draining"],
        description="Worker status (must be one of: active, draining, unhealthy)",
    )
    processed_count: int | None = Field(
        None,
        ge=0,
        description="Total messages processed so far (must be >= 0)",
        examples=[15000],
    )


class Worker(BaseModel):
    """Full worker representation."""

    worker_id: str
    status: str = "active"
    registered_at: datetime
    last_heartbeat: datetime
    processed_count: int = 0
