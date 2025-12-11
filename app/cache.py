"""Redis caching utilities for analytics endpoints."""
from __future__ import annotations

import json
import hashlib
import structlog
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec, TYPE_CHECKING, Awaitable, cast
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session
from app.config import settings

if TYPE_CHECKING:
    from app.auth import Principal

P = ParamSpec("P")
T = TypeVar("T")

_redis_client: Optional[redis.Redis] = None
logger = structlog.get_logger(__name__)


async def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client if configured (async, non-blocking)."""
    global _redis_client
    if _redis_client is None and settings.redis_url:
        try:
            _redis_client = redis.from_url(settings.redis_url)
            await _redis_client.ping()
        except RedisConnectionError:
            _redis_client = None
    return _redis_client


def cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a cache key from prefix and arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12]
    return f"analytics:{prefix}:{key_hash}"


def cached(
    prefix: str,
    ttl: int = 300,  # 5 minutes default
    skip_args: int = 0,  # Number of leading args to skip (e.g., 'db' session)
    include_principal: bool = False,  # Include principal context in cache key
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for caching function results in Redis.

    Args:
        prefix: Cache key prefix (usually the endpoint name)
        ttl: Time to live in seconds
        skip_args: Number of leading positional args to skip when building cache key
                   (useful for skipping db session, request objects, etc.)
        include_principal: When True, includes principal id/type/scopes in cache key to avoid cross-tenant bleed
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            client = await get_redis_client()

            # Skip caching if Redis not available
            if client is None:
                return await func(*args, **kwargs)

            # Build cache key from args (skipping specified leading args)
            raw_args = args[skip_args:] if skip_args else args
            cache_args = []

            principal: Any = None
            RuntimePrincipal: Any = None
            try:
                from app.auth import Principal as _RuntimePrincipal

                RuntimePrincipal = _RuntimePrincipal
            except Exception:
                RuntimePrincipal = None

            for arg in raw_args:
                if isinstance(arg, Session):
                    continue  # exclude DB sessions from cache key
                if RuntimePrincipal is not None and isinstance(arg, RuntimePrincipal):
                    principal = arg
                    continue  # principal captured separately
                if RuntimePrincipal is None and all(
                    hasattr(arg, attr) for attr in ["id", "type", "scopes", "is_superuser"]
                ):
                    principal = arg
                    continue
                cache_args.append(arg)

            # Remove 'db' from kwargs if present
            cache_kwargs = {k: v for k, v in kwargs.items() if k not in {"db"}}
            if "principal" in cache_kwargs:
                principal = cache_kwargs.pop("principal")

            if include_principal and principal is not None:
                principal_scopes = sorted(list(getattr(principal, "scopes", []) or []))
                cache_kwargs["_principal"] = {
                    "id": getattr(principal, "id", None),
                    "type": getattr(principal, "type", None),
                    "is_superuser": getattr(principal, "is_superuser", False),
                    "scopes": principal_scopes,
                }
            key = cache_key(prefix, *cache_args, **cache_kwargs)

            try:
                # Try to get from cache
                cached_data = await client.get(key)
                if cached_data:
                    return cast(T, json.loads(cached_data))

                # Execute function and cache result
                result = await func(*args, **kwargs)

                # Serialize and cache
                try:
                    await client.setex(key, ttl, json.dumps(result, default=str))
                except RedisError as err:
                    logger.warning("cache_set_failed", key=key, prefix=prefix, error=str(err))

                return result
            except (RedisError, json.JSONDecodeError):
                # Fall back to uncached execution on any Redis error
                return await func(*args, **kwargs)

        return wrapper
    return decorator


async def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "analytics:overview:*")

    Returns:
        Number of keys deleted
    """
    client = await get_redis_client()
    if client is None:
        return 0

    try:
        keys = [key async for key in client.scan_iter(match=pattern)]
        if keys:
            deleted = await client.delete(*keys)
            return int(deleted)
        return 0
    except RedisError:
        return 0


async def invalidate_analytics_cache() -> int:
    """Invalidate all analytics cache entries."""
    return await invalidate_pattern("analytics:*")


# Cache TTL presets (in seconds)
CACHE_TTL = {
    "short": 60,       # 1 minute - for real-time-ish data
    "medium": 300,     # 5 minutes - default
    "long": 900,       # 15 minutes - for expensive queries
    "hourly": 3600,    # 1 hour - for slowly changing data
}
