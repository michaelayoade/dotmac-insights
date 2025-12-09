from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.pop import Pop
    from app.models.subscription import Subscription
    from app.models.invoice import Invoice
    from app.models.payment import Payment
    from app.models.conversation import Conversation
    from app.models.credit_note import CreditNote
    from app.models.ticket import Ticket
    from app.models.project import Project


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


class BillingType(enum.Enum):
    PREPAID = "prepaid"
    PREPAID_MONTHLY = "prepaid_monthly"
    RECURRING = "recurring"


class Customer(Base):
    """Unified customer record from all sources."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs for linking across systems
    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    zoho_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    billing_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone_secondary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Address
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address_2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gps: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Classification
    customer_type: Mapped[CustomerType] = mapped_column(Enum(CustomerType), default=CustomerType.RESIDENTIAL)
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE, index=True)
    billing_type: Mapped[Optional[BillingType]] = mapped_column(Enum(BillingType), nullable=True)

    # Location/POP
    pop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pops.id"), nullable=True, index=True)

    # Network/Infrastructure - from Splynx additional_attributes
    base_station: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    building_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Account info
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Financial
    mrr: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    daily_prepaid_cost: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Partner/Reseller
    partner_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    # Dates
    signup_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    activation_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancellation_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    contract_end_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    conversion_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_online: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Attribution
    added_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    added_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Labels/Tags (stored as comma-separated string)
    labels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pop: Mapped[Optional[Pop]] = relationship(back_populates="customers")
    subscriptions: Mapped[List[Subscription]] = relationship(back_populates="customer")
    invoices: Mapped[List[Invoice]] = relationship(back_populates="customer")
    payments: Mapped[List[Payment]] = relationship(back_populates="customer")
    conversations: Mapped[List[Conversation]] = relationship(back_populates="customer")
    credit_notes: Mapped[List[CreditNote]] = relationship(back_populates="customer")
    tickets: Mapped[List[Ticket]] = relationship(back_populates="customer")
    projects: Mapped[List[Project]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
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
