"""Type definitions for CRM analytics service.

These dataclasses define the contract for CRM analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


__all__ = [
    "AnalyticsFilters",
    "LeadFunnel",
    "SourceBreakdown",
    "ConversionMetrics",
    "PipelineForecast",
    "VelocityMetrics",
    "AgingAnalysis",
    "ActivityMetrics",
    "RepPerformance",
    "TerritoryPerformance",
    "TrendPoint",
]


@dataclass
class AnalyticsFilters:
    """Filters for CRM analytics queries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    owner_id: Optional[int] = None
    owner_ids: List[int] = field(default_factory=list)
    source: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    campaign_id: Optional[int] = None
    stage_id: Optional[int] = None
    territory: Optional[str] = None


@dataclass
class LeadFunnel:
    """Lead funnel breakdown by qualification status."""

    total_leads: int
    by_qualification: Dict[str, int]  # qualification → count
    by_status: Dict[str, int]  # status → count
    by_source: Dict[str, int]  # source → count
    conversion_to_opportunity: float  # percentage
    avg_time_to_convert_days: Optional[float]


@dataclass
class SourceBreakdown:
    """Lead source performance breakdown."""

    source: str
    lead_count: int
    opportunity_count: int
    won_count: int
    conversion_rate: float  # leads → opportunities
    win_rate: float  # opportunities → won
    total_value: Decimal
    avg_deal_size: Decimal


@dataclass
class ConversionMetrics:
    """Lead-to-opportunity conversion metrics."""

    total_leads: int
    converted_leads: int
    conversion_rate: float
    avg_conversion_time_days: Optional[float]
    by_period: List[Dict[str, Any]]  # [{period, leads, converted, rate}]
    by_source: Dict[str, float]  # source → conversion_rate


@dataclass
class PipelineForecast:
    """Sales pipeline forecast."""

    total_pipeline_value: Decimal
    weighted_pipeline_value: Decimal  # Based on stage probability
    expected_revenue: Decimal  # Closing this period
    by_stage: List[Dict[str, Any]]  # [{stage_id, name, value, count, probability}]
    by_month: List[Dict[str, Any]]  # [{month, value, weighted_value}]
    at_risk_value: Decimal  # Overdue or stalled deals


@dataclass
class VelocityMetrics:
    """Pipeline velocity and deal speed metrics."""

    avg_deal_cycle_days: float  # Average time from creation to close
    median_deal_cycle_days: float
    avg_stage_time_days: Dict[str, float]  # stage_name → avg_days
    deals_stuck: int  # Deals with no activity in X days
    velocity_trend: List[Dict[str, Any]]  # [{period, avg_cycle_days}]


@dataclass
class AgingAnalysis:
    """Aging analysis for opportunities or quotes."""

    entity_type: str  # "opportunity", "quotation"
    total_count: int
    total_value: Decimal
    buckets: List[Dict[str, Any]]  # [{label, min_days, max_days, count, value}]
    overdue_count: int
    overdue_value: Decimal


@dataclass
class ActivityMetrics:
    """Activity analytics for CRM."""

    total_activities: int
    completed_activities: int
    completion_rate: float
    by_type: Dict[str, int]  # type → count
    by_owner: List[Dict[str, Any]]  # [{owner_id, name, count, completed}]
    avg_activities_per_deal: float
    activities_trend: List[Dict[str, Any]]  # [{period, count}]


@dataclass
class RepPerformance:
    """Sales representative performance metrics."""

    rep_id: int
    rep_name: str
    leads_assigned: int
    leads_converted: int
    conversion_rate: float
    opportunities_count: int
    opportunities_value: Decimal
    won_count: int
    won_value: Decimal
    win_rate: float
    avg_deal_size: Decimal
    avg_cycle_days: float
    activities_count: int
    rank: Optional[int] = None


@dataclass
class TerritoryPerformance:
    """Territory-level performance metrics."""

    territory: str
    lead_count: int
    opportunity_count: int
    opportunity_value: Decimal
    won_count: int
    won_value: Decimal
    win_rate: float
    avg_deal_size: Decimal
    rep_count: int


@dataclass
class TrendPoint:
    """Single point in a trend series."""

    period: str  # e.g., "2024-01", "2024-W05", "2024-01-15"
    period_type: str  # "daily", "weekly", "monthly"
    value: Decimal
    count: int
    comparison_value: Optional[Decimal] = None  # Previous period
    change_percent: Optional[float] = None
