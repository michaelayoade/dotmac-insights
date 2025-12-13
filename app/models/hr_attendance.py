"""Attendance models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.auth import User


# ============= ENUMS =============
class AttendanceStatus(enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    ON_LEAVE = "on_leave"
    HALF_DAY = "half_day"
    WORK_FROM_HOME = "work_from_home"


class AttendanceRequestStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ============= SHIFT TYPE =============
class ShiftType(Base):
    """Shift Type - shift definitions with timing and rules."""

    __tablename__ = "shift_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    shift_type_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Working hours thresholds
    working_hours_threshold_for_half_day: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    working_hours_threshold_for_absent: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Check-in/out settings
    determine_check_in_and_check_out: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    begin_check_in_before_shift_start_time: Mapped[int] = mapped_column(default=0)
    allow_check_out_after_shift_end_time: Mapped[int] = mapped_column(default=0)

    # Auto attendance
    enable_auto_attendance: Mapped[bool] = mapped_column(default=False)

    # Grace periods
    enable_entry_grace_period: Mapped[bool] = mapped_column(default=False)
    late_entry_grace_period: Mapped[int] = mapped_column(default=0)
    enable_exit_grace_period: Mapped[bool] = mapped_column(default=False)
    early_exit_grace_period: Mapped[int] = mapped_column(default=0)

    # Holiday list reference
    holiday_list: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ShiftType {self.shift_type_name}>"


# ============= SHIFT ASSIGNMENT =============
class ShiftAssignment(Base):
    """Shift Assignment - employee shift assignments for a period."""

    __tablename__ = "shift_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Shift type
    shift_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    shift_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("shift_types.id"), nullable=True, index=True
    )

    # Assignment period
    start_date: Mapped[date] = mapped_column(nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Status
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_shift_assignments_emp_dates", "employee_id", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<ShiftAssignment {self.employee} - {self.shift_type} from {self.start_date}>"


# ============= ATTENDANCE =============
class Attendance(Base):
    """Attendance - daily attendance records."""

    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Attendance date and status
    attendance_date: Mapped[date] = mapped_column(nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.PRESENT, index=True
    )

    # Leave reference (if on leave)
    leave_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    leave_application: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Shift reference
    shift: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Check-in/out times
    in_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    out_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    working_hours: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Geolocation and device metadata
    check_in_latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    check_in_longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    check_out_latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    check_out_longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Late/early flags
    late_entry: Mapped[bool] = mapped_column(default=False)
    early_exit: Mapped[bool] = mapped_column(default=False)

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
        Index("ix_attendances_emp_date", "employee_id", "attendance_date", unique=True),
        Index("ix_attendances_date_status", "attendance_date", "status"),
    )

    def __repr__(self) -> str:
        return f"<Attendance {self.employee} - {self.attendance_date}: {self.status.value}>"


# ============= ATTENDANCE REQUEST =============
class AttendanceRequest(Base):
    """Attendance Request - correction/regularization requests."""

    __tablename__ = "attendance_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Request period
    from_date: Mapped[date] = mapped_column(nullable=False, index=True)
    to_date: Mapped[date] = mapped_column(nullable=False)
    half_day: Mapped[bool] = mapped_column(default=False)
    half_day_date: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Reason
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[AttendanceRequestStatus] = mapped_column(
        Enum(AttendanceRequestStatus), default=AttendanceRequestStatus.DRAFT, index=True
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

    def __repr__(self) -> str:
        return f"<AttendanceRequest {self.employee} ({self.from_date} to {self.to_date})>"
