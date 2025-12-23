"""
Rate limiting middleware for authentication endpoints.

Provides protection against brute-force attacks on login endpoints.
Uses in-memory storage by default, with optional Redis backend for distributed deployments.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import asyncio

import structlog
from fastapi import HTTPException, Request

from app.config import settings

logger = structlog.get_logger("auth.rate_limit")


@dataclass
class RateLimitEntry:
    """Tracks request counts and timestamps for rate limiting."""
    count: int = 0
    window_start: float = 0.0
    blocked_until: float = 0.0


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window.

    For production deployments with multiple workers, use Redis-backed limiter.
    """

    def __init__(
        self,
        requests_per_window: int = 10,
        window_seconds: int = 60,
        block_seconds: int = 300,
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._entries: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if the key is rate limited.

        Args:
            key: Identifier for rate limiting (e.g., IP address, user ID)

        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        async with self._lock:
            now = time.time()
            entry = self._entries[key]

            # Check if currently blocked
            if entry.blocked_until > now:
                retry_after = int(entry.blocked_until - now)
                return True, retry_after

            # Check if window has expired
            if now - entry.window_start > self.window_seconds:
                entry.count = 0
                entry.window_start = now

            # Increment and check
            entry.count += 1

            if entry.count > self.requests_per_window:
                entry.blocked_until = now + self.block_seconds
                logger.warning(
                    "rate_limit_exceeded",
                    key=key,
                    count=entry.count,
                    block_seconds=self.block_seconds,
                )
                return True, self.block_seconds

            return False, None

    async def record_failure(self, key: str) -> None:
        """
        Record a failed attempt (e.g., invalid token).

        Failures are weighted more heavily to detect attacks faster.
        """
        async with self._lock:
            now = time.time()
            entry = self._entries[key]
            if now - entry.window_start > self.window_seconds:
                entry.count = 0
                entry.window_start = now

            entry.count += 2  # Weight failures more heavily

            if entry.count > self.requests_per_window:
                entry.blocked_until = now + self.block_seconds
                logger.warning(
                    "rate_limit_exceeded_failures",
                    key=key,
                    count=entry.count,
                )

    async def clear(self, key: str) -> None:
        """Clear rate limit entry for a key (e.g., after successful auth)."""
        async with self._lock:
            if key in self._entries:
                del self._entries[key]

    def cleanup_expired(self) -> int:
        """Remove expired entries to prevent memory growth. Returns count of removed entries."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._entries.items()
            if now - entry.window_start > self.window_seconds * 2
            and entry.blocked_until < now
        ]
        for key in expired_keys:
            del self._entries[key]
        return len(expired_keys)


# Global rate limiter instance for auth endpoints
# Conservative defaults: 10 requests/minute, 5-minute block on excess
auth_rate_limiter = InMemoryRateLimiter(
    requests_per_window=10,
    window_seconds=60,
    block_seconds=300,
)


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, respecting X-Forwarded-For for proxied requests.

    Security: Only trust X-Forwarded-For if behind a trusted reverse proxy.
    """
    # Check for forwarded header (when behind proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP (client IP)
        return forwarded_for.split(",")[0].strip()

    # Check for real IP header (nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


async def check_auth_rate_limit(request: Request) -> None:
    """
    Rate limiting dependency for auth endpoints.

    Raises HTTPException 429 if rate limited.

    Usage:
        @router.post("/session", dependencies=[Depends(check_auth_rate_limit)])
    """
    client_ip = get_client_ip(request)

    is_limited, retry_after = await auth_rate_limiter.is_rate_limited(client_ip)

    if is_limited:
        logger.warning(
            "auth_rate_limited",
            client_ip=client_ip,
            retry_after=retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )


async def record_auth_failure(request: Request) -> None:
    """Record a failed authentication attempt for rate limiting."""
    client_ip = get_client_ip(request)
    await auth_rate_limiter.record_failure(client_ip)


async def clear_auth_rate_limit(request: Request) -> None:
    """Clear rate limit after successful authentication."""
    client_ip = get_client_ip(request)
    await auth_rate_limiter.clear(client_ip)
