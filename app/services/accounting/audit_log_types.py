"""Type definitions for audit log service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models.accounting_ext import AuditAction

__all__ = [
    "AuditLogFilters",
]


@dataclass
class AuditLogFilters:
    """Filters for listing audit log entries."""

    query: Optional[str] = None
    doc_type: Optional[str] = None
    action: Optional[AuditAction] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
