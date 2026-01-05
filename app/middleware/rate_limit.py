"""
Rate limiting middleware for authentication endpoints.

Provides protection against brute-force attacks on login endpoints.
Uses Redis backend for distributed deployments, with in-memory fallback.
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

try:
    from redis.exceptions import RedisError
except ImportError:
    class RedisError(Exception):
        pass


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


class RedisRateLimiter:
    """
    Redis-backed rate limiter using sliding window algorithm.
    Falls back to in-memory when Redis is unavailable.
    """

    def __init__(
        self,
        requests_per_window: int = 10,
        window_seconds: int = 60,
        block_seconds: int = 300,
        key_prefix: str = "ratelimit",
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.key_prefix = key_prefix
        self._fallback = InMemoryRateLimiter(
            requests_per_window, window_seconds, block_seconds
        )

    async def is_rate_limited(self, key: str) -> Tuple[bool, Optional[int]]:
        """Check if key is rate limited. Falls back to in-memory if Redis unavailable."""
        from app.cache import get_redis_client

        client = await get_redis_client()
        if client is None:
            return await self._fallback.is_rate_limited(key)

        try:
            return await self._check_redis(client, key)
        except RedisError as e:
            logger.warning("redis_rate_limit_fallback", error=str(e))
            return await self._fallback.is_rate_limited(key)

    async def _check_redis(self, client, key: str) -> Tuple[bool, Optional[int]]:
        """Redis implementation using sorted sets for sliding window."""
        redis_key = f"{self.key_prefix}:{key}"
        block_key = f"{self.key_prefix}:blocked:{key}"
        now = time.time()
        window_start = now - self.window_seconds

        blocked_until = await client.get(block_key)
        if blocked_until:
            retry_after = int(float(blocked_until) - now)
            if retry_after > 0:
                return True, retry_after
            else:
                await client.delete(block_key)

        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, self.window_seconds * 2)
        results = await pipe.execute()

        count = results[2]

        if count > self.requests_per_window:
            await client.setex(block_key, self.block_seconds, str(now + self.block_seconds))
            logger.warning("rate_limit_exceeded_redis", key=key, count=count)
            return True, self.block_seconds

        return False, None

    async def record_failure(self, key: str) -> None:
        """Record a failed attempt with heavier weight."""
        from app.cache import get_redis_client

        client = await get_redis_client()
        if client is None:
            await self._fallback.record_failure(key)
            return

        try:
            redis_key = f"{self.key_prefix}:{key}"
            now = time.time()
            pipe = client.pipeline()
            pipe.zadd(redis_key, {f"{now}_1": now})
            pipe.zadd(redis_key, {f"{now}_2": now})
            pipe.expire(redis_key, self.window_seconds * 2)
            await pipe.execute()
        except RedisError:
            await self._fallback.record_failure(key)

    async def clear(self, key: str) -> None:
        """Clear rate limit entry for a key."""
        from app.cache import get_redis_client

        client = await get_redis_client()
        if client is None:
            await self._fallback.clear(key)
            return

        try:
            redis_key = f"{self.key_prefix}:{key}"
            block_key = f"{self.key_prefix}:blocked:{key}"
            await client.delete(redis_key, block_key)
        except RedisError:
            await self._fallback.clear(key)


# Global rate limiter instance for auth endpoints
# Uses Redis when available, falls back to in-memory
auth_rate_limiter = RedisRateLimiter(
    requests_per_window=10,
    window_seconds=60,
    block_seconds=300,
    key_prefix="auth",
)

# Webhook rate limiter - more permissive but still protective
webhook_rate_limiter = RedisRateLimiter(
    requests_per_window=100,
    window_seconds=60,
    block_seconds=300,
    key_prefix="webhook",
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


async def check_webhook_rate_limit(request: Request) -> None:
    """
    Rate limiting dependency for webhook endpoints.

    Raises HTTPException 429 if rate limited.

    Usage:
        @router.post("/paystack", dependencies=[Depends(check_webhook_rate_limit)])
    """
    client_ip = get_client_ip(request)

    is_limited, retry_after = await webhook_rate_limiter.is_rate_limited(client_ip)

    if is_limited:
        logger.warning(
            "webhook_rate_limited",
            client_ip=client_ip,
            retry_after=retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many webhook requests. Please try again later.",
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )
