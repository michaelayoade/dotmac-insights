from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class InvoiceStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class InvoiceSource(enum.Enum):
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"


class Invoice(Base):
    """Customer invoices from Splynx and ERPNext."""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    # External IDs
    splynx_id = Column(Integer, index=True, nullable=True)
    erpnext_id = Column(String(255), index=True, nullable=True)

    # Source system
    source = Column(Enum(InvoiceSource), nullable=False, index=True)

    # Customer link
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)

    # Invoice details
    invoice_number = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)

    # Amounts
    amount = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    amount_paid = Column(Numeric(12, 2), default=0)
    balance = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), default="NGN")

    # Status
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING, index=True)

    # Dates
    invoice_date = Column(DateTime, nullable=False, index=True)
    due_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)

    # Categorization
    category = Column(String(100), nullable=True)  # e.g., "Internet", "Installation", "Equipment"

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")

    def __repr__(self):
        return f"<Invoice {self.invoice_number} - {self.total_amount} {self.currency}>"

    @property
    def days_overdue(self) -> int:
        """Number of days past due date."""
        if not self.due_date or self.status == InvoiceStatus.PAID:
            return 0
        if datetime.utcnow() > self.due_date:
            return (datetime.utcnow() - self.due_date).days
        return 0

    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0 and self.status not in [
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
        ]
