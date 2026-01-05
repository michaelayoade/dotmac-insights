from __future__ import annotations

from sqlalchemy import BigInteger, String, Text, ForeignKey, Enum, Index, text, Numeric, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base, SoftDeleteMixin
from app.models.validation import SoftValidationMixin
from app.models.document_lines import InvoiceLine
from app.models.payment_allocation import PaymentAllocation, AllocationType

if TYPE_CHECKING:
    from app.models.party import CustomerAccount
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
    INTERNAL = "internal"


class Invoice(SoftValidationMixin, SoftDeleteMixin, Base):
    """Customer invoices from Splynx, ERPNext, or internal creation."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    # Source system
    source: Mapped[InvoiceSource] = mapped_column(Enum(InvoiceSource), nullable=False, index=True)

    # Customer account link (party-based identity)
    customer_account_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

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

    # Audit columns
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    # deleted_by_id provided by SoftDeleteMixin

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
    customer_account: Mapped[Optional["CustomerAccount"]] = relationship(foreign_keys=[customer_account_id])
    payments: Mapped[List[Payment]] = relationship(back_populates="invoice")
    credit_notes: Mapped[List[CreditNote]] = relationship(back_populates="invoice")
    lines: Mapped[List[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by=InvoiceLine.idx,
    )
    allocations: Mapped[List[PaymentAllocation]] = relationship(
        primaryjoin=lambda: and_(
            PaymentAllocation.allocation_type == AllocationType.INVOICE,
            PaymentAllocation.document_id == Invoice.id,
        ),
        foreign_keys=[PaymentAllocation.document_id],
        viewonly=True,
    )

    __table_args__ = (
        Index(
            "ix_invoices_status_currency",
            "status",
            "currency",
        ),
        Index(
            "ix_invoices_due_status_currency",
            "due_date",
            "status",
            "currency",
            postgresql_where=text(
                "status IN ('pending','overdue','partially_paid')"
            ),
        ),
        Index("ix_invoices_payment_terms_id", "payment_terms_id"),
        Index("ix_invoices_fiscal_period_id", "fiscal_period_id"),
        Index("ix_invoices_journal_entry_id", "journal_entry_id"),
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
        # Audit column indexes
        Index("ix_invoices_created_by_id", "created_by_id"),
        Index("ix_invoices_updated_by_id", "updated_by_id"),
        Index("ix_invoices_deleted_by_id", "deleted_by_id"),
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} - {self.total_amount} {self.currency}>"

    @property
    def days_overdue(self) -> int:
        """Number of days past due date."""
        if not self.due_date or self.status == InvoiceStatus.PAID:
            return 0
        now = datetime.now(timezone.utc)
        due = self.due_date
        # Handle timezone-naive vs timezone-aware comparison
        if due.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif due.tzinfo is not None and now.tzinfo is None:
            due = due.replace(tzinfo=None)
        if now > due:
            return (now - due).days
        return 0

    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0 and self.status not in [
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
        ]
