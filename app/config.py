"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurable application settings, overridable via environment variables."""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Scaling thresholds
    worker_capacity: int = 1500  # max messages/second per worker
    scale_down_threshold: int = 1000  # messages/second per worker to trigger scale-down
    min_workers: int = 1
    max_workers: int = 10

    # Throughput sliding window
    throughput_window_seconds: int = 10  # seconds of history to average over

    model_config = {"env_prefix": "IOT_", "env_file": ".env"}


settings = Settings()
