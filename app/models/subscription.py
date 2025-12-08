from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"


class Subscription(Base):
    """Customer service subscriptions (internet plans, etc.)."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    # External ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=True)

    # Customer link
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)

    # Plan details
    plan_name = Column(String(255), nullable=False)
    plan_code = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Pricing
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN")
    billing_cycle = Column(String(50), default="monthly")  # monthly, quarterly, yearly

    # Speed/Service details (for internet plans)
    download_speed = Column(Integer, nullable=True)  # in Mbps
    upload_speed = Column(Integer, nullable=True)  # in Mbps
    data_cap = Column(Integer, nullable=True)  # in GB, null = unlimited

    # Status
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, index=True)

    # Dates
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    cancelled_date = Column(DateTime, nullable=True)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="subscriptions")

    def __repr__(self):
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
