"""FastAPI application entry-point for the IoT Data Ingestion platform."""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.middleware.exception_handler import register_exception_handlers
from app.middleware.logging_config import setup_logging
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.redis_client import close_redis, init_redis
from app.routers import metrics, scaling, sensors, workers

logger = logging.getLogger("iot_platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup / shutdown: Redis connections."""
    setup_logging()
    logger.info("Starting IoT Data Ingestion platform …")
    await init_redis()
    logger.info("Redis connection established")
    yield
    logger.info("Shutting down …")
    await close_redis()
    logger.info("Redis connection closed")


app = FastAPI(
    title="IoT Data Ingestion & Microservice Manager",
    description=(
        "A real-time IoT data ingestion platform that receives sensor data, "
        "stores it in Redis, and dynamically manages worker microservices."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: first added = outermost) ───────────────
app.add_middleware(RequestLoggingMiddleware)

# ── Global exception handlers ────────────────────────────────────────
register_exception_handlers(app)

# ── Routers ──────────────────────────────────────────────────────────
app.include_router(sensors.router)
app.include_router(workers.router)
app.include_router(metrics.router)
app.include_router(scaling.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic liveness probe."""
    return {"status": "ok"}
