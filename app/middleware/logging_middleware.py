"""Request / response logging middleware – logs every API call with timing."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("iot_platform")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and latency for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        logger.info("→  %s %s", request.method, request.url.path)

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "←  %s %s  %s  %.1f ms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
