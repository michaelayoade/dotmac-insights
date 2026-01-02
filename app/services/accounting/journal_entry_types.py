"""Type definitions for journal entry service.

These dataclasses define the contract for journal entry operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.accounting import JournalEntryType

__all__ = [
    "JEFilters",
    "JELineData",
    "JECreateData",
    "JEUpdateData",
]


@dataclass
class JEFilters:
    """Filters for listing journal entries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    voucher_type: Optional[JournalEntryType] = None
    company: Optional[str] = None
    is_opening: Optional[bool] = None


@dataclass
class JELineData:
    """Data for a journal entry line item."""

    account: Optional[str] = None
    account_id: Optional[int] = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None
    description: Optional[str] = None
    user_remark: Optional[str] = None


@dataclass
class JECreateData:
    """Data for creating a journal entry."""

    posting_date: date
    voucher_type: JournalEntryType = JournalEntryType.JOURNAL_ENTRY
    user_remark: Optional[str] = None
    description: Optional[str] = None
    company: Optional[str] = None
    is_opening: bool = False
    lines: List[JELineData] = field(default_factory=list)


@dataclass
class JEUpdateData:
    """Data for updating a journal entry (all fields optional)."""

    posting_date: Optional[date] = None
    user_remark: Optional[str] = None
    company: Optional[str] = None
