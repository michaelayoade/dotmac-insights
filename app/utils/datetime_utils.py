"""
DateTime Utility Module

Provides timezone-aware datetime utilities for consistent UTC handling
across the application.

Usage:
    from app.utils.datetime_utils import utc_now, ensure_utc, naive_to_utc

    # For model defaults
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # For normalizing input
    dt = ensure_utc(user_provided_datetime)
"""
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """
    Return timezone-aware UTC now.

    Use this as default for model datetime columns:
        created_at: Mapped[datetime] = mapped_column(default=utc_now)

    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware UTC.

    If the datetime is naive (no timezone), assumes it's UTC and adds tzinfo.
    If the datetime has a different timezone, converts to UTC.

    Args:
        dt: A datetime object (naive or aware) or None

    Returns:
        datetime: Timezone-aware UTC datetime, or None if input was None

    Example:
        >>> ensure_utc(datetime(2025, 1, 1, 12, 0))
        datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    # Convert to UTC if in different timezone
    return dt.astimezone(timezone.utc)


def naive_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert naive datetime (assumed UTC) to aware.

    Unlike ensure_utc, this only adds UTC tzinfo to naive datetimes.
    Already-aware datetimes are returned unchanged.

    Args:
        dt: A datetime object or None

    Returns:
        datetime: Timezone-aware datetime, or None if input was None

    Example:
        >>> naive_to_utc(datetime(2025, 1, 1, 12, 0))
        datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def is_aware(dt: Optional[datetime]) -> bool:
    """
    Check if a datetime is timezone-aware.

    Args:
        dt: A datetime object or None

    Returns:
        bool: True if datetime has timezone info, False otherwise
    """
    if dt is None:
        return False
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
