"""Type definitions for payment subscription service.

These dataclasses define the contract for payment subscription operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


__all__ = [
    "PaymentSubscriptionFilters",
    "PaymentSubscriptionCreateData",
    "PaymentSubscriptionUpdateData",
    "BillingActionResult",
    "PaymentSubscriptionStats",
]


@dataclass
class PaymentSubscriptionFilters:
    """Filters for listing payment subscriptions."""

    search: Optional[str] = None
    status: Optional[str] = None  # active, paused, cancelled, past_due, etc.
    party_id: Optional[int] = None
    provider: Optional[str] = None  # paystack, flutterwave, etc.
    service_subscription_id: Optional[int] = None
    due_before: Optional[datetime] = None  # next_billing_date filter
    interval: Optional[str] = None  # daily, weekly, monthly, quarterly, annually


@dataclass
class PaymentSubscriptionCreateData:
    """Data for creating a payment subscription."""

    # Required
    party_id: int
    customer_email: str
    provider: str
    authorization_code: str
    plan_name: str
    amount: Decimal
    interval: str  # daily, weekly, monthly, quarterly, annually
    current_period_start: datetime
    current_period_end: datetime
    next_billing_date: datetime

    # Optional
    currency: str = "NGN"
    interval_count: int = 1
    plan_code: Optional[str] = None
    description: Optional[str] = None
    max_charges: Optional[int] = None
    service_subscription_id: Optional[int] = None
    invoice_template_id: Optional[int] = None
    product_id: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None
    company: Optional[str] = None


@dataclass
class PaymentSubscriptionUpdateData:
    """Data for updating a payment subscription (all fields optional)."""

    plan_name: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    max_charges: Optional[int] = None
    next_billing_date: Optional[datetime] = None
    service_subscription_id: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class BillingActionResult:
    """Result of a billing action."""

    success: bool
    action: str
    message: str
    new_status: Optional[str] = None
    next_billing_date: Optional[datetime] = None


@dataclass
class PaymentSubscriptionStats:
    """Payment subscription statistics summary."""

    active: int = 0
    paused: int = 0
    cancelled: int = 0
    past_due: int = 0
    total: int = 0
    monthly_revenue: Decimal = field(default_factory=lambda: Decimal("0"))
    total_collected: Decimal = field(default_factory=lambda: Decimal("0"))
