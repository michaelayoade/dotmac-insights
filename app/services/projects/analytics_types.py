"""Type definitions for project analytics service.

These dataclasses define the contract for analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

__all__ = [
    "DashboardStats",
    "StatusDistribution",
    "StatusTrendPoint",
    "TaskDistribution",
    "BudgetPerformance",
    "TimelinePerformance",
    "ProfitabilityMetrics",
    "ProjectPerformance",
    "DepartmentSummary",
]


@dataclass
class DashboardStats:
    """Dashboard summary statistics."""

    total_active: int
    total_completed: int
    overdue_projects: int
    open_tasks: int
    overdue_tasks: int


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
class TaskDistribution:
    """Task distribution across different dimensions."""

    by_status: List[Dict] = field(default_factory=list)
    by_priority: List[Dict] = field(default_factory=list)
    by_assignee: List[Dict] = field(default_factory=list)


@dataclass
class BudgetPerformance:
    """Budget performance metrics."""

    total_analyzed: int
    under_budget: int
    over_budget: int
    adherence_rate: float


@dataclass
class TimelinePerformance:
    """Timeline performance metrics."""

    total_analyzed: int
    on_time: int
    delayed: int
    on_time_rate: float


@dataclass
class ProfitabilityMetrics:
    """Profitability metrics for projects."""

    avg_margin_percent: float
    top_projects: List[Dict] = field(default_factory=list)


@dataclass
class ProjectPerformance:
    """Overall project performance metrics."""

    budget: BudgetPerformance
    timeline: TimelinePerformance
    profitability: ProfitabilityMetrics


@dataclass
class DepartmentSummary:
    """Summary of projects by department."""

    department: str
    project_count: int
    task_count: int
    total_estimated: Decimal
    total_billed: Decimal
    avg_completion: Decimal
