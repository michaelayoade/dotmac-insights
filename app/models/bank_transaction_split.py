"""Bank Transaction Split model for categorizing bank transactions."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.accounting import BankTransaction


class BankTransactionSplit(Base):
    """
    Split line for bank transactions.

    Allows a single bank transaction to be allocated to multiple
    accounts/tax codes (e.g., a mixed expense with different tax rates).
    """

    __tablename__ = "bank_transaction_splits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    bank_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=False, index=True
    )

    # Amount in transaction currency
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Base currency amount
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Account allocation
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tax
    tax_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tax_codes.id"), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Description
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Party (if applicable)
    party_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    party: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="splits")

    def __repr__(self) -> str:
        return f"<BankTransactionSplit {self.amount} -> {self.account}>"
