"""Pydantic schemas for worker microservices."""

from datetime import datetime

from pydantic import BaseModel, Field


class WorkerRegister(BaseModel):
    """Payload to register a new worker."""

    worker_id: str = Field(..., examples=["worker-001"])


class WorkerHealthUpdate(BaseModel):
    """Payload for worker heartbeat / health update."""

    status: str = Field("active", examples=["active", "draining"])
    processed_count: int | None = Field(
        None, description="Total messages processed so far", examples=[15000]
    )


class Worker(BaseModel):
    """Full worker representation."""

    worker_id: str
    status: str = "active"
    registered_at: datetime
    last_heartbeat: datetime
    processed_count: int = 0


class WorkerGetResponse(BaseModel):
    """Worker Status representation."""

    worker_id: str
    status: str = "active"
