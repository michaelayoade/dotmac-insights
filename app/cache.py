"""Redis caching utilities for analytics endpoints."""
from __future__ import annotations

import json
import hashlib
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec
import redis
from app.config import settings

P = ParamSpec("P")
T = TypeVar("T")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client if configured."""
    global _redis_client
    if _redis_client is None and settings.redis_url:
        try:
            _redis_client = redis.from_url(settings.redis_url)
            _redis_client.ping()
        except redis.exceptions.ConnectionError:
            _redis_client = None
    return _redis_client


def cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a cache key from prefix and arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
    return f"analytics:{prefix}:{key_hash}"


def cached(
    prefix: str,
    ttl: int = 300,  # 5 minutes default
    skip_args: int = 0,  # Number of leading args to skip (e.g., 'db' session)
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for caching function results in Redis.

    Args:
        prefix: Cache key prefix (usually the endpoint name)
        ttl: Time to live in seconds
        skip_args: Number of leading positional args to skip when building cache key
                   (useful for skipping db session, request objects, etc.)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            client = get_redis_client()

            # Skip caching if Redis not available
            if client is None:
                return await func(*args, **kwargs)

            # Build cache key from args (skipping specified leading args)
            cache_args = args[skip_args:] if skip_args else args
            # Remove 'db' from kwargs if present
            cache_kwargs = {k: v for k, v in kwargs.items() if k != "db"}
            key = cache_key(prefix, *cache_args, **cache_kwargs)

            try:
                # Try to get from cache
                cached_data = client.get(key)
                if cached_data:
                    return json.loads(cached_data)

                # Execute function and cache result
                result = await func(*args, **kwargs)

                # Serialize and cache
                client.setex(key, ttl, json.dumps(result, default=str))

                return result
            except (redis.exceptions.RedisError, json.JSONDecodeError):
                # Fall back to uncached execution on any Redis error
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "analytics:overview:*")

    Returns:
        Number of keys deleted
    """
    client = get_redis_client()
    if client is None:
        return 0

    try:
        keys = list(client.scan_iter(match=pattern))
        if keys:
            return client.delete(*keys)
        return 0
    except redis.exceptions.RedisError:
        return 0


def invalidate_analytics_cache() -> int:
    """Invalidate all analytics cache entries."""
    return invalidate_pattern("analytics:*")


# Cache TTL presets (in seconds)
CACHE_TTL = {
    "short": 60,       # 1 minute - for real-time-ish data
    "medium": 300,     # 5 minutes - default
    "long": 900,       # 15 minutes - for expensive queries
    "hourly": 3600,    # 1 hour - for slowly changing data
}
