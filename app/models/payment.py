from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    OTHER = "other"


class PaymentSource(enum.Enum):
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"


class Payment(Base):
    """Payment records from all sources."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    # Source system
    source: Mapped[PaymentSource] = mapped_column(Enum(PaymentSource), nullable=False, index=True)

    # Links
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)

    # Payment details
    receipt_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Method & Status
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), default=PaymentMethod.BANK_TRANSFER)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.COMPLETED, index=True)

    # Transaction reference
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gateway_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    payment_date: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="payments")
    invoice: Mapped[Optional[Invoice]] = relationship(back_populates="payments")

    __table_args__ = (
        Index(
            "uq_payments_splynx_id_not_null",
            "splynx_id",
            unique=True,
            postgresql_where=text("splynx_id IS NOT NULL"),
        ),
        Index(
            "uq_payments_erpnext_id_not_null",
            "erpnext_id",
            unique=True,
            postgresql_where=text("erpnext_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Payment {self.receipt_number} - {self.amount} {self.currency}>"
