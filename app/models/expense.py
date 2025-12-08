from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum, ForeignKey
from datetime import datetime
import enum
from app.database import Base


class ExpenseStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class Expense(Base):
    """Expense records from ERPNext for cost analysis."""

    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)

    # External ID
    erpnext_id = Column(String(255), unique=True, index=True, nullable=True)

    # Expense details
    expense_type = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    vendor = Column(String(255), nullable=True)

    # Amounts
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN")

    # Categorization
    category = Column(String(255), nullable=True, index=True)  # e.g., "Bandwidth", "Salaries", "Equipment"
    cost_center = Column(String(255), nullable=True, index=True)  # e.g., specific POP or department
    pop_id = Column(Integer, ForeignKey("pops.id"), nullable=True, index=True)

    # Status
    status = Column(Enum(ExpenseStatus), default=ExpenseStatus.PAID, index=True)

    # Dates
    expense_date = Column(DateTime, nullable=False, index=True)
    posting_date = Column(DateTime, nullable=True)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Expense {self.expense_type} - {self.amount} {self.currency}>"
