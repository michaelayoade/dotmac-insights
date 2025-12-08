from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class CustomerStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PROSPECT = "prospect"


class CustomerType(enum.Enum):
    RESIDENTIAL = "residential"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class Customer(Base):
    """Unified customer record from all sources."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    # External IDs for linking across systems
    splynx_id = Column(Integer, unique=True, index=True, nullable=True)
    erpnext_id = Column(String(255), unique=True, index=True, nullable=True)
    chatwoot_contact_id = Column(Integer, index=True, nullable=True)

    # Basic info
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    phone_secondary = Column(String(50), nullable=True)

    # Address
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)

    # Classification
    customer_type = Column(Enum(CustomerType), default=CustomerType.RESIDENTIAL)
    status = Column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE, index=True)

    # Location/POP
    pop_id = Column(Integer, ForeignKey("pops.id"), nullable=True, index=True)

    # Account info
    account_number = Column(String(100), nullable=True, unique=True)
    contract_number = Column(String(100), nullable=True)

    # Dates
    signup_date = Column(DateTime, nullable=True)
    activation_date = Column(DateTime, nullable=True)
    cancellation_date = Column(DateTime, nullable=True)
    contract_end_date = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pop = relationship("Pop", back_populates="customers")
    subscriptions = relationship("Subscription", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")
    conversations = relationship("Conversation", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.name} ({self.status.value})>"

    @property
    def is_churned(self) -> bool:
        return self.status == CustomerStatus.CANCELLED and self.cancellation_date is not None

    @property
    def tenure_days(self) -> int:
        """Days since signup."""
        if not self.signup_date:
            return 0
        end_date = self.cancellation_date or datetime.utcnow()
        return (end_date - self.signup_date).days
