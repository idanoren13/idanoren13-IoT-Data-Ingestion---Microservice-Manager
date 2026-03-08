"""Pydantic schemas for scaling recommendations."""

from pydantic import BaseModel


class ScalingRecommendation(BaseModel):
    """Scaling recommendation response model."""

    current_throughput: float
    active_workers: int
    recommended_action: str
    recommended_workers: int
    reason: str
