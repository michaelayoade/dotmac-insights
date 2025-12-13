"""Leave Management models for ERPNext HR Module sync."""
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
class LeaveApplicationStatus(enum.Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveAllocationStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


# ============= LEAVE TYPE =============
class LeaveType(Base):
    """Leave Type reference - types of leave available (PTO, Sick, etc.)."""

    __tablename__ = "leave_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    leave_type_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    max_leaves_allowed: Mapped[int] = mapped_column(default=0)
    max_continuous_days_allowed: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Leave characteristics
    is_carry_forward: Mapped[bool] = mapped_column(default=False)
    is_lwp: Mapped[bool] = mapped_column(default=False)  # Leave Without Pay
    is_optional_leave: Mapped[bool] = mapped_column(default=False)
    is_compensatory: Mapped[bool] = mapped_column(default=False)
    allow_encashment: Mapped[bool] = mapped_column(default=False)
    include_holiday: Mapped[bool] = mapped_column(default=False)

    # Earned leave settings
    is_earned_leave: Mapped[bool] = mapped_column(default=False)
    earned_leave_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rounding: Mapped[Decimal] = mapped_column(default=Decimal("0.5"))

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LeaveType {self.leave_type_name}>"


# ============= HOLIDAY LIST =============
class HolidayList(Base):
    """Holiday List - company holidays for a year."""

    __tablename__ = "holiday_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    holiday_list_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    to_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    total_holidays: Mapped[int] = mapped_column(default=0)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    weekly_off: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "Sunday"

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    holidays: Mapped[List["Holiday"]] = relationship(
        back_populates="holiday_list", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<HolidayList {self.holiday_list_name}>"


# ============= HOLIDAY (Child Table) =============
class Holiday(Base):
    """Holiday - individual holiday entries in a Holiday List."""

    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    holiday_list_id: Mapped[int] = mapped_column(
        ForeignKey("holiday_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    holiday_date: Mapped[date] = mapped_column(nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    weekly_off: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    holiday_list: Mapped["HolidayList"] = relationship(back_populates="holidays")

    __table_args__ = (
        Index("ix_holidays_list_date", "holiday_list_id", "holiday_date"),
    )

    def __repr__(self) -> str:
        return f"<Holiday {self.holiday_date} - {self.description}>"


# ============= LEAVE POLICY =============
class LeavePolicy(Base):
    """Leave Policy - defines leave allocations per year by type."""

    __tablename__ = "leave_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    leave_policy_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    details: Mapped[List["LeavePolicyDetail"]] = relationship(
        back_populates="leave_policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LeavePolicy {self.leave_policy_name}>"


# ============= LEAVE POLICY DETAIL (Child Table) =============
class LeavePolicyDetail(Base):
    """Leave Policy Detail - individual leave type allocations in a policy."""

    __tablename__ = "leave_policy_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    leave_policy_id: Mapped[int] = mapped_column(
        ForeignKey("leave_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    leave_type: Mapped[str] = mapped_column(String(255), nullable=False)
    leave_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leave_types.id"), nullable=True, index=True
    )
    annual_allocation: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    leave_policy: Mapped["LeavePolicy"] = relationship(back_populates="details")

    def __repr__(self) -> str:
        return f"<LeavePolicyDetail {self.leave_type}: {self.annual_allocation}>"


# ============= LEAVE ALLOCATION =============
class LeaveAllocation(Base):
    """Leave Allocation - employee leave balance for a period."""

    __tablename__ = "leave_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Leave type
    leave_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    leave_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leave_types.id"), nullable=True, index=True
    )

    # Period
    from_date: Mapped[date] = mapped_column(nullable=False, index=True)
    to_date: Mapped[date] = mapped_column(nullable=False)

    # Allocation amounts
    new_leaves_allocated: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_leaves_allocated: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    unused_leaves: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    carry_forwarded_leaves: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    carry_forwarded_leaves_count: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Policy reference
    leave_policy: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[LeaveAllocationStatus] = mapped_column(
        Enum(LeaveAllocationStatus), default=LeaveAllocationStatus.DRAFT
    )
    docstatus: Mapped[int] = mapped_column(default=0)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
        Index("ix_leave_allocations_emp_type_period", "employee_id", "leave_type_id", "from_date"),
    )

    def __repr__(self) -> str:
        return f"<LeaveAllocation {self.employee} - {self.leave_type}: {self.total_leaves_allocated}>"


# ============= LEAVE APPLICATION =============
class LeaveApplication(Base):
    """Leave Application - employee leave requests."""

    __tablename__ = "leave_applications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Leave type
    leave_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    leave_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leave_types.id"), nullable=True, index=True
    )

    # Leave period
    from_date: Mapped[date] = mapped_column(nullable=False, index=True)
    to_date: Mapped[date] = mapped_column(nullable=False)
    half_day: Mapped[bool] = mapped_column(default=False)
    half_day_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    total_leave_days: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval
    leave_approver: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    leave_approver_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[LeaveApplicationStatus] = mapped_column(
        Enum(LeaveApplicationStatus), default=LeaveApplicationStatus.OPEN, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)
    posting_date: Mapped[date] = mapped_column(nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
        Index("ix_leave_applications_emp_dates", "employee_id", "from_date", "to_date"),
    )

    def __repr__(self) -> str:
        return f"<LeaveApplication {self.employee} - {self.leave_type} ({self.from_date} to {self.to_date})>"
