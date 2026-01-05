"""Type definitions for leave service.

These dataclasses define the contract for leave operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.models.hr_leave import LeaveApplicationStatus, LeaveAllocationStatus

__all__ = [
    # Leave Type
    "LeaveTypeCreateData",
    "LeaveTypeUpdateData",
    # Leave Policy
    "LeavePolicyCreateData",
    "LeavePolicyUpdateData",
    "LeavePolicyDetailData",
    # Leave Allocation
    "AllocationFilters",
    "AllocationCreateData",
    "AllocationUpdateData",
    "BulkAllocationData",
    "BulkAllocationResult",
    # Leave Application
    "ApplicationFilters",
    "ApplicationCreateData",
    "ApplicationUpdateData",
    "BulkApprovalResult",
    # Balance & Validation
    "LeaveBalanceInfo",
    "ValidationResult",
    "OverlapInfo",
    # Holiday List
    "HolidayListCreateData",
    "HolidayListUpdateData",
    "HolidayData",
]


# ==============================================================================
# Leave Type
# ==============================================================================


@dataclass
class LeaveTypeCreateData:
    """Data for creating a leave type."""

    leave_type_name: str
    max_leaves_allowed: int = 0
    max_continuous_days_allowed: Optional[int] = None
    is_carry_forward: bool = False
    is_lwp: bool = False
    is_optional_leave: bool = False
    is_compensatory: bool = False
    allow_encashment: bool = False
    include_holiday: bool = False
    is_earned_leave: bool = False
    earned_leave_frequency: Optional[str] = None
    rounding: Decimal = Decimal("0.5")


@dataclass
class LeaveTypeUpdateData:
    """Data for updating a leave type (all fields optional)."""

    leave_type_name: Optional[str] = None
    max_leaves_allowed: Optional[int] = None
    max_continuous_days_allowed: Optional[int] = None
    is_carry_forward: Optional[bool] = None
    is_lwp: Optional[bool] = None
    is_optional_leave: Optional[bool] = None
    is_compensatory: Optional[bool] = None
    allow_encashment: Optional[bool] = None
    include_holiday: Optional[bool] = None
    is_earned_leave: Optional[bool] = None
    earned_leave_frequency: Optional[str] = None
    rounding: Optional[Decimal] = None


# ==============================================================================
# Leave Policy
# ==============================================================================


@dataclass
class LeavePolicyDetailData:
    """Detail line in a leave policy."""

    leave_type: str
    leave_type_id: Optional[int] = None
    annual_allocation: Decimal = Decimal("0")


@dataclass
class LeavePolicyCreateData:
    """Data for creating a leave policy."""

    leave_policy_name: str
    details: List[LeavePolicyDetailData] = field(default_factory=list)


@dataclass
class LeavePolicyUpdateData:
    """Data for updating a leave policy (all fields optional)."""

    leave_policy_name: Optional[str] = None
    details: Optional[List[LeavePolicyDetailData]] = None


# ==============================================================================
# Leave Allocation
# ==============================================================================


@dataclass
class AllocationFilters:
    """Filters for listing leave allocations."""

    employee_id: Optional[int] = None
    leave_type_id: Optional[int] = None
    status: Optional[LeaveAllocationStatus] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None


@dataclass
class AllocationCreateData:
    """Data for creating a leave allocation."""

    employee_id: int
    employee: str
    leave_type_id: int
    leave_type: str
    from_date: date
    to_date: date
    new_leaves_allocated: Decimal = Decimal("0")
    carry_forwarded_leaves: Decimal = Decimal("0")
    employee_name: Optional[str] = None
    leave_policy: Optional[str] = None
    company: Optional[str] = None


@dataclass
class AllocationUpdateData:
    """Data for updating a leave allocation (all fields optional)."""

    new_leaves_allocated: Optional[Decimal] = None
    carry_forwarded_leaves: Optional[Decimal] = None
    unused_leaves: Optional[Decimal] = None
    status: Optional[LeaveAllocationStatus] = None


@dataclass
class BulkAllocationData:
    """Data for bulk leave allocation."""

    employee_ids: List[int]
    leave_type_id: int
    leave_type: str
    from_date: date
    to_date: date
    new_leaves_allocated: Decimal
    company: Optional[str] = None


@dataclass
class BulkAllocationResult:
    """Result of bulk allocation."""

    created_count: int = 0
    skipped_count: int = 0
    skipped_employees: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ==============================================================================
# Leave Application
# ==============================================================================


@dataclass
class ApplicationFilters:
    """Filters for listing leave applications."""

    employee_id: Optional[int] = None
    leave_type_id: Optional[int] = None
    status: Optional[LeaveApplicationStatus] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    search: Optional[str] = None


@dataclass
class ApplicationCreateData:
    """Data for creating a leave application."""

    employee_id: int
    employee: str
    leave_type_id: int
    leave_type: str
    from_date: date
    to_date: date
    posting_date: Optional[date] = None
    half_day: bool = False
    half_day_date: Optional[date] = None
    total_leave_days: Optional[Decimal] = None
    description: Optional[str] = None
    employee_name: Optional[str] = None
    leave_approver: Optional[str] = None
    leave_approver_name: Optional[str] = None
    company: Optional[str] = None


@dataclass
class ApplicationUpdateData:
    """Data for updating a leave application (all fields optional)."""

    from_date: Optional[date] = None
    to_date: Optional[date] = None
    half_day: Optional[bool] = None
    half_day_date: Optional[date] = None
    total_leave_days: Optional[Decimal] = None
    description: Optional[str] = None
    leave_approver: Optional[str] = None
    leave_approver_name: Optional[str] = None


@dataclass
class BulkApprovalResult:
    """Result of bulk approval/rejection."""

    approved_count: int = 0
    rejected_count: int = 0
    skipped: List[dict] = field(default_factory=list)


# ==============================================================================
# Balance & Validation
# ==============================================================================


@dataclass
class LeaveBalanceInfo:
    """Employee leave balance information."""

    employee_id: int
    leave_type_id: int
    leave_type_name: str
    total_allocated: Decimal
    used: Decimal
    available: Decimal
    carry_forwarded: Decimal
    pending_approval: Decimal


@dataclass
class ValidationResult:
    """Result of leave application validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class OverlapInfo:
    """Information about overlapping leave application."""

    id: int
    from_date: date
    to_date: date
    leave_type: str
    status: str


# ==============================================================================
# Holiday List
# ==============================================================================


@dataclass
class HolidayListCreateData:
    """Data for creating a holiday list."""

    holiday_list_name: str
    from_date: date
    to_date: date
    company: Optional[str] = None
    weekly_off: Optional[str] = None


@dataclass
class HolidayListUpdateData:
    """Data for updating a holiday list (all fields optional)."""

    holiday_list_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    weekly_off: Optional[str] = None


@dataclass
class HolidayData:
    """Data for a single holiday entry."""

    holiday_date: date
    description: str
    weekly_off: bool = False
