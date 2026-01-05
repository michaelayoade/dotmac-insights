"""Type definitions for credit notes service.

These dataclasses define the contract for credit note operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.credit_note import CreditNoteStatus

__all__ = [
    "CreditNoteFilters",
    "CreditNoteLineData",
    "CreditNoteCreateData",
    "CreditNoteUpdateData",
]


@dataclass
class CreditNoteFilters:
    """Filters for listing credit notes."""

    customer_account_id: Optional[int] = None
    status: Optional[CreditNoteStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    search: Optional[str] = None
    sort_by: str = "issue_date"
    sort_dir: str = "desc"


@dataclass
class CreditNoteLineData:
    """Data for a credit note line."""

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
class CreditNoteCreateData:
    """Data for creating a credit note."""

    customer_account_id: int
    issue_date: datetime
    invoice_id: Optional[int] = None
    credit_number: Optional[str] = None
    description: Optional[str] = None
    posting_date: Optional[datetime] = None
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    company: Optional[str] = None
    lines: List[CreditNoteLineData] = field(default_factory=list)


@dataclass
class CreditNoteUpdateData:
    """Data for updating a credit note (all fields optional)."""

    description: Optional[str] = None
    issue_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None
    lines: Optional[List[CreditNoteLineData]] = None
