"""Customer Health API endpoints - CRM-Support Integration Analytics."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, User
from app.database import get_async_session
from app.utils.company_context import get_company_id

from app.services.crm.customer_health import CustomerHealthService
from app.services.crm.customer_health_types import (
    CalculateHealthInput,
    BulkHealthCalculationInput,
    ListHealthScoresInput,
    DetectPatternsInput,
    HealthGrade,
    RiskLevel,
)

router = APIRouter(prefix="/customer-health", tags=["CRM - Customer Health"])


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------


class HealthScoreBreakdownResponse(BaseModel):
    """Health score component breakdown."""

    ticket_frequency_score: float
    resolution_time_score: float
    csat_score: float
    escalation_score: float
    sla_compliance_score: float
    engagement_score: float


class TicketMetricsResponse(BaseModel):
    """Ticket metrics for a customer."""

    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    high_priority_tickets: int
    critical_tickets: int
    avg_resolution_hours: float
    avg_first_response_hours: float
    sla_breaches: int
    tickets_last_30_days: int
    tickets_last_90_days: int
    trend_direction: str


class CSATMetricsResponse(BaseModel):
    """CSAT metrics for a customer."""

    average_score: float
    response_count: int
    promoters: int
    passives: int
    detractors: int
    nps_score: Optional[float] = None
    trend_direction: str
    last_feedback_date: Optional[str] = None


class CustomerHealthScoreResponse(BaseModel):
    """Complete customer health score."""

    party_id: int
    overall_score: float
    grade: str
    breakdown: HealthScoreBreakdownResponse
    ticket_metrics: TicketMetricsResponse
    csat_metrics: CSATMetricsResponse
    calculated_at: str
    previous_score: Optional[float] = None
    score_change: float
    trend_direction: str


class CustomerHealthSummaryResponse(BaseModel):
    """Summary view of customer health."""

    party_id: int
    party_name: str
    overall_score: float
    grade: str
    churn_risk: str
    open_tickets: int
    avg_csat: Optional[float] = None
    last_ticket_date: Optional[str] = None
    has_alerts: bool
    alert_count: int


class ChurnRiskResponse(BaseModel):
    """Churn risk assessment response."""

    party_id: int
    risk_level: str
    risk_score: float
    contributing_factors: list[str]
    factor_details: dict
    recommended_actions: list[str]
    estimated_revenue_at_risk: Optional[float] = None
    assessed_at: str


class EscalationAlertResponse(BaseModel):
    """Escalation alert response."""

    party_id: int
    alert_type: str
    severity: str
    ticket_ids: list[int]
    escalation_count: int
    period_days: int
    message: str
    created_at: str


class SLABreachWarningResponse(BaseModel):
    """SLA breach warning response."""

    party_id: int
    breach_count: int
    breach_rate: float
    at_risk_tickets: list[int]
    avg_breach_hours: float
    severity: str
    created_at: str


class OpportunitySignalResponse(BaseModel):
    """Opportunity signal response."""

    party_id: int
    signal_type: str
    confidence: float
    source_ticket_ids: list[int]
    description: str
    suggested_product: Optional[str] = None
    suggested_action: str
    estimated_value: Optional[float] = None
    detected_at: str


class FeatureRequestResponse(BaseModel):
    """Aggregated feature request response."""

    feature_keyword: str
    request_count: int
    requesting_party_count: int
    first_requested: Optional[str] = None
    last_requested: Optional[str] = None
    priority_score: float


class RecurringIssueResponse(BaseModel):
    """Recurring issue pattern response."""

    issue_id: int
    category: str
    description: str
    occurrence_count: int
    first_occurrence: str
    last_occurrence: str
    affected_party_count: int
    avg_resolution_hours: float
    is_product_issue: bool
    suggested_action: Optional[str] = None


class PatternDetectionResponse(BaseModel):
    """Pattern detection results."""

    recurring_issues: list[RecurringIssueResponse]
    top_issue_categories: list[tuple[str, int]]
    common_keywords: list[tuple[str, int]]
    peak_ticket_hours: list[int]
    peak_ticket_days: list[int]
    analyzed_at: str


class HealthTrendPointResponse(BaseModel):
    """Single trend data point."""

    date: str
    score: float
    grade: str
    ticket_count: int
    csat_score: Optional[float] = None


class HealthTrendResponse(BaseModel):
    """Health score trend over time."""

    party_id: int
    period_days: int
    data_points: list[HealthTrendPointResponse]
    overall_trend: str
    trend_velocity: float


class HealthDashboardResponse(BaseModel):
    """Dashboard aggregate statistics."""

    total_customers: int
    excellent_count: int
    good_count: int
    at_risk_count: int
    critical_count: int
    avg_health_score: float
    churn_risk_high: int
    churn_risk_critical: int
    active_alerts: int
    total_open_tickets: int
    avg_resolution_hours: float
    avg_csat: float
    calculated_at: str


class PaginatedHealthSummariesResponse(BaseModel):
    """Paginated list of health summaries."""

    items: list[CustomerHealthSummaryResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _format_datetime(dt) -> Optional[str]:
    """Format datetime to ISO string."""
    return dt.isoformat() if dt else None


def _health_score_to_response(score) -> CustomerHealthScoreResponse:
    """Convert CustomerHealthScore to response schema."""
    return CustomerHealthScoreResponse(
        party_id=score.party_id,
        overall_score=score.overall_score,
        grade=score.grade.value,
        breakdown=HealthScoreBreakdownResponse(
            ticket_frequency_score=score.breakdown.ticket_frequency_score,
            resolution_time_score=score.breakdown.resolution_time_score,
            csat_score=score.breakdown.csat_score,
            escalation_score=score.breakdown.escalation_score,
            sla_compliance_score=score.breakdown.sla_compliance_score,
            engagement_score=score.breakdown.engagement_score,
        ),
        ticket_metrics=TicketMetricsResponse(
            total_tickets=score.ticket_metrics.total_tickets,
            open_tickets=score.ticket_metrics.open_tickets,
            resolved_tickets=score.ticket_metrics.resolved_tickets,
            escalated_tickets=score.ticket_metrics.escalated_tickets,
            high_priority_tickets=score.ticket_metrics.high_priority_tickets,
            critical_tickets=score.ticket_metrics.critical_tickets,
            avg_resolution_hours=score.ticket_metrics.avg_resolution_hours,
            avg_first_response_hours=score.ticket_metrics.avg_first_response_hours,
            sla_breaches=score.ticket_metrics.sla_breaches,
            tickets_last_30_days=score.ticket_metrics.tickets_last_30_days,
            tickets_last_90_days=score.ticket_metrics.tickets_last_90_days,
            trend_direction=score.ticket_metrics.trend_direction,
        ),
        csat_metrics=CSATMetricsResponse(
            average_score=score.csat_metrics.average_score,
            response_count=score.csat_metrics.response_count,
            promoters=score.csat_metrics.promoters,
            passives=score.csat_metrics.passives,
            detractors=score.csat_metrics.detractors,
            nps_score=score.csat_metrics.nps_score,
            trend_direction=score.csat_metrics.trend_direction,
            last_feedback_date=_format_datetime(score.csat_metrics.last_feedback_date),
        ),
        calculated_at=_format_datetime(score.calculated_at),
        previous_score=score.previous_score,
        score_change=score.score_change,
        trend_direction=score.trend_direction,
    )


# -----------------------------------------------------------------------------
# Health Score Endpoints
# -----------------------------------------------------------------------------


@router.get("/scores", response_model=PaginatedHealthSummariesResponse)
async def list_health_scores(
    grade: Optional[str] = Query(None, description="Filter by health grade"),
    risk_level: Optional[str] = Query(None, description="Filter by churn risk level"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    has_alerts: Optional[bool] = Query(None),
    sort_by: str = Query("score", enum=["score", "name", "ticket_count", "last_activity"]),
    sort_desc: bool = Query(True),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """List customer health scores with filtering and pagination."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    grade_filter = HealthGrade(grade) if grade else None
    risk_filter = RiskLevel(risk_level) if risk_level else None

    summaries, total = await service.list_health_scores(
        ListHealthScoresInput(
            grade_filter=grade_filter,
            risk_level_filter=risk_filter,
            min_score=min_score,
            max_score=max_score,
            has_alerts=has_alerts,
            sort_by=sort_by,
            sort_desc=sort_desc,
            page=page,
            per_page=per_page,
        )
    )

    items = [
        CustomerHealthSummaryResponse(
            party_id=s.party_id,
            party_name=s.party_name,
            overall_score=s.overall_score,
            grade=s.grade.value,
            churn_risk=s.churn_risk.value,
            open_tickets=s.open_tickets,
            avg_csat=s.avg_csat,
            last_ticket_date=_format_datetime(s.last_ticket_date),
            has_alerts=s.has_alerts,
            alert_count=s.alert_count,
        )
        for s in summaries
    ]

    return PaginatedHealthSummariesResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/scores/{party_id}", response_model=CustomerHealthScoreResponse)
async def get_health_score(
    party_id: int,
    lookback_days: int = Query(90, ge=7, le=365),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get detailed health score for a specific customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    score = await service.calculate_health_score(
        CalculateHealthInput(
            party_id=party_id,
            lookback_days=lookback_days,
        )
    )

    return _health_score_to_response(score)


@router.post("/scores/bulk", response_model=list[CustomerHealthScoreResponse])
async def bulk_calculate_scores(
    party_ids: Optional[list[int]] = None,
    lookback_days: int = Query(90, ge=7, le=365),
    grade_filter: Optional[str] = Query(None),
    min_ticket_count: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Bulk calculate health scores for multiple customers."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    scores = await service.bulk_calculate_health_scores(
        BulkHealthCalculationInput(
            party_ids=party_ids,
            lookback_days=lookback_days,
            health_grade_filter=HealthGrade(grade_filter) if grade_filter else None,
            min_ticket_count=min_ticket_count,
        )
    )

    return [_health_score_to_response(s) for s in scores]


@router.get("/scores/{party_id}/trend", response_model=HealthTrendResponse)
async def get_health_trend(
    party_id: int,
    period_days: int = Query(90, ge=14, le=365),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get health score trend over time for a customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    trend = await service.get_health_trend(party_id, period_days)

    return HealthTrendResponse(
        party_id=trend.party_id,
        period_days=trend.period_days,
        data_points=[
            HealthTrendPointResponse(
                date=_format_datetime(p.date),
                score=p.score,
                grade=p.grade.value,
                ticket_count=p.ticket_count,
                csat_score=p.csat_score,
            )
            for p in trend.data_points
        ],
        overall_trend=trend.overall_trend,
        trend_velocity=trend.trend_velocity,
    )


# -----------------------------------------------------------------------------
# Risk Assessment Endpoints
# -----------------------------------------------------------------------------


@router.get("/churn-risk/{party_id}", response_model=ChurnRiskResponse)
async def assess_churn_risk(
    party_id: int,
    lookback_days: int = Query(90, ge=7, le=365),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Assess churn risk for a specific customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    risk = await service.assess_churn_risk(party_id, lookback_days)

    return ChurnRiskResponse(
        party_id=risk.party_id,
        risk_level=risk.risk_level.value,
        risk_score=risk.risk_score,
        contributing_factors=[f.value for f in risk.contributing_factors],
        factor_details=risk.factor_details,
        recommended_actions=risk.recommended_actions,
        estimated_revenue_at_risk=float(risk.estimated_revenue_at_risk) if risk.estimated_revenue_at_risk else None,
        assessed_at=_format_datetime(risk.assessed_at),
    )


@router.get("/alerts/escalations/{party_id}", response_model=list[EscalationAlertResponse])
async def get_escalation_alerts(
    party_id: int,
    period_days: int = Query(30, ge=7, le=90),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get escalation alerts for a customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    alerts = await service.get_escalation_alerts(party_id, period_days)

    return [
        EscalationAlertResponse(
            party_id=a.party_id,
            alert_type=a.alert_type,
            severity=a.severity.value,
            ticket_ids=a.ticket_ids,
            escalation_count=a.escalation_count,
            period_days=a.period_days,
            message=a.message,
            created_at=_format_datetime(a.created_at),
        )
        for a in alerts
    ]


@router.get("/alerts/sla-breach/{party_id}", response_model=SLABreachWarningResponse)
async def get_sla_breach_warning(
    party_id: int,
    period_days: int = Query(30, ge=7, le=90),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get SLA breach warning for a customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    warning = await service.get_sla_breach_warnings(party_id, period_days)

    return SLABreachWarningResponse(
        party_id=warning.party_id,
        breach_count=warning.breach_count,
        breach_rate=warning.breach_rate,
        at_risk_tickets=warning.at_risk_tickets,
        avg_breach_hours=warning.avg_breach_hours,
        severity=warning.severity.value,
        created_at=_format_datetime(warning.created_at),
    )


# -----------------------------------------------------------------------------
# Opportunity Signal Endpoints
# -----------------------------------------------------------------------------


@router.get("/opportunities/{party_id}", response_model=list[OpportunitySignalResponse])
async def detect_opportunities(
    party_id: int,
    lookback_days: int = Query(180, ge=30, le=365),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Detect sales/expansion opportunities for a customer."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    signals = await service.detect_opportunity_signals(party_id, lookback_days)

    return [
        OpportunitySignalResponse(
            party_id=s.party_id,
            signal_type=s.signal_type.value,
            confidence=s.confidence,
            source_ticket_ids=s.source_ticket_ids,
            description=s.description,
            suggested_product=s.suggested_product,
            suggested_action=s.suggested_action,
            estimated_value=float(s.estimated_value) if s.estimated_value else None,
            detected_at=_format_datetime(s.detected_at),
        )
        for s in signals
    ]


@router.get("/feature-requests", response_model=list[FeatureRequestResponse])
async def get_feature_requests(
    lookback_days: int = Query(180, ge=30, le=365),
    min_requests: int = Query(2, ge=1),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get aggregated feature requests from support tickets."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    requests = await service.aggregate_feature_requests(lookback_days, min_requests)

    return [
        FeatureRequestResponse(
            feature_keyword=r.feature_keyword,
            request_count=r.request_count,
            requesting_party_count=len(r.requesting_parties),
            first_requested=_format_datetime(r.first_requested),
            last_requested=_format_datetime(r.last_requested),
            priority_score=r.priority_score,
        )
        for r in requests
    ]


# -----------------------------------------------------------------------------
# Pattern Detection Endpoints
# -----------------------------------------------------------------------------


@router.get("/patterns", response_model=PatternDetectionResponse)
async def detect_patterns(
    lookback_days: int = Query(90, ge=14, le=365),
    min_occurrence_count: int = Query(3, ge=2),
    include_resolved: bool = Query(True),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Detect recurring issue patterns across all customers."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    result = await service.detect_patterns(
        DetectPatternsInput(
            lookback_days=lookback_days,
            min_occurrence_count=min_occurrence_count,
            include_resolved=include_resolved,
        )
    )

    return PatternDetectionResponse(
        recurring_issues=[
            RecurringIssueResponse(
                issue_id=i.issue_id,
                category=i.category,
                description=i.description,
                occurrence_count=i.occurrence_count,
                first_occurrence=_format_datetime(i.first_occurrence),
                last_occurrence=_format_datetime(i.last_occurrence),
                affected_party_count=len(i.affected_parties),
                avg_resolution_hours=i.avg_resolution_hours,
                is_product_issue=i.is_product_issue,
                suggested_action=i.suggested_action,
            )
            for i in result.recurring_issues
        ],
        top_issue_categories=result.top_issue_categories,
        common_keywords=result.common_keywords,
        peak_ticket_hours=result.peak_ticket_hours,
        peak_ticket_days=result.peak_ticket_days,
        analyzed_at=_format_datetime(result.analyzed_at),
    )


# -----------------------------------------------------------------------------
# Dashboard Endpoints
# -----------------------------------------------------------------------------


@router.get("/dashboard", response_model=HealthDashboardResponse)
async def get_health_dashboard(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Get aggregate health statistics for the dashboard."""
    company_id = get_company_id(user)
    service = CustomerHealthService(session, company_id)

    stats = await service.get_dashboard_stats()

    return HealthDashboardResponse(
        total_customers=stats.total_customers,
        excellent_count=stats.excellent_count,
        good_count=stats.good_count,
        at_risk_count=stats.at_risk_count,
        critical_count=stats.critical_count,
        avg_health_score=stats.avg_health_score,
        churn_risk_high=stats.churn_risk_high,
        churn_risk_critical=stats.churn_risk_critical,
        active_alerts=stats.active_alerts,
        total_open_tickets=stats.total_open_tickets,
        avg_resolution_hours=stats.avg_resolution_hours,
        avg_csat=stats.avg_csat,
        calculated_at=_format_datetime(stats.calculated_at),
    )
