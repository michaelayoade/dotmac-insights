"""Shared utilities for ERPNext sync modules."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def safe_int(value: Any) -> Optional[int]:
    """Parse an integer from ERPNext custom fields if present."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_iso_date(value: Any) -> Optional[datetime]:
    """Best-effort ISO date parser used for ERPNext date fields."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
