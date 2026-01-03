"""Upselling Service Types - Business Intelligence type definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class TriggerType(str, Enum):
    """Upselling trigger types."""
    HIGH_USAGE = "high_usage"
    BUNDLE_EXHAUSTION = "bundle_exhaustion"
    SPEED_UPGRADE = "speed_upgrade"
    PLAN_MISMATCH = "plan_mismatch"
    LOYALTY_UPGRADE = "loyalty_upgrade"
    CONTRACT_RENEWAL = "contract_renewal"
    FEATURE_REQUEST = "feature_request"


@dataclass
class UsageMetrics:
    """Usage metrics for a subscription."""
    subscription_id: int
    avg_usage_percent: float  # Average data usage as % of cap
    peak_usage_percent: float
    usage_trend: str  # increasing, stable, decreasing
    months_high_usage: int  # Consecutive months with high usage
    bundle_exhaustion_count: int  # Times exhausted in period
    avg_session_duration_hours: float
    total_data_gb: float
    peak_throughput_mbps: float
    plan_speed_mbps: int


@dataclass
class TriggerEvidence:
    """Evidence supporting an upsell trigger."""
    trigger_type: TriggerType
    confidence_score: int  # 0-100
    metrics: Dict[str, Any]
    explanation: str
    detected_at: datetime


@dataclass
class UpgradeRecommendation:
    """Recommended upgrade for a subscription."""
    tariff_id: int
    tariff_name: str
    current_price: Decimal
    new_price: Decimal
    price_increase: Decimal
    speed_increase_mbps: int
    data_increase_gb: Optional[int]
    features_added: List[str]
    match_score: int  # How well this matches customer needs


@dataclass
class AnalysisResult:
    """Result of analyzing a single subscription."""
    subscription_id: int
    party_id: int
    current_plan: str
    current_mrr: Decimal
    triggers_found: List[TriggerEvidence]
    recommendations: List[UpgradeRecommendation]
    best_recommendation: Optional[UpgradeRecommendation]
    potential_mrr_increase: Decimal
    priority: str  # low, medium, high, urgent


@dataclass
class BatchAnalysisInput:
    """Input for batch upselling analysis."""
    subscription_ids: Optional[List[int]] = None  # None = all active
    trigger_types: Optional[List[TriggerType]] = None
    min_months_active: int = 3
    exclude_recently_analyzed: bool = True
    recently_analyzed_days: int = 7


@dataclass
class BatchAnalysisResult:
    """Result of batch upselling analysis."""
    run_id: int
    subscriptions_analyzed: int
    opportunities_found: int
    opportunities_by_trigger: Dict[str, int]
    total_potential_mrr: Decimal
    duration_seconds: float


@dataclass
class ConversionStats:
    """Conversion statistics for analytics."""
    period: str
    total_opportunities: int
    converted_count: int
    declined_count: int
    expired_count: int
    conversion_rate: float
    total_mrr_gained: Decimal
    avg_mrr_per_conversion: Decimal
    avg_days_to_convert: float
    top_trigger_types: List[tuple[str, int, float]]  # (type, count, rate)


@dataclass
class SalesLeaderboardEntry:
    """Entry in sales leaderboard."""
    employee_id: int
    employee_name: str
    opportunities_assigned: int
    opportunities_converted: int
    conversion_rate: float
    mrr_generated: Decimal
    avg_days_to_convert: float


@dataclass
class OpportunityListFilters:
    """Filters for listing opportunities."""
    status: Optional[str] = None
    trigger_type: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_id: Optional[int] = None
    min_revenue_increase: Optional[Decimal] = None
    min_score: Optional[int] = None
    created_after: Optional[datetime] = None
    expires_before: Optional[datetime] = None


@dataclass
class UpsellingSettings:
    """Configurable upselling thresholds and settings."""
    # High Usage Trigger
    high_usage_threshold_percent: int = 80
    high_usage_months_required: int = 3

    # Bundle Exhaustion Trigger
    bundle_exhaustion_count: int = 2
    bundle_exhaustion_months: int = 3

    # Speed Upgrade Trigger
    speed_limit_session_percent: int = 50

    # Loyalty Trigger
    loyalty_months_threshold: int = 12

    # Contract Renewal Trigger
    contract_renewal_days_before: int = 60

    # Opportunity Settings
    opportunity_expiry_days: int = 30
    auto_create_crm_opportunity: bool = True
    notify_sales_on_high_score: bool = True
    high_score_threshold: int = 80

    # Batch Analysis
    analysis_batch_size: int = 100


@dataclass
class RevenueForecast:
    """Revenue forecast from opportunities."""
    total_opportunities: int
    active_opportunities: int
    potential_monthly_revenue: Decimal
    potential_annual_revenue: Decimal
    expected_conversion_rate: float
    expected_monthly_revenue: Decimal
    expected_annual_revenue: Decimal
    by_trigger_type: Dict[str, Decimal]
    by_priority: Dict[str, Decimal]
