"""Type definitions for debit notes service.

These dataclasses define the contract for debit note operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.books_settings import DebitNoteStatus

__all__ = [
    "DebitNoteFilters",
    "DebitNoteLineData",
    "DebitNoteCreateData",
    "DebitNoteUpdateData",
]


@dataclass
class DebitNoteFilters:
    """Filters for listing debit notes."""

    supplier_id: Optional[int] = None
    status: Optional[DebitNoteStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    search: Optional[str] = None
    sort_by: str = "posting_date"
    sort_dir: str = "desc"


@dataclass
class DebitNoteLineData:
    """Data for a debit note line."""

    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    account: Optional[str] = None
    cost_center: Optional[str] = None
    return_reason: Optional[str] = None


@dataclass
class DebitNoteCreateData:
    """Data for creating a debit note."""

    supplier_id: int
    issue_date: datetime
    supplier_name: Optional[str] = None
    original_bill_id: Optional[int] = None
    description: Optional[str] = None
    posting_date: Optional[datetime] = None
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    company: Optional[str] = None
    lines: List[DebitNoteLineData] = field(default_factory=list)


@dataclass
class DebitNoteUpdateData:
    """Data for updating a debit note (all fields optional)."""

    description: Optional[str] = None
    issue_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None
    lines: Optional[List[DebitNoteLineData]] = None
