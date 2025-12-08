from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    OTHER = "other"


class PaymentSource(enum.Enum):
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"


class Payment(Base):
    """Payment records from all sources."""

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    # External IDs
    splynx_id = Column(Integer, index=True, nullable=True)
    erpnext_id = Column(String(255), index=True, nullable=True)

    # Source system
    source = Column(Enum(PaymentSource), nullable=False, index=True)

    # Links
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)

    # Payment details
    receipt_number = Column(String(100), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN")

    # Method & Status
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.BANK_TRANSFER)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.COMPLETED, index=True)

    # Transaction reference
    transaction_reference = Column(String(255), nullable=True)
    gateway_reference = Column(String(255), nullable=True)

    # Dates
    payment_date = Column(DateTime, nullable=False, index=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.receipt_number} - {self.amount} {self.currency}>"
