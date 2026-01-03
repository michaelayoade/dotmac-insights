"""Service Transaction model.

Tracks all service-level transactions for subscriptions:
- Lifecycle events (activation, suspension, cancellation)
- Plan changes (upgrades, downgrades)
- Charges (subscription, usage, fees)
- Credits and refunds
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Index, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.party import Party
    from app.models.invoice import Invoice
    from app.models.payment import Payment


class ServiceTransaction(Base):
    """Service transaction audit trail."""

    __tablename__ = "service_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[int] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Types: activation, suspension, reactivation, cancellation,
    #        upgrade, downgrade, renewal,
    #        subscription_charge, usage_charge, installation_fee, activation_fee,
    #        reconnection_fee, early_termination_fee, other_fee,
    #        credit, adjustment, refund, proration_credit, proration_charge,
    #        provisioning, deprovisioning, ip_change, speed_change

    status: Mapped[str] = mapped_column(String(20), default="completed", index=True)
    # Status: pending, completed, failed, reversed, cancelled

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Financial
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    # Positive = charge, Negative = credit/refund
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Links to accounting
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    credit_note_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Change tracking (for plan changes, etc.)
    old_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Flexible metadata (attribute name can't be "metadata" on declarative models)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Effective date (when the transaction takes effect)
    effective_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        backref="service_transactions",
        foreign_keys=[subscription_id],
    )
    party: Mapped["Party"] = relationship(
        backref="service_transactions",
        foreign_keys=[party_id],
    )

    __table_args__ = (
        Index("ix_service_transactions_sub_type", "subscription_id", "transaction_type"),
        Index("ix_service_transactions_party_date", "party_id", "effective_date"),
        Index("ix_service_transactions_type_date", "transaction_type", "effective_date"),
    )

    def __repr__(self) -> str:
        return f"<ServiceTransaction {self.id} {self.transaction_type} {self.amount}>"

    @property
    def is_charge(self) -> bool:
        """Check if this is a charge (positive amount)."""
        return self.amount > 0

    @property
    def is_credit(self) -> bool:
        """Check if this is a credit (negative amount)."""
        return self.amount < 0

    @property
    def is_lifecycle_event(self) -> bool:
        """Check if this is a lifecycle event."""
        return self.transaction_type in (
            "activation", "suspension", "reactivation", "cancellation",
            "upgrade", "downgrade", "renewal",
        )
