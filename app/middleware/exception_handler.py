"""Global exception handlers – keeps route code clean of try/except boilerplate."""

import logging
import traceback
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

logger = logging.getLogger("iot_platform")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI application."""

    # ── HTTP exceptions (raised intentionally in route logic) ──────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_id = uuid4().hex[:8]
        logger.warning(
            "HTTP %s | %s %s | detail=%s | error_id=%s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            error_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_id": error_id,
            },
        )

    # ── Pydantic / query-param validation errors ──────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        error_id = uuid4().hex[:8]
        logger.warning(
            "Validation error | %s %s | errors=%s | error_id=%s",
            request.method,
            request.url.path,
            exc.errors(),
            error_id,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "status_code": 422,
                "detail": "Request validation failed",
                "errors": _simplify_validation_errors(exc.errors()),
                "error_id": error_id,
            },
        )

    # ── Redis connectivity issues ─────────────────────────────────────
    @app.exception_handler(RedisConnectionError)
    async def redis_connection_handler(request: Request, exc: RedisConnectionError):
        error_id = uuid4().hex[:8]
        logger.error(
            "Redis connection error | %s %s | %s | error_id=%s",
            request.method,
            request.url.path,
            exc,
            error_id,
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": True,
                "status_code": 503,
                "detail": "Data store is temporarily unavailable",
                "error_id": error_id,
            },
        )

    @app.exception_handler(RedisTimeoutError)
    async def redis_timeout_handler(request: Request, exc: RedisTimeoutError):
        error_id = uuid4().hex[:8]
        logger.error(
            "Redis timeout | %s %s | %s | error_id=%s",
            request.method,
            request.url.path,
            exc,
            error_id,
        )
        return JSONResponse(
            status_code=504,
            content={
                "error": True,
                "status_code": 504,
                "detail": "Data store request timed out",
                "error_id": error_id,
            },
        )

    # ── Catch-all for any unhandled exception ─────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        error_id = uuid4().hex[:8]
        logger.critical(
            "Unhandled exception | %s %s | %s: %s | error_id=%s\n%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc,
            error_id,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "detail": "Internal server error",
                "error_id": error_id,
            },
        )


def _simplify_validation_errors(errors: list[dict]) -> list[dict]:
    """Strip Pydantic internals from validation errors for a cleaner API response."""
    return [
        {
            "field": " -> ".join(str(loc) for loc in e.get("loc", [])),
            "message": e.get("msg", ""),
            "type": e.get("type", ""),
        }
        for e in errors
    ]
