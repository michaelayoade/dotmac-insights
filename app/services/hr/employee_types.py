"""Type definitions for employee service.

These dataclasses define the contract for employee operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.employee import EmploymentStatus

__all__ = [
    "EmployeeFilters",
    "EmployeeCreateData",
    "EmployeeUpdateData",
    "EmployeeSummary",
    "OrgChartNode",
    "TerminationData",
    "BulkResult",
    "BulkUpdateData",
]


@dataclass
class EmployeeFilters:
    """Filters for listing employees."""

    status: Optional[EmploymentStatus] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    employment_type: Optional[str] = None
    search: Optional[str] = None  # Name, email, employee_number
    date_of_joining_from: Optional[date] = None
    date_of_joining_to: Optional[date] = None
    include_deleted: bool = False


@dataclass
class EmployeeCreateData:
    """Data for creating an employee."""

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_number: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    # Text fields for ERPNext values
    department: Optional[str] = None
    designation: Optional[str] = None
    reports_to: Optional[str] = None
    # Employment
    employment_type: Optional[str] = None
    date_of_joining: Optional[date] = None
    # Compensation
    salary: Optional[Decimal] = None
    currency: str = "NGN"
    # Status
    status: EmploymentStatus = EmploymentStatus.ACTIVE


@dataclass
class EmployeeUpdateData:
    """Data for updating an employee (all fields optional)."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_number: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    # Text fields for ERPNext values
    department: Optional[str] = None
    designation: Optional[str] = None
    reports_to: Optional[str] = None
    # Employment
    employment_type: Optional[str] = None
    date_of_joining: Optional[date] = None
    date_of_leaving: Optional[date] = None
    # Compensation
    salary: Optional[Decimal] = None
    currency: Optional[str] = None
    # Status
    status: Optional[EmploymentStatus] = None


@dataclass
class EmployeeSummary:
    """Summary view of employee for search/autocomplete."""

    id: int
    name: str
    email: Optional[str]
    employee_number: Optional[str]
    department: Optional[str]
    designation: Optional[str]
    status: EmploymentStatus


@dataclass
class OrgChartNode:
    """Node in organization chart."""

    employee_id: int
    name: str
    designation: Optional[str]
    department: Optional[str]
    email: Optional[str]
    direct_reports: List["OrgChartNode"] = field(default_factory=list)


@dataclass
class TerminationData:
    """Data for employee termination."""

    date_of_leaving: date
    reason: Optional[str] = None
    exit_interview_notes: Optional[str] = None


@dataclass
class BulkUpdateData:
    """Data for bulk updating employees."""

    ids: List[int] = field(default_factory=list)
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    status: Optional[EmploymentStatus] = None
    reports_to_id: Optional[int] = None


@dataclass
class BulkResult:
    """Result of a bulk operation."""

    updated_count: int = 0
    deleted_count: int = 0
    failed_ids: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
