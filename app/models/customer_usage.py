from __future__ import annotations

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.subscription import Subscription


class CustomerUsage(Base):
    """Daily traffic/bandwidth usage per customer service from Splynx."""

    __tablename__ = "customer_usage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subscriptions.id"), nullable=True, index=True)

    # Splynx reference
    splynx_service_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Usage data
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    upload_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    download_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Sync metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="usage_records")
    subscription: Mapped[Optional[Subscription]] = relationship()

    # Indexes for analytics queries
    __table_args__ = (
        Index("ix_usage_customer_date", "customer_id", "usage_date"),
        Index("ix_usage_date", "usage_date"),
        Index("ix_usage_service_date", "splynx_service_id", "usage_date", unique=True),
    )

    def __repr__(self) -> str:
        total_gb = (self.upload_bytes + self.download_bytes) / (1024 ** 3)
        return f"<CustomerUsage customer={self.customer_id} date={self.usage_date} total={total_gb:.2f}GB>"

    @property
    def total_bytes(self) -> int:
        return self.upload_bytes + self.download_bytes

    @property
    def upload_gb(self) -> float:
        return self.upload_bytes / (1024 ** 3)

    @property
    def download_gb(self) -> float:
        return self.download_bytes / (1024 ** 3)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 ** 3)
