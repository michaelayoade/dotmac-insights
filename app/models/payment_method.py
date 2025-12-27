from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.database import Base


class PaymentMethod(Base):
    """Payment methods from Splynx (Cash, Bank Transfer, Card, etc.)."""

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Splynx ID
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Localized names (name_1 through name_5 for different languages)
    name_1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name_2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name_3: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name_4: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name_5: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Linked bank account
    accounting_bank_accounts_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # E-invoicing integration
    einvoicing_payment_methods_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<PaymentMethod {self.name}>"
