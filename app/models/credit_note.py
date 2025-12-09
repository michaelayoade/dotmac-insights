from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice


class CreditNoteStatus(enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class CreditNote(Base):
    """Credit notes/adjustments issued to customers (Splynx)."""

    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Links
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=True)

    # Details
    credit_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Status & dates
    status: Mapped[CreditNoteStatus] = mapped_column(Enum(CreditNoteStatus), default=CreditNoteStatus.ISSUED, index=True)
    issue_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    applied_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="credit_notes")
    invoice: Mapped[Optional[Invoice]] = relationship(back_populates="credit_notes")

    def __repr__(self) -> str:
        return f"<CreditNote {self.credit_number} - {self.amount} {self.currency}>"
