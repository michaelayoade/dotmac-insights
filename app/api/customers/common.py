"""
Common utilities for customer endpoints.
"""

from typing import Optional
from datetime import datetime, date
from fastapi import HTTPException
from app.models.customer import CustomerStatus


def _calculate_tenure_days(signup_date) -> Optional[int]:
    """Calculate tenure days from signup date (accepts date or datetime)."""
    if not signup_date:
        return None
    if isinstance(signup_date, datetime):
        signup_date = signup_date.date()
    if isinstance(signup_date, date):
        return (date.today() - signup_date).days
    return None


def _parse_date(value: Optional[str], field: str) -> Optional[datetime]:
    """Parse ISO date string safely and raise HTTP 400 on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {value}")


def _normalize_status(status: Optional[CustomerStatus]) -> Optional[str]:
    """Map internal status enums to frontend display values."""
    if status is None:
        return None
    mapping = {
        CustomerStatus.ACTIVE: "active",
        CustomerStatus.INACTIVE: "inactive",
        CustomerStatus.SUSPENDED: "blocked",
        CustomerStatus.PROSPECT: "new",
    }
    return mapping.get(status, "inactive")

