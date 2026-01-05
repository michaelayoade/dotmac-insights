from __future__ import annotations

from sqlalchemy import BigInteger, String, Text, ForeignKey, Enum, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base, SoftDeleteMixin
from app.models.validation import SoftValidationMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.document_lines import CreditNoteLine
    from app.models.party import CustomerAccount


class CreditNoteStatus(enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class CreditNote(SoftValidationMixin, SoftDeleteMixin, Base):
    """Credit notes/adjustments issued to customers."""

    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Customer account link (party-based identity)
    customer_account_id: Mapped[Optional[int]] = mapped_column(
        "customer_id",
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=True)

    # Details
    credit_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts (document currency)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX fields (base currency)
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Status & dates
    status: Mapped[CreditNoteStatus] = mapped_column(Enum(CreditNoteStatus), default=CreditNoteStatus.DRAFT, index=True)
    issue_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    applied_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Workflow
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)  # 0=Draft, 1=Submitted, 2=Cancelled

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
    origin_system: Mapped[str] = mapped_column(String(50), default="local")
    write_back_status: Mapped[str] = mapped_column(String(50), default="pending")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer_account: Mapped[Optional["CustomerAccount"]] = relationship(foreign_keys=[customer_account_id])
    invoice: Mapped[Optional[Invoice]] = relationship(back_populates="credit_notes")
    lines: Mapped[List["CreditNoteLine"]] = relationship(
        back_populates="credit_note",
        cascade="all, delete-orphan",
        order_by="CreditNoteLine.idx",
    )

    __table_args__ = (
        Index("ix_credit_notes_posting_date", "posting_date"),
        Index("ix_credit_notes_fiscal_period_id", "fiscal_period_id"),
        # Audit column indexes
        Index("ix_credit_notes_created_by_id", "created_by_id"),
        Index("ix_credit_notes_updated_by_id", "updated_by_id"),
        Index("ix_credit_notes_deleted_by_id", "deleted_by_id"),
    )

    def __repr__(self) -> str:
        return f"<CreditNote {self.credit_number} - {self.amount} {self.currency}>"
