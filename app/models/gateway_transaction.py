"""
Gateway Transaction model for payment gateway transactions.

Records all transactions processed through Paystack, Flutterwave, etc.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Text, ForeignKey, Enum, Index, Numeric, JSON, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.payment import Payment
    from app.models.accounting import BankTransaction


class GatewayProvider(str, enum.Enum):
    """Payment gateway provider."""
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"


class GatewayTransactionType(str, enum.Enum):
    """Type of gateway transaction."""
    PAYMENT = "payment"
    TRANSFER = "transfer"
    REFUND = "refund"
    CHARGEBACK = "chargeback"


class GatewayTransactionStatus(str, enum.Enum):
    """Status of gateway transaction."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"
    ABANDONED = "abandoned"
    REFUNDED = "refunded"


class GatewayTransaction(Base):
    """
    Transactions processed through payment gateways.

    This model tracks all payment and transfer transactions
    initiated via Paystack, Flutterwave, or other gateways.
    """

    __tablename__ = "gateway_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider info
    provider: Mapped[GatewayProvider] = mapped_column(
        Enum(GatewayProvider), nullable=False, index=True
    )
    transaction_type: Mapped[GatewayTransactionType] = mapped_column(
        Enum(GatewayTransactionType), nullable=False, index=True
    )

    # References - idempotency key
    reference: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    provider_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Status
    status: Mapped[GatewayTransactionStatus] = mapped_column(
        Enum(GatewayTransactionStatus),
        default=GatewayTransactionStatus.PENDING,
        index=True
    )

    # Amount (document currency)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Payment channel
    channel: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # card, bank, ussd, etc.

    # Customer info
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Provider customer ID
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )

    # Linked documents
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True, index=True
    )

    # For recurring payments
    authorization_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    payment_subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_subscriptions.id"), nullable=True, index=True
    )

    # Virtual account (if paid via virtual account)
    virtual_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("virtual_accounts.id"), nullable=True, index=True
    )

    # Authorization URL (for redirect-based payments)
    authorization_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    callback_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Error handling
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)

    # IP address of payer
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Reconciliation
    reconciled: Mapped[bool] = mapped_column(default=False, index=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    bank_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=True
    )

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_gateway_transactions_provider_status", "provider", "status"),
        Index("ix_gateway_transactions_customer_status", "customer_id", "status"),
        Index("ix_gateway_transactions_invoice", "invoice_id"),
        Index("ix_gateway_transactions_initiated", "initiated_at"),
    )

    def __repr__(self) -> str:
        return f"<GatewayTransaction {self.reference} {self.status.value}>"

    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == GatewayTransactionStatus.SUCCESS

    @property
    def is_pending(self) -> bool:
        """Check if transaction is still pending."""
        return self.status in (
            GatewayTransactionStatus.PENDING,
            GatewayTransactionStatus.PROCESSING,
        )
