"""Type definitions for project analytics service.

These dataclasses define the contract for analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from typing import Any

__all__ = [
    "AnalyticsFilters",
    "DashboardStats",
    "DashboardData",
    "StatusDistribution",
    "StatusTrendPoint",
    "AssigneeTaskStats",
    "TaskDistribution",
    "BudgetPerformance",
    "TimelinePerformance",
    "TopProject",
    "ProfitabilityMetrics",
    "PerformanceMetrics",
    "DepartmentSummary",
]


@dataclass
class AnalyticsFilters:
    """Filters for analytics queries."""

    company: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class DashboardStats:
    """Dashboard summary statistics."""

    # Projects
    total_projects: int = 0
    active_projects: int = 0
    completed_projects: int = 0
    on_hold_projects: int = 0
    cancelled_projects: int = 0
    by_priority: Dict[str, int] = field(default_factory=dict)

    # Tasks
    total_tasks: int = 0
    open_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0

    # Financials
    total_estimated: float = 0.0
    total_actual_cost: float = 0.0
    total_billed: float = 0.0
    variance: float = 0.0

    # Metrics
    avg_completion_percent: float = 0.0
    due_this_week: int = 0
    overdue_projects: int = 0
    total_open_tasks: int = 0


@dataclass
class DashboardData:
    """Complete dashboard data for the projects dashboard page."""

    stats: DashboardStats
    status_distribution: List["StatusDistribution"] = field(default_factory=list)
    recent_projects: List[Any] = field(default_factory=list)  # List of Project models
    upcoming_milestones: List[Any] = field(default_factory=list)  # List of Milestone models
    overdue_tasks: List[Any] = field(default_factory=list)  # List of Task models


@dataclass
class StatusDistribution:
    """Status distribution data point."""

    status: str
    count: int


@dataclass
class StatusTrendPoint:
    """Monthly status trend data point."""

    period: str  # "YYYY-MM"
    year: int
    month: int
    created: int
    completed: int


@dataclass
class AssigneeTaskStats:
    """Task statistics for an assignee."""

    assignee: Optional[str]
    total: int
    completed: int
    completion_rate: float


@dataclass
class TaskDistribution:
    """Task distribution across different dimensions."""

    by_status: List[StatusDistribution] = field(default_factory=list)
    by_priority: List[StatusDistribution] = field(default_factory=list)
    by_assignee: List[AssigneeTaskStats] = field(default_factory=list)


@dataclass
class BudgetPerformance:
    """Budget performance metrics."""

    total_analyzed: int = 0
    under_budget: int = 0
    over_budget: int = 0
    adherence_rate: float = 0.0


@dataclass
class TimelinePerformance:
    """Timeline performance metrics."""

    total_analyzed: int = 0
    on_time: int = 0
    delayed: int = 0
    on_time_rate: float = 0.0


@dataclass
class TopProject:
    """Top performing project data."""

    id: int
    project_name: str
    gross_margin: float
    margin_percent: float


@dataclass
class ProfitabilityMetrics:
    """Profitability metrics for projects."""

    avg_margin_percent: float = 0.0
    top_projects: List[TopProject] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    """Overall project performance metrics."""

    budget: BudgetPerformance = field(default_factory=BudgetPerformance)
    timeline: TimelinePerformance = field(default_factory=TimelinePerformance)
    profitability: ProfitabilityMetrics = field(default_factory=ProfitabilityMetrics)


@dataclass
class DepartmentSummary:
    """Summary of projects by department."""

    department: str
    project_count: int
    task_count: int
    total_estimated: float
    total_billed: float
    avg_completion: float
