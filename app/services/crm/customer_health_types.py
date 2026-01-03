"""Customer Health Service Types - CRM-Support Integration Analytics."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class HealthGrade(str, Enum):
    """Customer health grade classification."""

    EXCELLENT = "excellent"  # 80-100
    GOOD = "good"  # 60-79
    AT_RISK = "at_risk"  # 40-59
    CRITICAL = "critical"  # 0-39


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChurnRiskFactor(str, Enum):
    """Factors contributing to churn risk."""

    HIGH_TICKET_VOLUME = "high_ticket_volume"
    RECURRING_ISSUES = "recurring_issues"
    LOW_CSAT = "low_csat"
    ESCALATIONS = "escalations"
    SLA_BREACHES = "sla_breaches"
    DECREASING_ENGAGEMENT = "decreasing_engagement"
    PAYMENT_ISSUES = "payment_issues"
    LONG_RESOLUTION_TIMES = "long_resolution_times"


class OpportunitySignalType(str, Enum):
    """Types of opportunity signals from support data."""

    FEATURE_REQUEST = "feature_request"
    UPGRADE_READINESS = "upgrade_readiness"
    CROSS_SELL = "cross_sell"
    UPSELL = "upsell"
    EXPANSION = "expansion"
    ADVOCACY = "advocacy"  # High satisfaction, potential reference


@dataclass
class TicketMetrics:
    """Aggregated ticket metrics for a customer."""

    total_tickets: int = 0
    open_tickets: int = 0
    resolved_tickets: int = 0
    escalated_tickets: int = 0
    high_priority_tickets: int = 0
    critical_tickets: int = 0
    avg_resolution_hours: float = 0.0
    avg_first_response_hours: float = 0.0
    sla_breaches: int = 0
    tickets_last_30_days: int = 0
    tickets_last_90_days: int = 0
    trend_direction: str = "stable"  # increasing, decreasing, stable


@dataclass
class CSATMetrics:
    """Customer satisfaction metrics."""

    average_score: float = 0.0
    response_count: int = 0
    promoters: int = 0  # 9-10 scores
    passives: int = 0  # 7-8 scores
    detractors: int = 0  # 0-6 scores
    nps_score: Optional[float] = None
    trend_direction: str = "stable"
    last_feedback_date: Optional[datetime] = None


@dataclass
class RecurringIssue:
    """Detected recurring issue pattern."""

    issue_id: UUID
    category: str
    description: str
    occurrence_count: int
    first_occurrence: datetime
    last_occurrence: datetime
    affected_parties: list[UUID] = field(default_factory=list)
    avg_resolution_hours: float = 0.0
    is_product_issue: bool = False
    suggested_action: Optional[str] = None


@dataclass
class HealthScoreBreakdown:
    """Detailed breakdown of health score components."""

    ticket_frequency_score: float = 0.0  # 0-100, lower tickets = higher score
    resolution_time_score: float = 0.0  # 0-100, faster = higher
    csat_score: float = 0.0  # 0-100
    escalation_score: float = 0.0  # 0-100, fewer escalations = higher
    sla_compliance_score: float = 0.0  # 0-100
    engagement_score: float = 0.0  # 0-100, healthy engagement patterns

    # Component weights (should sum to 1.0)
    ticket_frequency_weight: float = 0.20
    resolution_time_weight: float = 0.15
    csat_weight: float = 0.25
    escalation_weight: float = 0.15
    sla_compliance_weight: float = 0.15
    engagement_weight: float = 0.10


@dataclass
class CustomerHealthScore:
    """Complete customer health assessment."""

    party_id: UUID
    company_id: UUID
    overall_score: float  # 0-100
    grade: HealthGrade
    breakdown: HealthScoreBreakdown
    ticket_metrics: TicketMetrics
    csat_metrics: CSATMetrics
    calculated_at: datetime
    previous_score: Optional[float] = None
    score_change: float = 0.0
    trend_direction: str = "stable"


@dataclass
class ChurnRiskAssessment:
    """Churn risk assessment for a customer."""

    party_id: UUID
    company_id: UUID
    risk_level: RiskLevel
    risk_score: float  # 0-100, higher = more at risk
    contributing_factors: list[ChurnRiskFactor] = field(default_factory=list)
    factor_details: dict = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    estimated_revenue_at_risk: Optional[Decimal] = None
    assessed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EscalationAlert:
    """Alert for escalation patterns."""

    party_id: UUID
    company_id: UUID
    alert_type: str  # repeated_escalation, vip_escalation, trending_up
    severity: RiskLevel
    ticket_ids: list[UUID] = field(default_factory=list)
    escalation_count: int = 0
    period_days: int = 30
    message: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SLABreachWarning:
    """Warning for SLA breach patterns."""

    party_id: UUID
    company_id: UUID
    breach_count: int = 0
    breach_rate: float = 0.0  # Percentage of tickets with SLA breaches
    at_risk_tickets: list[UUID] = field(default_factory=list)
    avg_breach_hours: float = 0.0
    severity: RiskLevel = RiskLevel.LOW
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OpportunitySignal:
    """Sales/expansion opportunity signal from support data."""

    party_id: UUID
    company_id: UUID
    signal_type: OpportunitySignalType
    confidence: float  # 0-1
    source_ticket_ids: list[UUID] = field(default_factory=list)
    description: str = ""
    suggested_product: Optional[str] = None
    suggested_action: str = ""
    estimated_value: Optional[Decimal] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeatureRequestAggregate:
    """Aggregated feature requests from tickets."""

    feature_keyword: str
    request_count: int = 0
    requesting_parties: list[UUID] = field(default_factory=list)
    total_revenue_of_requesters: Decimal = Decimal("0")
    source_ticket_ids: list[UUID] = field(default_factory=list)
    first_requested: Optional[datetime] = None
    last_requested: Optional[datetime] = None
    priority_score: float = 0.0  # Based on customer value and request volume


@dataclass
class CustomerHealthSummary:
    """Summary view of customer health for listings."""

    party_id: UUID
    party_name: str
    overall_score: float
    grade: HealthGrade
    churn_risk: RiskLevel
    open_tickets: int
    avg_csat: Optional[float]
    last_ticket_date: Optional[datetime]
    has_alerts: bool = False
    alert_count: int = 0


@dataclass
class HealthTrendPoint:
    """Single point in health trend history."""

    date: datetime
    score: float
    grade: HealthGrade
    ticket_count: int = 0
    csat_score: Optional[float] = None


@dataclass
class CustomerHealthTrend:
    """Health score trend over time."""

    party_id: UUID
    company_id: UUID
    period_days: int = 90
    data_points: list[HealthTrendPoint] = field(default_factory=list)
    overall_trend: str = "stable"  # improving, declining, stable
    trend_velocity: float = 0.0  # Rate of change


@dataclass
class HealthDashboardStats:
    """Aggregate stats for health dashboard."""

    company_id: UUID
    total_customers: int = 0
    excellent_count: int = 0
    good_count: int = 0
    at_risk_count: int = 0
    critical_count: int = 0
    avg_health_score: float = 0.0
    churn_risk_high: int = 0
    churn_risk_critical: int = 0
    active_alerts: int = 0
    total_open_tickets: int = 0
    avg_resolution_hours: float = 0.0
    avg_csat: float = 0.0
    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PatternDetectionResult:
    """Result of pattern detection analysis."""

    company_id: UUID
    recurring_issues: list[RecurringIssue] = field(default_factory=list)
    top_issue_categories: list[tuple[str, int]] = field(default_factory=list)
    common_keywords: list[tuple[str, int]] = field(default_factory=list)
    peak_ticket_hours: list[int] = field(default_factory=list)
    peak_ticket_days: list[int] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CalculateHealthInput:
    """Input for calculating customer health score."""

    party_id: UUID
    lookback_days: int = 90
    include_trends: bool = True


@dataclass
class BulkHealthCalculationInput:
    """Input for bulk health score calculation."""

    party_ids: Optional[list[UUID]] = None  # None = all customers
    lookback_days: int = 90
    health_grade_filter: Optional[HealthGrade] = None
    min_ticket_count: int = 0


@dataclass
class ListHealthScoresInput:
    """Input for listing customer health scores."""

    grade_filter: Optional[HealthGrade] = None
    risk_level_filter: Optional[RiskLevel] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    has_alerts: Optional[bool] = None
    sort_by: str = "score"  # score, name, ticket_count, last_activity
    sort_desc: bool = True
    page: int = 1
    per_page: int = 50


@dataclass
class DetectPatternsInput:
    """Input for pattern detection."""

    lookback_days: int = 90
    min_occurrence_count: int = 3
    categories: Optional[list[str]] = None
    include_resolved: bool = True
