from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.credit_note import CreditNote


class InvoiceStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class InvoiceSource(enum.Enum):
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"


class Invoice(Base):
    """Customer invoices from Splynx and ERPNext."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    # Source system
    source: Mapped[InvoiceSource] = mapped_column(Enum(InvoiceSource), nullable=False, index=True)

    # Customer link
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    # Invoice details
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    balance: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING, index=True)

    # Dates
    invoice_date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    paid_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="invoices")
    payments: Mapped[List[Payment]] = relationship(back_populates="invoice")
    credit_notes: Mapped[List[CreditNote]] = relationship(back_populates="invoice")

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} - {self.total_amount} {self.currency}>"

    @property
    def days_overdue(self) -> int:
        """Number of days past due date."""
        if not self.due_date or self.status == InvoiceStatus.PAID:
            return 0
        if datetime.utcnow() > self.due_date:
            return (datetime.utcnow() - self.due_date).days
        return 0

    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0 and self.status not in [
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
        ]
