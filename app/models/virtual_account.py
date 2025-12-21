"""
Virtual Account Model

Dedicated virtual bank accounts for payment collection.
Customers can pay via bank transfer to these accounts.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, ForeignKey, Numeric, Index,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.utils.datetime_utils import utc_now

from app.database import Base
from app.models.gateway_transaction import GatewayProvider

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice


class VirtualAccountStatus(str, enum.Enum):
    """Virtual account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    EXPIRED = "expired"


class VirtualAccount(Base):
    """
    Virtual bank accounts for collections.

    Virtual accounts allow customers to pay via bank transfer.
    Each virtual account is mapped to a real account at the bank
    and payments are automatically attributed to the customer.
    """

    __tablename__ = "virtual_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider info
    provider: Mapped[GatewayProvider] = mapped_column(
        SAEnum(GatewayProvider, name="gatewayprovider", create_constraint=False),
        nullable=False, index=True
    )
    provider_reference: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Account details
    account_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    bank_slug: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Ownership
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dedicated VA for specific invoice
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
    )

    # Status
    status: Mapped[VirtualAccountStatus] = mapped_column(
        SAEnum(VirtualAccountStatus, name="virtualaccountstatus"),
        default=VirtualAccountStatus.ACTIVE, index=True
    )

    # Account type
    is_permanent: Mapped[bool] = mapped_column(default=True)  # vs single-use
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Expected amount (for single-use accounts)
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN")

    # Usage stats
    total_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0")
    )
    transaction_count: Mapped[int] = mapped_column(default=0)
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_va_provider_status", "provider", "status"),
        Index("ix_va_customer", "customer_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<VirtualAccount {self.account_number} {self.bank_name}>"

    @property
    def is_active(self) -> bool:
        """Check if account is active."""
        if self.status != VirtualAccountStatus.ACTIVE:
            return False
        if self.expires_at and utc_now() > self.expires_at:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if account has expired."""
        if self.expires_at and utc_now() > self.expires_at:
            return True
        return False
