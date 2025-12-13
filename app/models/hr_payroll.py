"""Payroll models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.auth import User


# ============= ENUMS =============
class SalaryComponentType(enum.Enum):
    EARNING = "earning"
    DEDUCTION = "deduction"


class SalarySlipStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"
    # New statuses
    PAID = "paid"
    VOIDED = "voided"


# ============= SALARY COMPONENT =============
class SalaryComponent(Base):
    """Salary Component - earnings and deductions types."""

    __tablename__ = "salary_components"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    salary_component_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    salary_component_abbr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type: Mapped[SalaryComponentType] = mapped_column(
        Enum(SalaryComponentType), default=SalaryComponentType.EARNING, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tax settings
    is_tax_applicable: Mapped[bool] = mapped_column(default=False)
    is_payable: Mapped[bool] = mapped_column(default=True)
    is_flexible_benefit: Mapped[bool] = mapped_column(default=False)
    depends_on_payment_days: Mapped[bool] = mapped_column(default=True)
    variable_based_on_taxable_salary: Mapped[bool] = mapped_column(default=False)
    exempted_from_income_tax: Mapped[bool] = mapped_column(default=False)

    # Display settings
    statistical_component: Mapped[bool] = mapped_column(default=False)
    do_not_include_in_total: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Accounts
    default_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SalaryComponent {self.salary_component_name} ({self.type.value})>"


# ============= SALARY STRUCTURE =============
class SalaryStructure(Base):
    """Salary Structure - pay structure templates."""

    __tablename__ = "salary_structures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    salary_structure_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[str] = mapped_column(String(10), default="Yes")  # ERPNext uses "Yes"/"No"
    payroll_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Monthly, Biweekly, etc.
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Payment settings
    payment_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mode_of_payment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    earnings: Mapped[List["SalaryStructureEarning"]] = relationship(
        back_populates="salary_structure", cascade="all, delete-orphan"
    )
    deductions: Mapped[List["SalaryStructureDeduction"]] = relationship(
        back_populates="salary_structure", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SalaryStructure {self.salary_structure_name}>"


# ============= SALARY STRUCTURE EARNING (Child Table) =============
class SalaryStructureEarning(Base):
    """Salary Structure Earning - earning components in a salary structure."""

    __tablename__ = "salary_structure_earnings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    salary_structure_id: Mapped[int] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    salary_component: Mapped[str] = mapped_column(String(255), nullable=False)
    abbr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    amount_based_on_formula: Mapped[bool] = mapped_column(default=False)
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    statistical_component: Mapped[bool] = mapped_column(default=False)
    do_not_include_in_total: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    salary_structure: Mapped["SalaryStructure"] = relationship(back_populates="earnings")

    def __repr__(self) -> str:
        return f"<SalaryStructureEarning {self.salary_component}: {self.amount}>"


# ============= SALARY STRUCTURE DEDUCTION (Child Table) =============
class SalaryStructureDeduction(Base):
    """Salary Structure Deduction - deduction components in a salary structure."""

    __tablename__ = "salary_structure_deductions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    salary_structure_id: Mapped[int] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    salary_component: Mapped[str] = mapped_column(String(255), nullable=False)
    abbr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    amount_based_on_formula: Mapped[bool] = mapped_column(default=False)
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    statistical_component: Mapped[bool] = mapped_column(default=False)
    do_not_include_in_total: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    salary_structure: Mapped["SalaryStructure"] = relationship(back_populates="deductions")

    def __repr__(self) -> str:
        return f"<SalaryStructureDeduction {self.salary_component}: {self.amount}>"


# ============= SALARY STRUCTURE ASSIGNMENT =============
class SalaryStructureAssignment(Base):
    """Salary Structure Assignment - assigns salary structure to employees."""

    __tablename__ = "salary_structure_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Salary structure
    salary_structure: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    salary_structure_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("salary_structures.id"), nullable=True, index=True
    )

    # Assignment details
    from_date: Mapped[date] = mapped_column(nullable=False, index=True)
    base: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    variable: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    income_tax_slab: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_salary_struct_assign_emp_date", "employee_id", "from_date"),
    )

    def __repr__(self) -> str:
        return f"<SalaryStructureAssignment {self.employee} - {self.salary_structure}>"


# ============= PAYROLL ENTRY =============
class PayrollEntry(Base):
    """Payroll Entry - bulk payroll processing runs."""

    __tablename__ = "payroll_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    posting_date: Mapped[date] = mapped_column(nullable=False, index=True)
    payroll_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_date: Mapped[date] = mapped_column(nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(nullable=False)

    # Organization filters
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Currency
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(default=Decimal("1"))

    # Payment
    payment_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status flags
    salary_slips_created: Mapped[bool] = mapped_column(default=False)
    salary_slips_submitted: Mapped[bool] = mapped_column(default=False)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_payroll_entries_period", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<PayrollEntry {self.start_date} to {self.end_date}>"


# ============= SALARY SLIP =============
class SalarySlip(Base):
    """Salary Slip - employee monthly payslip."""

    __tablename__ = "salary_slips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Salary structure
    salary_structure: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Period
    posting_date: Mapped[date] = mapped_column(nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(nullable=False)
    payroll_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Payment days
    total_working_days: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    absent_days: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    payment_days: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    leave_without_pay: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Amounts
    gross_pay: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_deduction: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    net_pay: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    rounded_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Status
    status: Mapped[SalarySlipStatus] = mapped_column(
        Enum(SalarySlipStatus), default=SalarySlipStatus.DRAFT, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)

    # Bank details
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_account_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Payroll entry link
    payroll_entry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Payment tracking
    paid_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    paid_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_mode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Void tracking
    voided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    voided_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    earnings: Mapped[List["SalarySlipEarning"]] = relationship(
        back_populates="salary_slip", cascade="all, delete-orphan"
    )
    deductions: Mapped[List["SalarySlipDeduction"]] = relationship(
        back_populates="salary_slip", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_salary_slips_emp_period", "employee_id", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<SalarySlip {self.employee} - {self.start_date} to {self.end_date}: {self.net_pay}>"


# ============= SALARY SLIP EARNING (Child Table) =============
class SalarySlipEarning(Base):
    """Salary Slip Earning - earning line items on a salary slip."""

    __tablename__ = "salary_slip_earnings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    salary_slip_id: Mapped[int] = mapped_column(
        ForeignKey("salary_slips.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    salary_component: Mapped[str] = mapped_column(String(255), nullable=False)
    abbr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    default_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    additional_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    year_to_date: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    statistical_component: Mapped[bool] = mapped_column(default=False)
    do_not_include_in_total: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    salary_slip: Mapped["SalarySlip"] = relationship(back_populates="earnings")

    def __repr__(self) -> str:
        return f"<SalarySlipEarning {self.salary_component}: {self.amount}>"


# ============= SALARY SLIP DEDUCTION (Child Table) =============
class SalarySlipDeduction(Base):
    """Salary Slip Deduction - deduction line items on a salary slip."""

    __tablename__ = "salary_slip_deductions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    salary_slip_id: Mapped[int] = mapped_column(
        ForeignKey("salary_slips.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    salary_component: Mapped[str] = mapped_column(String(255), nullable=False)
    abbr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    default_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    additional_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    year_to_date: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    statistical_component: Mapped[bool] = mapped_column(default=False)
    do_not_include_in_total: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    salary_slip: Mapped["SalarySlip"] = relationship(back_populates="deductions")

    def __repr__(self) -> str:
        return f"<SalarySlipDeduction {self.salary_component}: {self.amount}>"
