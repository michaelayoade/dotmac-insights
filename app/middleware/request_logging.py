"""
Structured request logging middleware.

Logs every request with method, path, status, latency, and client IP.
"""
from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.rate_limit import get_client_ip

logger = structlog.get_logger("request")

EXCLUDED_PATHS = {"/health", "/health/ready", "/metrics", "/api/health", "/api/health/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        request.state.request_id = request_id
        client_ip = get_client_ip(request)

        try:
            response = await call_next(request)
            latency = time.time() - start_time

            log_level = "warning" if response.status_code >= 400 else "info"
            getattr(logger, log_level)(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=round(latency * 1000, 2),
                client_ip=client_ip,
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            latency = time.time() - start_time
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                latency_ms=round(latency * 1000, 2),
                client_ip=client_ip,
                error=str(exc)[:100],
            )
            raise
