"""Type definitions for AP payment service.

These dataclasses define the contract for supplier payment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.supplier_payment import SupplierPaymentStatus

__all__ = [
    "APPaymentFilters",
    "APAllocationData",
    "APPaymentCreateData",
    "APPaymentUpdateData",
]


@dataclass
class APPaymentFilters:
    """Filters for listing supplier payments."""

    supplier_id: Optional[int] = None
    status: Optional[SupplierPaymentStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class APAllocationData:
    """Data for creating a payment allocation."""

    document_type: str  # "bill" or "debit_note"
    document_id: int
    allocated_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    write_off_amount: Decimal = Decimal("0")
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None


@dataclass
class APPaymentCreateData:
    """Data for creating a supplier payment."""

    supplier_id: int
    payment_date: date
    paid_amount: Decimal
    supplier_name: Optional[str] = None
    posting_date: Optional[date] = None
    mode_of_payment: Optional[str] = None
    bank_account_id: Optional[int] = None
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    reference_number: Optional[str] = None
    reference_date: Optional[date] = None
    remarks: Optional[str] = None
    company: Optional[str] = None
    allocations: List[APAllocationData] = field(default_factory=list)


@dataclass
class APPaymentUpdateData:
    """Data for updating a supplier payment (all fields optional)."""

    payment_date: Optional[date] = None
    posting_date: Optional[date] = None
    mode_of_payment: Optional[str] = None
    bank_account_id: Optional[int] = None
    paid_amount: Optional[Decimal] = None
    conversion_rate: Optional[Decimal] = None
    reference_number: Optional[str] = None
    reference_date: Optional[date] = None
    remarks: Optional[str] = None
