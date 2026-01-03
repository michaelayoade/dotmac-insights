"""Type definitions for payment modes service.

These dataclasses define the contract for payment mode operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.accounting import PaymentModeType

__all__ = [
    "PaymentModeFilters",
    "PaymentModeCreateData",
    "PaymentModeUpdateData",
]


@dataclass
class PaymentModeFilters:
    """Filters for listing payment modes."""

    include_disabled: bool = False
    search: Optional[str] = None
    mode_type: Optional[PaymentModeType] = None
    sort_by: str = "mode_of_payment"
    sort_dir: str = "asc"


@dataclass
class PaymentModeCreateData:
    """Data for creating a payment mode."""

    mode_of_payment: str
    mode_type: Optional[PaymentModeType] = None
    enabled: bool = True


@dataclass
class PaymentModeUpdateData:
    """Data for updating a payment mode (all fields optional)."""

    mode_of_payment: Optional[str] = None
    mode_type: Optional[PaymentModeType] = None
    enabled: Optional[bool] = None
