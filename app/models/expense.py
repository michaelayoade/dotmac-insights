from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.pop import Pop
    from app.models.project import Project


class ExpenseStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    CANCELLED = "cancelled"


class Expense(Base):
    """Expense Claim records from ERPNext for cost analysis."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee FK
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    erpnext_employee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Project FK
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    erpnext_project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Expense details
    expense_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts
    total_claimed_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_sanctioned_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_amount_reimbursed: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_advance_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Taxes
    total_taxes_and_charges: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    pop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pops.id"), nullable=True, index=True)

    # Company
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Accounting
    payable_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mode_of_payment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    clearance_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Approval
    approval_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    expense_approver: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.DRAFT, index=True)
    is_paid: Mapped[bool] = mapped_column(default=False)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Dates
    expense_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    # Task (if linked)
    task: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee: Mapped[Optional[Employee]] = relationship(back_populates="expenses")
    project: Mapped[Optional[Project]] = relationship(back_populates="expenses")
    pop: Mapped[Optional[Pop]] = relationship(back_populates="expenses")

    def __repr__(self) -> str:
        return f"<Expense {self.erpnext_id} - {self.total_claimed_amount} {self.currency}>"

    @property
    def outstanding_amount(self) -> Decimal:
        """Calculate outstanding amount to be reimbursed."""
        return self.total_sanctioned_amount - self.total_amount_reimbursed
