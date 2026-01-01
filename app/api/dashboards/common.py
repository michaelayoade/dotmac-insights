"""
Common utilities for dashboard endpoints.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from typing import Optional
from datetime import datetime, date


def resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, return first."""
    if requested:
        return requested
    currencies = [row[0] for row in db.query(distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    first = currencies[0]
    return str(first) if first is not None else None


def parse_date_param(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}") from exc
