"""Type definitions for payment terms service.

These dataclasses define the contract for payment terms operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

__all__ = [
    "PaymentTermsFilters",
    "ScheduleData",
    "PaymentTermsCreateData",
    "PaymentTermsUpdateData",
]


@dataclass
class PaymentTermsFilters:
    """Filters for listing payment terms."""

    is_active: Optional[bool] = None
    company: Optional[str] = None
    search: Optional[str] = None
    sort_by: str = "template_name"
    sort_dir: str = "asc"


@dataclass
class ScheduleData:
    """Data for a payment schedule line."""

    credit_days: int = 0
    credit_months: int = 0
    day_of_month: Optional[int] = None
    payment_percentage: Decimal = Decimal("100")
    discount_percentage: Decimal = Decimal("0")
    discount_days: int = 0
    description: Optional[str] = None


@dataclass
class PaymentTermsCreateData:
    """Data for creating payment terms."""

    template_name: str
    description: Optional[str] = None
    company: Optional[str] = None
    schedules: List[ScheduleData] = field(default_factory=list)


@dataclass
class PaymentTermsUpdateData:
    """Data for updating payment terms (all fields optional)."""

    template_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    schedules: Optional[List[ScheduleData]] = None
