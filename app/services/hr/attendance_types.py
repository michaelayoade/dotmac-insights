"""Type definitions for attendance service.

These dataclasses define the contract for attendance operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from app.models.hr_attendance import AttendanceStatus, AttendanceRequestStatus

__all__ = [
    # Shift Types
    "ShiftTypeCreateData",
    "ShiftTypeUpdateData",
    # Shift Assignments
    "ShiftAssignmentFilters",
    "ShiftAssignmentCreateData",
    "ShiftAssignmentUpdateData",
    "BulkShiftAssignmentData",
    # Attendance
    "AttendanceFilters",
    "AttendanceCreateData",
    "AttendanceUpdateData",
    "CheckInData",
    "CheckOutData",
    # Attendance Requests
    "AttendanceRequestFilters",
    "AttendanceRequestCreateData",
    # Reports
    "EmployeeAttendanceStats",
    "AttendanceSummary",
    "DepartmentAttendanceSummary",
    "WorkingHoursSummary",
    "LateArrivalRecord",
    # Bulk
    "BulkResult",
]


# ==============================================================================
# Shift Types
# ==============================================================================


@dataclass
class ShiftTypeCreateData:
    """Data for creating a shift type."""

    shift_type_name: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    working_hours_threshold_for_half_day: Decimal = Decimal("0")
    working_hours_threshold_for_absent: Decimal = Decimal("0")
    determine_check_in_and_check_out: Optional[str] = None
    begin_check_in_before_shift_start_time: int = 0
    allow_check_out_after_shift_end_time: int = 0
    enable_auto_attendance: bool = False
    enable_entry_grace_period: bool = False
    late_entry_grace_period: int = 0
    enable_exit_grace_period: bool = False
    early_exit_grace_period: int = 0
    holiday_list: Optional[str] = None


@dataclass
class ShiftTypeUpdateData:
    """Data for updating a shift type (all fields optional)."""

    shift_type_name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    working_hours_threshold_for_half_day: Optional[Decimal] = None
    working_hours_threshold_for_absent: Optional[Decimal] = None
    determine_check_in_and_check_out: Optional[str] = None
    begin_check_in_before_shift_start_time: Optional[int] = None
    allow_check_out_after_shift_end_time: Optional[int] = None
    enable_auto_attendance: Optional[bool] = None
    enable_entry_grace_period: Optional[bool] = None
    late_entry_grace_period: Optional[int] = None
    enable_exit_grace_period: Optional[bool] = None
    early_exit_grace_period: Optional[int] = None
    holiday_list: Optional[str] = None


# ==============================================================================
# Shift Assignments
# ==============================================================================


@dataclass
class ShiftAssignmentFilters:
    """Filters for listing shift assignments."""

    employee_id: Optional[int] = None
    shift_type_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company: Optional[str] = None


@dataclass
class ShiftAssignmentCreateData:
    """Data for creating a shift assignment."""

    employee_id: int
    employee: str
    shift_type_id: int
    shift_type: str
    start_date: date
    end_date: Optional[date] = None
    employee_name: Optional[str] = None
    company: Optional[str] = None


@dataclass
class ShiftAssignmentUpdateData:
    """Data for updating a shift assignment (all fields optional)."""

    shift_type_id: Optional[int] = None
    shift_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class BulkShiftAssignmentData:
    """Data for bulk shift assignment."""

    employee_ids: List[int]
    shift_type_id: int
    shift_type: str
    start_date: date
    end_date: Optional[date] = None
    company: Optional[str] = None


# ==============================================================================
# Attendance
# ==============================================================================


@dataclass
class AttendanceFilters:
    """Filters for listing attendance records."""

    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    status: Optional[AttendanceStatus] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    late_entry: Optional[bool] = None
    early_exit: Optional[bool] = None
    company: Optional[str] = None


@dataclass
class AttendanceCreateData:
    """Data for creating an attendance record."""

    employee_id: int
    employee: str
    attendance_date: date
    status: AttendanceStatus = AttendanceStatus.PRESENT
    employee_name: Optional[str] = None
    shift: Optional[str] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    working_hours: Decimal = Decimal("0")
    leave_type: Optional[str] = None
    leave_application: Optional[str] = None
    late_entry: bool = False
    early_exit: bool = False
    company: Optional[str] = None


@dataclass
class AttendanceUpdateData:
    """Data for updating an attendance record (all fields optional)."""

    status: Optional[AttendanceStatus] = None
    shift: Optional[str] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    working_hours: Optional[Decimal] = None
    late_entry: Optional[bool] = None
    early_exit: Optional[bool] = None
    leave_type: Optional[str] = None
    leave_application: Optional[str] = None


@dataclass
class CheckInData:
    """Data for employee check-in."""

    attendance_date: Optional[date] = None
    in_time: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None


@dataclass
class CheckOutData:
    """Data for employee check-out."""

    attendance_date: Optional[date] = None
    out_time: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None


# ==============================================================================
# Attendance Requests
# ==============================================================================


@dataclass
class AttendanceRequestFilters:
    """Filters for listing attendance requests."""

    employee_id: Optional[int] = None
    status: Optional[AttendanceRequestStatus] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None


@dataclass
class AttendanceRequestCreateData:
    """Data for creating an attendance request."""

    employee_id: int
    employee: str
    from_date: date
    to_date: date
    reason: Optional[str] = None
    explanation: Optional[str] = None
    employee_name: Optional[str] = None
    half_day: bool = False
    half_day_date: Optional[date] = None
    company: Optional[str] = None


# ==============================================================================
# Reports
# ==============================================================================


@dataclass
class EmployeeAttendanceStats:
    """Simple attendance statistics for a date range."""

    present_count: int = 0
    absent_count: int = 0
    half_day_count: int = 0
    on_leave_count: int = 0
    late_entry_count: int = 0
    early_exit_count: int = 0


@dataclass
class AttendanceSummary:
    """Monthly attendance summary for an employee."""

    employee_id: int
    employee_name: str
    month: int
    year: int
    total_days: int
    present_days: int
    absent_days: int
    half_days: int
    leave_days: int
    work_from_home_days: int
    late_entries: int
    early_exits: int
    total_working_hours: Decimal


@dataclass
class DepartmentAttendanceSummary:
    """Daily attendance summary for a department."""

    department_id: int
    department_name: str
    attendance_date: date
    total_employees: int
    present: int
    absent: int
    on_leave: int
    half_day: int
    work_from_home: int
    attendance_rate: Decimal


@dataclass
class WorkingHoursSummary:
    """Working hours summary for a period."""

    employee_id: int
    employee_name: str
    from_date: date
    to_date: date
    total_days: int
    total_hours: Decimal
    average_hours_per_day: Decimal
    overtime_hours: Decimal


@dataclass
class LateArrivalRecord:
    """Record of a late arrival."""

    employee_id: int
    employee_name: str
    attendance_date: date
    shift_start: Optional[time]
    actual_in_time: Optional[datetime]
    minutes_late: int
    department: Optional[str]


# ==============================================================================
# Bulk
# ==============================================================================


@dataclass
class BulkResult:
    """Result of a bulk operation."""

    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_ids: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
