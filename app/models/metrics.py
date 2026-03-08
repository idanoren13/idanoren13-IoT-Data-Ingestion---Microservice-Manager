"""Pydantic schemas for throughput metrics."""

from pydantic import BaseModel


class ThroughputMetrics(BaseModel):
    """Throughput metrics response model."""

    current_throughput: float
    window_seconds: int
    messages_in_window: int
