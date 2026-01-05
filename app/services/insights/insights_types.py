"""Type definitions for insights service.

These dataclasses define the contract for insights operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompletenessRecommendation:
    """A single recommendation for improving data completeness."""
    priority: str  # high, medium, low
    category: str  # contact, network, integration
    issue: str
    action: str
    impact: str


@dataclass
class FieldCompleteness:
    """Completeness metrics for a single field."""
    count: int
    percent: float
    missing: int


@dataclass
class SystemLinkage:
    """Linkage counts for an external system."""
    count: int
    percent: float


@dataclass
class DataCompletenessResult:
    """Result of data completeness analysis."""
    summary: Dict[str, Any]
    customer_fields: Dict[str, FieldCompleteness]
    system_linkage: Dict[str, SystemLinkage]
    subscriptions: Dict[str, Any]
    invoices: Dict[str, Any]
    payments: Dict[str, Any]
    support: Dict[str, Any]
    recommendations: List[CompletenessRecommendation]


@dataclass
class SegmentData:
    """Data for a single segment."""
    segment: str
    count: int
    mrr: float = 0.0


@dataclass
class CustomerSegmentsResult:
    """Result of customer segmentation analysis."""
    by_status: List[Dict[str, Any]]
    by_type: List[Dict[str, Any]]
    by_billing_type: List[Dict[str, Any]]
    by_tenure: List[Dict[str, Any]]
    by_mrr_tier: List[Dict[str, Any]]
    by_city: List[Dict[str, Any]]
    by_pop: List[Dict[str, Any]]


@dataclass
class PaymentTiming:
    """Payment timing breakdown."""
    early: int
    on_time: int
    late: int
    total_paid_invoices: int


@dataclass
class PaymentTimingDistribution:
    """Payment timing as percentages."""
    early_percent: float
    on_time_percent: float
    late_percent: float


@dataclass
class PaymentBehavior:
    """Customer payment behavior metrics."""
    customers_with_overdue: int
    overdue_percent: float
    payment_timing: PaymentTiming
    payment_timing_distribution: PaymentTimingDistribution


@dataclass
class SupportIntensity:
    """Support interaction intensity metrics."""
    customers_with_tickets_30d: int
    high_support_customers: int
    customers_with_conversations_30d: int


@dataclass
class ChurnIndicators:
    """Indicators of customer churn."""
    recently_cancelled_30d: int
    currently_suspended: int
    inactive_60d: int


@dataclass
class RiskSegments:
    """Customer risk segment counts."""
    at_risk: int
    high_maintenance: int
    churned_30d: int


@dataclass
class CustomerHealthResult:
    """Result of customer health analysis."""
    summary: Dict[str, Any]
    payment_behavior: PaymentBehavior
    support_intensity: SupportIntensity
    churn_indicators: ChurnIndicators
    risk_segments: RiskSegments


@dataclass
class ChurnRiskResult:
    """Result of churn risk analysis."""
    summary: Dict[str, Any]


@dataclass
class PlanTransition:
    """A single plan change transition."""
    party_id: int
    from_plan: Optional[str]
    to_plan: Optional[str]
    price_change: float
    change_type: str  # upgrade, downgrade, lateral
    date: str


@dataclass
class PlanChangesResult:
    """Result of plan changes analysis."""
    period_months: int
    summary: Dict[str, Any]
    revenue_impact: Dict[str, Any]
    rates: Dict[str, Any]
    common_transitions: List[Dict[str, Any]]
    recent_changes: List[Dict[str, Any]]


@dataclass
class RelationshipMapResult:
    """Result of relationship mapping analysis."""
    entity_counts: Dict[str, int]
    relationships: Dict[str, Dict[str, int]]
    relationship_health_scores: Dict[str, float]
    average_overall_score: float


@dataclass
class AgingBucket:
    """Invoice aging bucket data."""
    count: int
    amount: float


@dataclass
class FinancialInsightsResult:
    """Result of financial insights analysis."""
    mrr: Dict[str, Any]
    invoice_aging: Dict[str, AgingBucket]
    total_outstanding: float
    payment_methods: List[Dict[str, Any]]
    credit_notes_issued: float
    revenue_trend: List[Dict[str, Any]]


@dataclass
class TicketMetrics:
    """Ticket metrics for a period."""
    total: int
    resolved: int
    resolution_rate: float
    avg_resolution_hours: float
    by_priority: Dict[str, int]


@dataclass
class ConversationMetrics:
    """Conversation metrics for a period."""
    total: int
    resolved: int
    resolution_rate: float
    avg_first_response_hours: float
    by_channel: Dict[str, int]


@dataclass
class OperationalInsightsResult:
    """Result of operational insights analysis."""
    period_days: int
    tickets: TicketMetrics
    conversations: ConversationMetrics
    employee_productivity: List[Dict[str, Any]]
    pop_utilization: List[Dict[str, Any]]


@dataclass
class NetworkHealthResult:
    """Result of network health analysis."""
    summary: Dict[str, Any]
    by_pop: List[Dict[str, Any]]


@dataclass
class Anomaly:
    """A detected data anomaly."""
    type: str  # billing, support, data_quality
    severity: str  # high, medium, low
    description: str
    action: Optional[str] = None
    customers: Optional[List[Dict[str, Any]]] = None


@dataclass
class Pattern:
    """A detected data pattern."""
    type: str  # payment_pattern, pricing
    description: str
    insight: str


@dataclass
class AnomalySummary:
    """Summary of detected anomalies."""
    total_anomalies: int
    high_severity: int
    medium_severity: int
    low_severity: int


@dataclass
class AnomaliesResult:
    """Result of anomaly detection."""
    anomalies: List[Anomaly]
    patterns: List[Pattern]
    summary: AnomalySummary


@dataclass
class MissingData:
    """Information about missing data."""
    entity: str
    field: str
    count: int
    impact: str  # critical, high, medium, low
    description: str


@dataclass
class DataAvailabilityResult:
    """Result of data availability analysis."""
    last_sync: Optional[str]
    data_by_source: Dict[str, Dict[str, int]]
    missing_critical_data: List[MissingData]
    totals: Dict[str, int]
