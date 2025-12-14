"""Supplier Payment model for AP payments."""
from __future__ import annotations

import enum
from sqlalchemy import String, Text, ForeignKey, Numeric, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.payment_allocation import PaymentAllocation


class SupplierPaymentStatus(enum.Enum):
    """Status of supplier payment."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    POSTED = "posted"
    CANCELLED = "cancelled"


class SupplierPayment(Base):
    """
    Payment made to suppliers/vendors.

    Supports allocation to multiple bills/debit notes,
    multi-currency, and workflow approval.
    """

    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Payment identification
    payment_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Supplier
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Payment method
    mode_of_payment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bank_accounts.id"), nullable=True)

    # Currency and amounts
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Allocation tracking
    total_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Deductions
    total_discount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_write_off: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_withholding_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Reference
    reference_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reference_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status and workflow
    status: Mapped[SupplierPaymentStatus] = mapped_column(
        Enum(SupplierPaymentStatus), default=SupplierPaymentStatus.DRAFT, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)  # 0=Draft, 1=Submitted, 2=Cancelled
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Links
    journal_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    fiscal_period_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fiscal_periods.id"), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    allocations: Mapped[List["PaymentAllocation"]] = relationship(
        back_populates="supplier_payment",
        foreign_keys="PaymentAllocation.supplier_payment_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SupplierPayment {self.payment_number} - {self.paid_amount} {self.currency}>"

    @property
    def is_fully_allocated(self) -> bool:
        """Check if payment is fully allocated."""
        return self.unallocated_amount <= Decimal("0.01")
