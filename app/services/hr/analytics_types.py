"""Type definitions for HR analytics service.

These dataclasses define the contract for analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Any

__all__ = [
    # Dashboard Types
    "HRDashboardSummary",
    "ModuleSummary",
    # Organization Analytics
    "HeadcountByDepartment",
    "DepartmentHeadcountTrend",
    "DesignationDistribution",
    "TeamMetrics",
    # Trend Types
    "TrendPoint",
    # Workforce Analytics
    "WorkforceAnalytics",
    "TurnoverAnalytics",
]


# ==============================================================================
# Dashboard Types
# ==============================================================================


@dataclass
class ModuleSummary:
    """Summary for a single HR module."""

    total: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    period_count: int = 0


@dataclass
class HRDashboardSummary:
    """Complete HR dashboard summary."""

    total_employees: int
    active_employees: int
    on_leave_today: int
    pending_leave_requests: int
    leave_summary: ModuleSummary
    attendance_summary: ModuleSummary
    recruitment_summary: ModuleSummary
    payroll_summary: ModuleSummary
    training_summary: ModuleSummary
    appraisal_summary: ModuleSummary


# ==============================================================================
# Trend Types
# ==============================================================================


@dataclass
class TrendPoint:
    """Generic trend data point."""

    period: str  # YYYY-MM or YYYY-MM-DD
    value: float
    label: Optional[str] = None


# ==============================================================================
# Organization Analytics
# ==============================================================================


@dataclass
class HeadcountByDepartment:
    """Headcount breakdown by department."""

    department_id: int
    department_name: str
    total_employees: int
    active_employees: int
    on_leave: int
    terminated: int
    percentage_of_total: float


@dataclass
class DepartmentHeadcountTrend:
    """Headcount trend for a department over time."""

    department_id: int
    department_name: str
    data_points: List[TrendPoint] = field(default_factory=list)


@dataclass
class DesignationDistribution:
    """Employee distribution by designation."""

    designation_id: int
    designation_name: str
    employee_count: int
    percentage: float


@dataclass
class TeamMetrics:
    """Metrics for HD teams."""

    team_id: int
    team_name: str
    member_count: int
    avg_workload: Optional[float] = None


# ==============================================================================
# Workforce Analytics
# ==============================================================================


@dataclass
class WorkforceAnalytics:
    """Comprehensive workforce analytics."""

    total_headcount: int
    active_employees: int
    on_leave: int
    terminated: int
    headcount_by_department: List[HeadcountByDepartment]
    headcount_by_designation: List[DesignationDistribution]
    headcount_trend: List[TrendPoint]
    avg_tenure_months: float
    new_hires_30d: int
    separations_30d: int


@dataclass
class TurnoverAnalytics:
    """Employee turnover analytics."""

    period_start: date
    period_end: date
    total_separations: int
    voluntary_separations: int
    involuntary_separations: int
    turnover_rate: float
    avg_tenure_at_exit_months: float
    by_department: List[Dict[str, Any]] = field(default_factory=list)
