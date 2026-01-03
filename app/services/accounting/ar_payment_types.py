"""Type definitions for AR payment service.

These dataclasses define the contract for payment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.payment import PaymentMethod, PaymentStatus

__all__ = [
    "PaymentFilters",
    "AllocationData",
    "PaymentCreateData",
    "PaymentUpdateData",
]


@dataclass
class PaymentFilters:
    """Filters for listing payments."""

    search: Optional[str] = None
    customer_account_id: Optional[int] = None
    status: Optional[PaymentStatus] = None
    payment_method: Optional[PaymentMethod] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sort_by: str = "payment_date"
    sort_dir: str = "desc"


@dataclass
class AllocationData:
    """Data for creating a payment allocation."""

    document_type: str  # "invoice" or "credit_note"
    document_id: int
    allocated_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    write_off_amount: Decimal = Decimal("0")
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None


@dataclass
class PaymentCreateData:
    """Data for creating a payment."""

    payment_date: datetime
    amount: Decimal
    customer_account_id: Optional[int] = None
    currency: str = "NGN"
    payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    receipt_number: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: Decimal = Decimal("1")
    bank_account_id: Optional[int] = None
    allocations: List[AllocationData] = field(default_factory=list)


@dataclass
class PaymentUpdateData:
    """Data for updating a payment (all fields optional)."""

    payment_date: Optional[datetime] = None
    amount: Optional[Decimal] = None
    receipt_number: Optional[str] = None
    customer_account_id: Optional[int] = None
    currency: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: Optional[Decimal] = None
    bank_account_id: Optional[int] = None
