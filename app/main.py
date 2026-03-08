"""FastAPI application entry-point for the IoT Data Ingestion platform."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import close_redis, init_redis
from app.routers import scaling, sensors, workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup / shutdown: Redis connections."""
    await init_redis()
    yield
    await close_redis()


app = FastAPI(
    title="IoT Data Ingestion & Microservice Manager",
    description=(
        "A real-time IoT data ingestion platform that receives sensor data, "
        "stores it in Redis, and dynamically manages worker microservices."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(sensors.router)
app.include_router(workers.router)
app.include_router(scaling.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic liveness probe."""
    return {"status": "ok"}
