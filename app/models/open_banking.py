"""
Open Banking Connection Model

Linked bank accounts via Mono, Okra, etc.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, ForeignKey, Numeric, Index, JSON,
    Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.accounting import BankAccount


class OpenBankingProvider(str, enum.Enum):
    """Open banking providers."""
    MONO = "mono"
    OKRA = "okra"


class ConnectionStatus(str, enum.Enum):
    """Connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REAUTHORIZATION_REQUIRED = "reauthorization_required"
    FAILED = "failed"
    SYNCING = "syncing"


class OpenBankingConnection(Base):
    """
    Linked bank accounts via open banking.

    Stores connections to customer bank accounts for
    transaction history, balance checks, and identity verification.
    """

    __tablename__ = "open_banking_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider
    provider: Mapped[OpenBankingProvider] = mapped_column(
        SAEnum(OpenBankingProvider, name="openbankingprovider"),
        nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Provider's account ID

    # Account details
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # savings, current, domiciliary
    currency: Mapped[str] = mapped_column(String(3), default="NGN")

    # Customer/Company link
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )  # For company accounts

    # Identity information
    bvn: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[ConnectionStatus] = mapped_column(
        SAEnum(ConnectionStatus, name="connectionstatus"),
        default=ConnectionStatus.CONNECTED, index=True
    )
    status_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Sync tracking
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    sync_start_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Earliest transaction synced
    sync_end_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Latest transaction synced
    total_transactions_synced: Mapped[int] = mapped_column(default=0)

    # Cached balance
    cached_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    balance_updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Link to internal bank account record
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=True
    )

    # Authorization details
    authorization_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    reauth_required_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reauth_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_account_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    connected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "provider", "account_id",
            name="uq_open_banking_provider_account"
        ),
        Index("ix_open_banking_customer", "customer_id", "status"),
        Index("ix_open_banking_company", "company", "status"),
    )

    def __repr__(self) -> str:
        return f"<OpenBankingConnection {self.provider.value} {self.account_number}>"

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.status == ConnectionStatus.CONNECTED

    @property
    def needs_reauthorization(self) -> bool:
        """Check if reauthorization is needed."""
        return self.status == ConnectionStatus.REAUTHORIZATION_REQUIRED

    @property
    def display_account(self) -> str:
        """Get masked account number for display."""
        if len(self.account_number) > 4:
            return f"****{self.account_number[-4:]}"
        return self.account_number
