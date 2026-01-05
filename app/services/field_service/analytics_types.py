"""Type definitions for field service analytics.

These dataclasses define the contract for analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

__all__ = [
    "AnalyticsFilters",
    "DashboardMetrics",
    "OrderTypeBreakdown",
    "PerformanceMetrics",
    "TechnicianPerformance",
    "TeamPerformance",
    "MonthlyTrend",
    "CostAnalysis",
    "UtilizationMetrics",
]


@dataclass
class AnalyticsFilters:
    """Filters for analytics queries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    team_id: Optional[int] = None
    zone_id: Optional[int] = None
    company: Optional[str] = None


@dataclass
class DashboardMetrics:
    """Dashboard summary metrics."""

    total_orders: int = 0
    completed_orders: int = 0
    pending_orders: int = 0
    cancelled_orders: int = 0
    completion_rate: float = 0.0
    avg_completion_time_hours: float = 0.0
    avg_customer_rating: float = 0.0
    total_revenue: Decimal = field(default_factory=lambda: Decimal("0"))
    total_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    profit_margin: float = 0.0


@dataclass
class OrderTypeBreakdown:
    """Order breakdown by type."""

    order_type: str
    count: int
    percentage: float
    revenue: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class PerformanceMetrics:
    """Performance metrics."""

    first_time_fix_rate: float = 0.0
    avg_response_time_hours: float = 0.0
    avg_travel_time_hours: float = 0.0
    avg_work_time_hours: float = 0.0
    on_time_completion_rate: float = 0.0
    sla_compliance_rate: float = 0.0


@dataclass
class TechnicianPerformance:
    """Performance metrics for a technician."""

    technician_id: int
    technician_name: str
    total_orders: int = 0
    completed_orders: int = 0
    completion_rate: float = 0.0
    avg_rating: float = 0.0
    avg_completion_time_hours: float = 0.0
    total_revenue: Decimal = field(default_factory=lambda: Decimal("0"))
    first_time_fix_rate: float = 0.0


@dataclass
class TeamPerformance:
    """Performance metrics for a team."""

    team_id: int
    team_name: str
    member_count: int = 0
    total_orders: int = 0
    completed_orders: int = 0
    completion_rate: float = 0.0
    avg_rating: float = 0.0
    total_revenue: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class MonthlyTrend:
    """Monthly trend data point."""

    period: str  # "YYYY-MM"
    year: int
    month: int
    total_orders: int = 0
    completed_orders: int = 0
    revenue: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class CostAnalysis:
    """Cost analysis metrics."""

    total_labor_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    total_parts_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    total_travel_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    total_overhead: Decimal = field(default_factory=lambda: Decimal("0"))
    avg_cost_per_order: Decimal = field(default_factory=lambda: Decimal("0"))
    avg_revenue_per_order: Decimal = field(default_factory=lambda: Decimal("0"))
    profit_per_order: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class UtilizationMetrics:
    """Utilization metrics for technicians."""

    total_available_hours: float = 0.0
    total_scheduled_hours: float = 0.0
    total_worked_hours: float = 0.0
    utilization_rate: float = 0.0
    idle_time_hours: float = 0.0
    overtime_hours: float = 0.0
    by_technician: List[Dict[str, Any]] = field(default_factory=list)
