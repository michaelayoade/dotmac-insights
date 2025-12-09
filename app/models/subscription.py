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


class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"


class SubscriptionType(enum.Enum):
    INTERNET = "internet"
    VOICE = "voice"
    CUSTOM = "custom"
    BUNDLE = "bundle"


class Subscription(Base):
    """Customer service subscriptions (internet plans, etc.)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)

    # Customer link
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)

    # Tariff/Plan link
    tariff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tariffs.id"), nullable=True, index=True)
    splynx_tariff_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    # Service type
    service_type: Mapped[SubscriptionType] = mapped_column(
        Enum(SubscriptionType), default=SubscriptionType.INTERNET, index=True
    )

    # Plan details
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pricing
    price: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    billing_cycle: Mapped[str] = mapped_column(String(50), default="monthly")

    # Speed/Service details (for internet plans)
    download_speed: Mapped[Optional[int]] = mapped_column(nullable=True)
    upload_speed: Mapped[Optional[int]] = mapped_column(nullable=True)
    data_cap: Mapped[Optional[int]] = mapped_column(nullable=True)

    # IP Address assignment
    ipv4_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    ipv6_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Router/NAS assignment
    router_id: Mapped[Optional[int]] = mapped_column(ForeignKey("routers.id"), nullable=True, index=True)

    # Status
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, index=True)

    # Dates
    start_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancelled_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    tariff = relationship("Tariff", backref="subscriptions")
    router = relationship("Router", backref="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription {self.plan_name} - {self.customer_id}>"

    @property
    def mrr(self) -> float:
        """Monthly Recurring Revenue for this subscription."""
        if self.status != SubscriptionStatus.ACTIVE:
            return 0.0
        if self.billing_cycle == "monthly":
            return float(self.price)
        elif self.billing_cycle == "quarterly":
            return float(self.price) / 3
        elif self.billing_cycle == "yearly":
            return float(self.price) / 12
        return float(self.price)
