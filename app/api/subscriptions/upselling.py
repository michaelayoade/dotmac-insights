"""Upselling API Endpoints.

REST API for upselling opportunity management and analytics.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_or_none
from app.database import get_db
from app.services.subscriptions.upselling import UpsellingService
from app.services.subscriptions.upselling_types import (
    AnalysisResult,
    BatchAnalysisInput,
    BatchAnalysisResult,
    ConversionStats,
    OpportunityListFilters,
    RevenueForecast,
    TriggerType,
    UpgradeRecommendation,
)

router = APIRouter(prefix="/upselling", tags=["Upselling"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class OpportunityResponse(BaseModel):
    """Upsell opportunity response."""
    id: int
    subscription_id: int
    party_id: int
    trigger_type: str
    trigger_score: int
    current_plan_name: str
    current_mrr: float
    recommended_plan_name: Optional[str]
    recommended_mrr: Optional[float]
    monthly_revenue_increase: float
    annual_revenue_increase: float
    status: str
    priority: str
    assigned_to_id: Optional[int]
    contacted_at: Optional[datetime]
    converted_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, opp):
        return cls(
            id=opp.id,
            subscription_id=opp.subscription_id,
            party_id=opp.party_id,
            trigger_type=opp.trigger_type,
            trigger_score=opp.trigger_score,
            current_plan_name=opp.current_plan_name,
            current_mrr=float(opp.current_mrr),
            recommended_plan_name=opp.recommended_plan_name,
            recommended_mrr=float(opp.recommended_mrr) if opp.recommended_mrr else None,
            monthly_revenue_increase=float(opp.monthly_revenue_increase),
            annual_revenue_increase=float(opp.annual_revenue_increase),
            status=opp.status,
            priority=opp.priority,
            assigned_to_id=opp.assigned_to_id,
            contacted_at=opp.contacted_at,
            converted_at=opp.converted_at,
            expires_at=opp.expires_at,
            created_at=opp.created_at,
        )


class PaginatedOpportunitiesResponse(BaseModel):
    """Paginated list of opportunities."""
    items: List[OpportunityResponse]
    total: int
    page: int
    per_page: int


class TriggerEvidenceResponse(BaseModel):
    """Trigger evidence in analysis result."""
    trigger_type: str
    confidence_score: int
    metrics: Dict[str, Any]
    explanation: str


class RecommendationResponse(BaseModel):
    """Upgrade recommendation in analysis result."""
    tariff_id: int
    tariff_name: str
    current_price: float
    new_price: float
    price_increase: float
    speed_increase_mbps: int
    features_added: List[str]
    match_score: int


class AnalysisResultResponse(BaseModel):
    """Single subscription analysis result."""
    subscription_id: int
    party_id: int
    current_plan: str
    current_mrr: float
    triggers_found: List[TriggerEvidenceResponse]
    recommendations: List[RecommendationResponse]
    potential_mrr_increase: float
    priority: str


class BatchAnalysisRequest(BaseModel):
    """Request for batch analysis."""
    subscription_ids: Optional[List[int]] = None
    trigger_types: Optional[List[str]] = None
    min_months_active: int = 3
    exclude_recently_analyzed: bool = True
    recently_analyzed_days: int = 7


class BatchAnalysisResponse(BaseModel):
    """Response for batch analysis."""
    run_id: int
    subscriptions_analyzed: int
    opportunities_found: int
    opportunities_by_trigger: Dict[str, int]
    total_potential_mrr: float
    duration_seconds: float


class AssignRequest(BaseModel):
    """Request to assign opportunity."""
    employee_id: int


class ContactRequest(BaseModel):
    """Request to mark as contacted."""
    method: str = Field(..., description="Contact method (call, email, sms, etc.)")
    notes: Optional[str] = None


class ConvertRequest(BaseModel):
    """Request to mark as converted."""
    new_subscription_id: int
    converted_by_id: Optional[int] = None


class DeclineRequest(BaseModel):
    """Request to mark as declined."""
    reason: str


class ConversionStatsResponse(BaseModel):
    """Conversion statistics response."""
    period: str
    total_opportunities: int
    converted_count: int
    declined_count: int
    expired_count: int
    conversion_rate: float
    total_mrr_gained: float
    avg_mrr_per_conversion: float
    avg_days_to_convert: float


class RevenueForecastResponse(BaseModel):
    """Revenue forecast response."""
    total_opportunities: int
    active_opportunities: int
    potential_monthly_revenue: float
    potential_annual_revenue: float
    expected_conversion_rate: float
    expected_monthly_revenue: float
    expected_annual_revenue: float
    by_trigger_type: Dict[str, float]
    by_priority: Dict[str, float]


class DashboardStatsResponse(BaseModel):
    """Dashboard statistics."""
    open_opportunities: int
    high_priority_count: int
    expiring_soon_count: int
    total_potential_mrr: float
    conversion_rate_30d: float
    mrr_gained_30d: float
    by_status: Dict[str, int]
    by_trigger: Dict[str, int]


# =============================================================================
# Analysis Endpoints
# =============================================================================

def get_company_id(current_user) -> int:
    """Get company_id from user, requiring authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user.company_id


@router.post(
    "/analyze/{subscription_id}",
    response_model=AnalysisResultResponse,
    summary="Analyze subscription for upselling",
)
async def analyze_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Analyze a single subscription for upselling opportunities."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    try:
        result = await service.analyze_subscription(subscription_id)

        triggers = [
            TriggerEvidenceResponse(
                trigger_type=t.trigger_type.value,
                confidence_score=t.confidence_score,
                metrics=t.metrics,
                explanation=t.explanation,
            )
            for t in result.triggers_found
        ]

        recommendations = [
            RecommendationResponse(
                tariff_id=r.tariff_id,
                tariff_name=r.tariff_name,
                current_price=float(r.current_price),
                new_price=float(r.new_price),
                price_increase=float(r.price_increase),
                speed_increase_mbps=r.speed_increase_mbps,
                features_added=r.features_added,
                match_score=r.match_score,
            )
            for r in result.recommendations
        ]

        return AnalysisResultResponse(
            subscription_id=result.subscription_id,
            party_id=result.party_id,
            current_plan=result.current_plan,
            current_mrr=float(result.current_mrr),
            triggers_found=triggers,
            recommendations=recommendations,
            potential_mrr_increase=float(result.potential_mrr_increase),
            priority=result.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/analyze/batch",
    response_model=BatchAnalysisResponse,
    summary="Run batch analysis",
)
async def run_batch_analysis(
    request: BatchAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Run batch analysis on multiple subscriptions.

    Analyzes subscriptions for upselling opportunities based on usage patterns,
    bundle exhaustion, speed limits, loyalty, and contract renewal triggers.
    """
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    # Validate trigger types
    trigger_types = None
    if request.trigger_types:
        valid_types = {t.value for t in TriggerType}
        invalid = [t for t in request.trigger_types if t not in valid_types]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trigger types: {invalid}. Valid types: {list(valid_types)}",
            )
        trigger_types = [TriggerType(t) for t in request.trigger_types]

    input_data = BatchAnalysisInput(
        subscription_ids=request.subscription_ids,
        trigger_types=trigger_types,
        min_months_active=request.min_months_active,
        exclude_recently_analyzed=request.exclude_recently_analyzed,
        recently_analyzed_days=request.recently_analyzed_days,
    )

    try:
        result = await service.run_batch_analysis(input_data)
        await db.commit()

        return BatchAnalysisResponse(
            run_id=result.run_id,
            subscriptions_analyzed=result.subscriptions_analyzed,
            opportunities_found=result.opportunities_found,
            opportunities_by_trigger=result.opportunities_by_trigger,
            total_potential_mrr=float(result.total_potential_mrr),
            duration_seconds=result.duration_seconds,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Opportunity Management Endpoints
# =============================================================================

@router.get(
    "/opportunities",
    response_model=PaginatedOpportunitiesResponse,
    summary="List upselling opportunities",
)
async def list_opportunities(
    status: Optional[str] = Query(None, description="Filter by status"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    assigned_to_id: Optional[int] = Query(None, description="Filter by assignee"),
    min_score: Optional[int] = Query(None, description="Minimum trigger score"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """List upselling opportunities with filters."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    filters = OpportunityListFilters(
        status=status,
        trigger_type=trigger_type,
        priority=priority,
        assigned_to_id=assigned_to_id,
        min_score=min_score,
    )

    opportunities, total = await service.list_opportunities(filters, page, per_page)

    return PaginatedOpportunitiesResponse(
        items=[OpportunityResponse.from_model(o) for o in opportunities],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/opportunities/{opportunity_id}",
    response_model=OpportunityResponse,
    summary="Get opportunity details",
)
async def get_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get detailed information about an upselling opportunity."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    opportunity = await service.get_opportunity(opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return OpportunityResponse.from_model(opportunity)


@router.post(
    "/opportunities/{opportunity_id}/assign",
    response_model=OpportunityResponse,
    summary="Assign opportunity",
)
async def assign_opportunity(
    opportunity_id: int,
    request: AssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Assign an opportunity to a sales representative."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    try:
        opportunity = await service.assign_opportunity(opportunity_id, request.employee_id)
        await db.commit()
        return OpportunityResponse.from_model(opportunity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/opportunities/{opportunity_id}/contact",
    response_model=OpportunityResponse,
    summary="Mark as contacted",
)
async def mark_contacted(
    opportunity_id: int,
    request: ContactRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Mark an opportunity as contacted."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    try:
        opportunity = await service.mark_contacted(
            opportunity_id, request.method, request.notes
        )
        await db.commit()
        return OpportunityResponse.from_model(opportunity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/opportunities/{opportunity_id}/convert",
    response_model=OpportunityResponse,
    summary="Mark as converted",
)
async def mark_converted(
    opportunity_id: int,
    request: ConvertRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Mark an opportunity as converted (customer upgraded)."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    try:
        opportunity = await service.mark_converted(
            opportunity_id, request.new_subscription_id, request.converted_by_id
        )
        await db.commit()
        return OpportunityResponse.from_model(opportunity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/opportunities/{opportunity_id}/decline",
    response_model=OpportunityResponse,
    summary="Mark as declined",
)
async def mark_declined(
    opportunity_id: int,
    request: DeclineRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Mark an opportunity as declined by customer."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    try:
        opportunity = await service.mark_declined(opportunity_id, request.reason)
        await db.commit()
        return OpportunityResponse.from_model(opportunity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/opportunities/expire",
    summary="Expire old opportunities",
)
async def expire_opportunities(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Expire opportunities past their expiry date."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    count = await service.expire_old_opportunities()
    await db.commit()

    return {"expired_count": count}


# =============================================================================
# Analytics Endpoints
# =============================================================================

@router.get(
    "/stats/dashboard",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get upselling dashboard statistics."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    # Get conversion stats for context
    stats = await service.get_conversion_stats(30)
    forecast = await service.get_revenue_forecast()

    # Get opportunities by status
    open_filters = OpportunityListFilters(status="new")
    open_opps, open_total = await service.list_opportunities(open_filters, 1, 1)

    high_priority_filters = OpportunityListFilters(priority="urgent")
    high_priority, hp_total = await service.list_opportunities(high_priority_filters, 1, 1)

    return DashboardStatsResponse(
        open_opportunities=open_total,
        high_priority_count=hp_total,
        expiring_soon_count=0,  # Would query opportunities expiring in 7 days
        total_potential_mrr=float(forecast.potential_monthly_revenue),
        conversion_rate_30d=stats.conversion_rate,
        mrr_gained_30d=float(stats.total_mrr_gained),
        by_status={},  # Would aggregate from opportunities
        by_trigger={},  # Would aggregate from opportunities
    )


@router.get(
    "/stats/conversion",
    response_model=ConversionStatsResponse,
    summary="Get conversion statistics",
)
async def get_conversion_stats(
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get conversion statistics for the specified period."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    stats = await service.get_conversion_stats(period_days)

    return ConversionStatsResponse(
        period=stats.period,
        total_opportunities=stats.total_opportunities,
        converted_count=stats.converted_count,
        declined_count=stats.declined_count,
        expired_count=stats.expired_count,
        conversion_rate=stats.conversion_rate,
        total_mrr_gained=float(stats.total_mrr_gained),
        avg_mrr_per_conversion=float(stats.avg_mrr_per_conversion),
        avg_days_to_convert=stats.avg_days_to_convert,
    )


@router.get(
    "/stats/forecast",
    response_model=RevenueForecastResponse,
    summary="Get revenue forecast",
)
async def get_revenue_forecast(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get revenue forecast from active opportunities."""
    company_id = get_company_id(current_user)
    service = UpsellingService(db, company_id)

    forecast = await service.get_revenue_forecast()

    return RevenueForecastResponse(
        total_opportunities=forecast.total_opportunities,
        active_opportunities=forecast.active_opportunities,
        potential_monthly_revenue=float(forecast.potential_monthly_revenue),
        potential_annual_revenue=float(forecast.potential_annual_revenue),
        expected_conversion_rate=forecast.expected_conversion_rate,
        expected_monthly_revenue=float(forecast.expected_monthly_revenue),
        expected_annual_revenue=float(forecast.expected_annual_revenue),
        by_trigger_type={k: float(v) for k, v in forecast.by_trigger_type.items()},
        by_priority={k: float(v) for k, v in forecast.by_priority.items()},
    )


@router.get(
    "/trigger-types",
    summary="List available trigger types",
)
async def list_trigger_types():
    """List all available upselling trigger types."""
    return {
        "trigger_types": [
            {
                "value": t.value,
                "name": t.name.replace("_", " ").title(),
                "description": _get_trigger_description(t),
            }
            for t in TriggerType
        ]
    }


def _get_trigger_description(trigger: TriggerType) -> str:
    """Get description for a trigger type."""
    descriptions = {
        TriggerType.HIGH_USAGE: "Customer consistently uses high percentage of their data cap",
        TriggerType.BUNDLE_EXHAUSTION: "Customer frequently exhausts their data bundle",
        TriggerType.SPEED_UPGRADE: "Customer may benefit from faster speeds based on usage",
        TriggerType.PLAN_MISMATCH: "Customer's usage patterns don't match their current plan",
        TriggerType.LOYALTY_UPGRADE: "Long-term customer eligible for loyalty upgrade",
        TriggerType.CONTRACT_RENEWAL: "Contract expiring soon, opportunity for upgrade discussion",
        TriggerType.FEATURE_REQUEST: "Customer has requested features available in higher plans",
    }
    return descriptions.get(trigger, "")
