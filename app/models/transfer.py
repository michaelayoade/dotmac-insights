"""
Transfer Model

Outbound bank transfers (disbursements) via payment gateways.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Text, ForeignKey, Numeric, Index, JSON,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.gateway_transaction import GatewayProvider

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.supplier_payment import SupplierPayment


class TransferStatus(str, enum.Enum):
    """Transfer status."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"


class TransferType(str, enum.Enum):
    """Type of transfer."""
    SINGLE = "single"
    BULK = "bulk"
    PAYROLL = "payroll"
    VENDOR_PAYMENT = "vendor_payment"
    REFUND = "refund"


class Transfer(Base):
    """
    Outbound bank transfers.

    Records all disbursements made through payment gateways,
    including vendor payments, payroll, and refunds.
    """

    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider
    provider: Mapped[GatewayProvider] = mapped_column(
        SAEnum(GatewayProvider, name="gatewayprovider", create_constraint=False),
        nullable=False, index=True
    )

    # Reference (idempotency key)
    reference: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    provider_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    transfer_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Type
    transfer_type: Mapped[TransferType] = mapped_column(
        SAEnum(TransferType, name="transfertype"),
        default=TransferType.SINGLE, index=True
    )
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Recipient details
    recipient_account: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    recipient_bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Provider recipient ID

    # Amount
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Status
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, name="transferstatus"),
        default=TransferStatus.PENDING, index=True
    )
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Purpose
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    narration: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Bank narration (max 100 chars)

    # Links to other entities
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier_payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier_payments.id"), nullable=True, index=True
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    salary_slip_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("salary_slips.id"), nullable=True, index=True
    )
    payroll_run_id: Mapped[Optional[int]] = mapped_column(
        nullable=True, index=True
    )

    # For refund transfers
    original_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("gateway_transactions.id"), nullable=True
    )

    # Approval workflow
    requires_approval: Mapped[bool] = mapped_column(default=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rejected_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Retry handling
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)

    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
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

    __table_args__ = (
        Index("ix_transfer_provider_status", "provider", "status"),
        Index("ix_transfer_batch", "batch_id", "status"),
        Index("ix_transfer_supplier", "supplier_id", "status"),
        Index("ix_transfer_employee", "employee_id", "status"),
        Index("ix_transfer_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Transfer {self.reference} {self.amount} {self.status.value}>"

    @property
    def is_successful(self) -> bool:
        """Check if transfer was successful."""
        return self.status == TransferStatus.SUCCESS

    @property
    def is_pending(self) -> bool:
        """Check if transfer is still pending."""
        return self.status in (
            TransferStatus.PENDING,
            TransferStatus.QUEUED,
            TransferStatus.PROCESSING,
        )

    @property
    def can_retry(self) -> bool:
        """Check if transfer can be retried."""
        return (
            self.status == TransferStatus.FAILED
            and self.retry_count < self.max_retries
        )
