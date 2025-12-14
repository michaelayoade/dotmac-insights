from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.credit_note import CreditNote
    from app.models.document_lines import InvoiceLine
    from app.models.payment_allocation import PaymentAllocation


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
    INTERNAL = "internal"


class Invoice(Base):
    """Customer invoices from Splynx, ERPNext, or internal creation."""

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

    # Customer info (denormalized for documents)
    customer_tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts (document currency)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    balance: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX fields (base currency)
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Payment terms
    payment_terms_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_terms_templates.id"), nullable=True
    )

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING, index=True)

    # Workflow
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)  # 0=Draft, 1=Submitted, 2=Cancelled

    # Dates
    invoice_date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    paid_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Additional links
    fiscal_period_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fiscal_periods.id"), nullable=True)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="invoices")
    payments: Mapped[List[Payment]] = relationship(back_populates="invoice")
    credit_notes: Mapped[List[CreditNote]] = relationship(back_populates="invoice")
    lines: Mapped[List["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.idx",
    )
    allocations: Mapped[List["PaymentAllocation"]] = relationship(
        primaryjoin="and_(PaymentAllocation.allocation_type=='invoice', PaymentAllocation.document_id==Invoice.id)",
        foreign_keys="PaymentAllocation.document_id",
        viewonly=True,
    )

    __table_args__ = (
        Index(
            "uq_invoices_splynx_id_not_null",
            "splynx_id",
            unique=True,
            postgresql_where=text("splynx_id IS NOT NULL"),
        ),
        Index(
            "uq_invoices_erpnext_id_not_null",
            "erpnext_id",
            unique=True,
            postgresql_where=text("erpnext_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} - {self.total_amount} {self.currency}>"

    @property
    def days_overdue(self) -> int:
        """Number of days past due date."""
        if not self.due_date or self.status == InvoiceStatus.PAID:
            return 0
        now = datetime.now(timezone.utc)
        if now > self.due_date:
            return (now - self.due_date).days
        return 0

    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0 and self.status not in [
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
        ]
