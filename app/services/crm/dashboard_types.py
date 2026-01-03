"""Type definitions for CRM dashboard service.

These dataclasses define the contract for CRM dashboard operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


__all__ = [
    "DashboardFilters",
    "DashboardSummary",
    "KPICard",
    "PipelineChart",
    "FunnelChart",
    "StageDistribution",
    "RevenueTrend",
    "ConversionTrend",
    "SalesForecast",
    "TeamActivitySummary",
    "UpcomingTask",
    "OverdueItems",
    "SalesRepRanking",
]


@dataclass
class DashboardFilters:
    """Filters for CRM dashboard queries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None
    territory: Optional[str] = None
    period: str = "month"  # day, week, month, quarter, year


@dataclass
class KPICard:
    """Single KPI card for dashboard."""

    key: str  # unique identifier
    title: str
    value: Any  # Can be int, Decimal, float, str
    formatted_value: str  # Pre-formatted display value
    trend: Optional[float]  # Percentage change
    trend_direction: Optional[str]  # "up", "down", "stable"
    comparison_period: Optional[str]  # e.g., "vs last month"
    icon: Optional[str] = None
    color: Optional[str] = None


@dataclass
class DashboardSummary:
    """Complete CRM dashboard summary."""

    # Lead metrics
    total_leads: int
    new_leads_this_period: int
    qualified_leads: int
    lead_conversion_rate: float

    # Opportunity metrics
    total_opportunities: int
    open_opportunities: int
    pipeline_value: Decimal
    weighted_pipeline_value: Decimal

    # Activity metrics
    activities_due_today: int
    overdue_activities: int
    activities_completed_this_period: int

    # Performance
    won_deals_this_period: int
    won_value_this_period: Decimal
    avg_deal_size: Decimal
    win_rate: float

    # KPI cards
    kpi_cards: List[KPICard]


@dataclass
class PipelineChart:
    """Pipeline visualization data."""

    stages: List[Dict[str, Any]]  # [{id, name, count, value, color, order}]
    total_count: int
    total_value: Decimal
    avg_per_stage: Decimal


@dataclass
class FunnelChart:
    """Lead/opportunity funnel data."""

    levels: List[Dict[str, Any]]  # [{name, count, value, conversion_rate}]
    overall_conversion: float
    drop_off_stages: List[str]  # Stages with highest drop-off


@dataclass
class StageDistribution:
    """Opportunity distribution by stage."""

    stage_id: int
    stage_name: str
    opportunity_count: int
    total_value: Decimal
    avg_value: Decimal
    avg_days_in_stage: float
    percentage_of_pipeline: float


@dataclass
class RevenueTrend:
    """Revenue trend over time."""

    period_type: str  # daily, weekly, monthly
    data_points: List[Dict[str, Any]]  # [{period, value, count, avg}]
    total_revenue: Decimal
    avg_revenue: Decimal
    trend_direction: str  # up, down, stable
    trend_percentage: float


@dataclass
class ConversionTrend:
    """Conversion rate trend over time."""

    period_type: str  # daily, weekly, monthly
    data_points: List[Dict[str, Any]]  # [{period, rate, converted, total}]
    avg_conversion_rate: float
    best_period: Optional[str]
    worst_period: Optional[str]


@dataclass
class SalesForecast:
    """Sales forecast data."""

    forecast_period: str  # e.g., "2024-Q2"
    predicted_revenue: Decimal
    confidence_level: float  # percentage
    best_case: Decimal
    worst_case: Decimal
    by_month: List[Dict[str, Any]]  # [{month, predicted, committed, stretch}]
    by_stage: List[Dict[str, Any]]  # [{stage, predicted, probability}]


@dataclass
class TeamActivitySummary:
    """Team activity summary for dashboard."""

    total_activities: int
    completed_today: int
    pending_today: int
    overdue: int
    by_type: Dict[str, int]  # type → count
    by_rep: List[Dict[str, Any]]  # [{rep_id, name, completed, pending}]
    completion_rate: float


@dataclass
class UpcomingTask:
    """Upcoming task/activity for dashboard."""

    id: int
    type: str  # call, meeting, task, etc.
    subject: str
    due_date: datetime
    due_time: Optional[str]
    party_id: Optional[int]
    party_name: Optional[str]
    opportunity_id: Optional[int]
    opportunity_name: Optional[str]
    priority: str
    is_overdue: bool


@dataclass
class OverdueItems:
    """Overdue items summary."""

    overdue_activities: int
    overdue_opportunities: int  # Past expected close date
    overdue_quotes: int
    overdue_tasks: int
    total_overdue_value: Decimal
    items: List[Dict[str, Any]]  # [{type, id, subject, due_date, value}]


@dataclass
class SalesRepRanking:
    """Sales rep ranking for leaderboard."""

    rank: int
    rep_id: int
    rep_name: str
    avatar_url: Optional[str]
    won_deals: int
    won_value: Decimal
    activities: int
    win_rate: float
    trend: Optional[str]  # up, down, stable vs last period
