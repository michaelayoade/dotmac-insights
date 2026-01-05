"""Middleware to attach soft validation warnings to responses."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request

from app.validation.soft_validation import clear_warnings, serialize_warnings, get_warnings


class ValidationWarningsMiddleware(BaseHTTPMiddleware):
    """Attach soft validation warnings as response headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        clear_warnings()
        response = await call_next(request)
        warnings = get_warnings()
        if warnings:
            encoded, total = serialize_warnings()
            response.headers["X-Validation-Warnings"] = encoded
            response.headers["X-Validation-Warnings-Count"] = str(total)
        return response
