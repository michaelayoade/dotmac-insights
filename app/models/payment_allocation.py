"""Payment Allocation model for linking payments to documents."""
from __future__ import annotations

import enum
from sqlalchemy import String, Text, ForeignKey, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.supplier_payment import SupplierPayment


class AllocationType(enum.Enum):
    """Type of document being allocated to."""
    INVOICE = "invoice"
    BILL = "bill"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"


class DiscountType(enum.Enum):
    """Type of discount applied."""
    EARLY_PAYMENT = "early_payment"
    SETTLEMENT = "settlement"
    OTHER = "other"


class PaymentAllocation(Base):
    """
    Allocation of a payment to one or more documents.

    Supports customer payments (AR) and supplier payments (AP),
    with discounts, write-offs, and FX gain/loss tracking.
    """

    __tablename__ = "payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Payment links (one or the other, not both)
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True, index=True
    )
    supplier_payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier_payments.id"), nullable=True, index=True
    )

    # Document being allocated to
    allocation_type: Mapped[AllocationType] = mapped_column(Enum(AllocationType), nullable=False)
    document_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # Allocated amounts (in document currency)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    write_off_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Base currency amounts
    base_allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_write_off_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # FX
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    exchange_gain_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Discount details
    discount_type: Mapped[Optional[DiscountType]] = mapped_column(Enum(DiscountType), nullable=True)
    discount_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Write-off details
    write_off_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    write_off_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    payment: Mapped[Optional["Payment"]] = relationship(
        back_populates="allocations",
        foreign_keys=[payment_id],
    )
    supplier_payment: Mapped[Optional["SupplierPayment"]] = relationship(
        back_populates="allocations",
        foreign_keys=[supplier_payment_id],
    )

    def __repr__(self) -> str:
        return f"<PaymentAllocation {self.allocated_amount} to {self.allocation_type.value}:{self.document_id}>"

    @property
    def total_settled(self) -> Decimal:
        """Total amount that settles the document."""
        return self.allocated_amount + self.discount_amount + self.write_off_amount
