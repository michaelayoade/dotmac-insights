from __future__ import annotations

from sqlalchemy import String, Text, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from decimal import Decimal
from typing import Optional
import enum
from app.database import Base


class TariffType(enum.Enum):
    INTERNET = "internet"
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class Tariff(Base):
    """Tariffs/Plans from Splynx."""

    __tablename__ = "tariffs"
    __table_args__ = (
        UniqueConstraint('splynx_id', 'tariff_type', name='uq_tariff_splynx_id_type'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID (unique per tariff_type)
    splynx_id: Mapped[int] = mapped_column(index=True, nullable=False)

    # Tariff type
    tariff_type: Mapped[TariffType] = mapped_column(Enum(TariffType), default=TariffType.INTERNET, index=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Tax
    vat_percent: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    with_vat: Mapped[bool] = mapped_column(default=True)

    # Speed (for internet tariffs)
    speed_download: Mapped[Optional[int]] = mapped_column(nullable=True)
    speed_upload: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Availability
    available_for_services: Mapped[bool] = mapped_column(default=True)
    show_on_customer_portal: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)

    # Billing
    billing_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<Tariff {self.title} ({self.tariff_type.value})>"
