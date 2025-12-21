"""
Payment Subscription Model

Recurring payment subscriptions for automatic billing via payment gateways.
This is distinct from service subscriptions (internet plans, etc.).
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, ForeignKey, Numeric, Index, JSON,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.gateway_transaction import GatewayProvider
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.gateway_transaction import GatewayTransaction


class PaymentSubscriptionStatus(str, enum.Enum):
    """Payment subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    PAST_DUE = "past_due"
    EXPIRED = "expired"


class PaymentSubscriptionInterval(str, enum.Enum):
    """Billing interval."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class PaymentSubscription(Base):
    """
    Recurring payment subscriptions via payment gateways.

    Manages automatic billing using saved payment authorizations.
    Different from service Subscription model which tracks internet/voice plans.
    """

    __tablename__ = "payment_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider
    provider: Mapped[GatewayProvider] = mapped_column(
        SAEnum(GatewayProvider, name="gatewayprovider", create_constraint=False),
        nullable=False, index=True
    )
    provider_subscription_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Customer
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    authorization_code: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Saved card/payment method

    # Plan details
    plan_code: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Provider plan
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Billing
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    interval: Mapped[PaymentSubscriptionInterval] = mapped_column(
        SAEnum(PaymentSubscriptionInterval, name="paymentsubscriptioninterval"),
        nullable=False
    )
    interval_count: Mapped[int] = mapped_column(default=1)  # Every N intervals

    # Status
    status: Mapped[PaymentSubscriptionStatus] = mapped_column(
        SAEnum(PaymentSubscriptionStatus, name="paymentsubscriptionstatus"),
        default=PaymentSubscriptionStatus.ACTIVE, index=True
    )

    # Billing cycle
    current_period_start: Mapped[datetime] = mapped_column(nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(nullable=False)
    next_billing_date: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Limits
    max_charges: Mapped[Optional[int]] = mapped_column(nullable=True)  # None = unlimited

    # Charge counts
    total_charges: Mapped[int] = mapped_column(default=0)
    successful_charges: Mapped[int] = mapped_column(default=0)
    failed_charges: Mapped[int] = mapped_column(default=0)

    # Total amount collected
    total_collected: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0")
    )

    # Retry handling for failed charges
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)
    last_charge_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_charge_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_charge_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to service subscription (if applicable)
    service_subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id"), nullable=True
    )

    # Invoice/product link
    invoice_template_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    paused_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    cancelled_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_payment_sub_customer_status", "customer_id", "status"),
        Index("ix_payment_sub_next_billing", "next_billing_date", "status"),
        Index("ix_payment_sub_provider", "provider", "status"),
    )

    def __repr__(self) -> str:
        return f"<PaymentSubscription {self.id} {self.plan_name} {self.status.value}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status == PaymentSubscriptionStatus.ACTIVE

    @property
    def is_billable(self) -> bool:
        """Check if subscription should be billed."""
        if not self.is_active:
            return False
        if self.max_charges and self.successful_charges >= self.max_charges:
            return False
        return utc_now() >= self.next_billing_date

    @property
    def charges_remaining(self) -> Optional[int]:
        """Get remaining charges (None if unlimited)."""
        if self.max_charges is None:
            return None
        return max(0, self.max_charges - self.successful_charges)
