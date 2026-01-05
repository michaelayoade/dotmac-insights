"""Type definitions for invoice service.

These dataclasses define the contract for invoice operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.invoice import InvoiceStatus

__all__ = [
    "InvoiceFilters",
    "InvoiceLineData",
    "InvoiceCreateData",
    "InvoiceUpdateData",
]


@dataclass
class InvoiceFilters:
    """Filters for listing invoices."""

    search: Optional[str] = None
    customer_account_id: Optional[int] = None
    status: Optional[InvoiceStatus] = None
    status_in: Optional[List[InvoiceStatus]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    overdue_only: bool = False
    sort_by: str = "invoice_date"
    sort_dir: str = "desc"


@dataclass
class InvoiceLineData:
    """Data for creating an invoice line."""

    quantity: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    account: Optional[str] = None
    cost_center: Optional[str] = None


@dataclass
class InvoiceCreateData:
    """Data for creating an invoice."""

    customer_account_id: int
    invoice_date: datetime
    lines: List[InvoiceLineData] = field(default_factory=list)
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    payment_terms_id: Optional[int] = None
    company: Optional[str] = None
    category: Optional[str] = None


@dataclass
class InvoiceUpdateData:
    """Data for updating an invoice (all fields optional)."""

    customer_account_id: Optional[int] = None
    description: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None
    currency: Optional[str] = None
    conversion_rate: Optional[Decimal] = None
    payment_terms_id: Optional[int] = None
    category: Optional[str] = None
