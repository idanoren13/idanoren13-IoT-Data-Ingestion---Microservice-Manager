# IoT Data Ingestion & Microservice Manager

A real-time IoT data ingestion platform that receives sensor data from thousands of devices, stores it efficiently in Redis, and dynamically manages worker microservices based on throughput load.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       FastAPI Application                    │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │  Sensors API  │  │  Workers API  │  │   Scaling API    │  │
│  │  (Part 1)     │  │  (Part 2)     │  │   (Part 3)       │  │
│  │              │  │               │  │                  │  │
│  │ POST /data   │  │ GET  /        │  │ GET /metrics/    │  │
│  │ GET  /data   │  │ POST /        │  │     throughput   │  │
│  │ GET  /range  │  │ DEL  /{id}    │  │ GET /scaling/    │  │
│  │ GET  /       │  │ PUT  /health  │  │     recommendation│ │
│  └──────┬───────┘  └──────┬────────┘  └────────┬─────────┘  │
│         │                 │                     │            │
│         └─────────────────┼─────────────────────┘            │
│                           │                                  │
│                    ┌──────▼───────┐                           │
│                    │ Redis Client │                           │
│                    └──────┬───────┘                           │
└───────────────────────────┼──────────────────────────────────┘
                            │
                     ┌──────▼───────┐
                     │    Redis     │
                     │              │
                     │ Sorted Sets  │ ← sensor time-series data
                     │ Hashes       │ ← worker state
                     │ Sets         │ ← registries
                     │ Strings      │ ← throughput counters
                     └──────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Sorted Sets for sensor data** | Score = Unix timestamp enables O(log N) range queries via `ZRANGEBYSCORE`, natural ordering without secondary indexes. |
| **Per-second throughput counters** | Each second gets its own Redis key (`throughput:{epoch}`). Sliding window averages the last N seconds. Keys auto-expire after 60s to prevent unbounded growth. |
| **Redis Hashes for workers** | Each worker is a hash (`worker:{id}`) — atomic field-level updates for heartbeats without overwriting the entire object. |
| **Pydantic Settings** | All thresholds (capacity, min/max workers) are configurable via environment variables with `IOT_` prefix. |

### Project Structure

```
├── app/
│   ├── main.py              # FastAPI app with lifespan-managed Redis
│   ├── config.py             # Pydantic Settings (env-configurable)
│   ├── redis_client.py       # Async Redis connection lifecycle
│   ├── models/
│   │   ├── sensor.py         # SensorReading, SensorReadingOut, SensorInfo
│   │   └── worker.py         # WorkerRegister, WorkerHealthUpdate, Worker
│   └── routers/
│       ├── sensors.py        # Part 1: Sensor data CRUD
│       ├── workers.py        # Part 2: Worker management
│       └── scaling.py        # Part 3: Metrics & scaling
├── tests/
│   ├── conftest.py           # fakeredis fixtures
│   ├── test_sensors.py
│   ├── test_workers.py
│   └── test_scaling.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Quick Start

### With Docker Compose (recommended)

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.  
Interactive docs at `http://localhost:8000/docs`.

### Local Development

```bash
# Prerequisites: Python 3.14, Redis running on localhost:6379
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Running Tests

```bash
pip install pytest pytest-asyncio httpx fakeredis
pytest tests/ -v
```

No running Redis instance required — tests use **fakeredis**.

## API Reference

### Sensor Data (Part 1)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sensors/data` | POST | Ingest a sensor reading |
| `/api/v1/sensors/{sensor_id}/data` | GET | Get latest readings (query: `limit`) |
| `/api/v1/sensors/{sensor_id}/data/range` | GET | Get readings in time range (query: `start`, `end`) |
| `/api/v1/sensors` | GET | List all registered sensors |

### Worker Management (Part 2)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/workers` | GET | List all workers |
| `/api/v1/workers` | POST | Register a new worker |
| `/api/v1/workers/{worker_id}` | DELETE | Deregister a worker |
| `/api/v1/workers/{worker_id}/health` | PUT | Worker heartbeat/health update |

### Scaling & Metrics (Part 3)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/metrics/throughput` | GET | Current throughput metrics |
| `/api/v1/scaling/recommendation` | GET | Scaling recommendation based on load |

### Scaling Rules

| Condition | Recommendation |
|-----------|---------------|
| `throughput > workers × 1500` | **SCALE_UP** |
| `throughput < workers × 1000` | **SCALE_DOWN** |
| Otherwise | **NO_CHANGE** |
| Workers clamped to | **[1, 10]** |

All thresholds configurable via environment variables with `IOT_` prefix (e.g., `IOT_WORKER_CAPACITY=1500`).

## Future Improvements

Given more time, the following enhancements would be prioritized:

1. **Data Retention & Eviction** — Add TTL or max-count policies to sensor sorted sets to prevent unbounded memory growth. Implement `ZREMRANGEBYSCORE` for time-based cleanup.

2. **Batch Ingestion** — Add a `POST /api/v1/sensors/data/batch` endpoint accepting arrays of readings for higher throughput and fewer round-trips.

3. **WebSocket Streaming** — Real-time push of sensor data and scaling events to dashboards via WebSocket connections.

4. **Actual Worker Orchestration** — Integrate with Docker/Kubernetes API to *execute* scaling decisions automatically (spin up/down containers) instead of only recommending.

5. **Authentication & Rate Limiting** — JWT/API-key auth for sensors and admin endpoints, per-sensor rate limiting to prevent abuse.

6. **Persistent Storage** — Write-behind to TimescaleDB or InfluxDB for long-term analytics while keeping Redis as the hot cache.

7. **Prometheus Metrics** — Export throughput, latency percentiles, and worker health as Prometheus metrics for Grafana dashboards.

8. **Worker Health Expiry** — Auto-mark workers as `inactive` if no heartbeat received within a configurable timeout (using Redis key expiry + keyspace notifications).

9. **CI/CD Pipeline** — GitHub Actions workflow with lint, test, build, and push to container registry.

10. **Load Testing** — Locust or k6 scripts to benchmark ingestion throughput and validate scaling thresholds under realistic load.
