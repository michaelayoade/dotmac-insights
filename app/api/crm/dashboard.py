"""
CRM Dashboard API - Real-time CRM metrics and KPIs
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.services.crm.dashboard import CRMDashboardService
from app.services.crm.dashboard_types import DashboardFilters

router = APIRouter(prefix="/dashboard", tags=["crm-dashboard"])


def get_dashboard_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CRMDashboardService:
    """Create a CRMDashboardService instance for dependency injection."""
    return CRMDashboardService(db, principal)


# ============= SCHEMAS =============
class KPICardResponse(BaseModel):
    """Single KPI card for dashboard."""

    key: str
    title: str
    value: str  # Serialized as string
    formatted_value: str
    trend: Optional[float]
    trend_direction: Optional[str]
    comparison_period: Optional[str]
    icon: Optional[str]
    color: Optional[str]


class DashboardSummaryResponse(BaseModel):
    """Complete CRM dashboard summary."""

    total_leads: int
    new_leads_this_period: int
    qualified_leads: int
    lead_conversion_rate: float
    total_opportunities: int
    open_opportunities: int
    pipeline_value: float
    weighted_pipeline_value: float
    activities_due_today: int
    overdue_activities: int
    activities_completed_this_period: int
    won_deals_this_period: int
    won_value_this_period: float
    avg_deal_size: float
    win_rate: float
    kpi_cards: List[KPICardResponse]


class PipelineChartResponse(BaseModel):
    """Pipeline visualization data."""

    stages: List[dict]
    total_count: int
    total_value: float
    avg_per_stage: float


class FunnelChartResponse(BaseModel):
    """Lead/opportunity funnel data."""

    levels: List[dict]
    overall_conversion: float
    drop_off_stages: List[str]


class StageDistributionResponse(BaseModel):
    """Opportunity distribution by stage."""

    stage_id: int
    stage_name: str
    opportunity_count: int
    total_value: float
    avg_value: float
    avg_days_in_stage: float
    percentage_of_pipeline: float


class RevenueTrendResponse(BaseModel):
    """Revenue trend over time."""

    period_type: str
    data_points: List[dict]
    total_revenue: float
    avg_revenue: float
    trend_direction: str
    trend_percentage: float


class ConversionTrendResponse(BaseModel):
    """Conversion rate trend over time."""

    period_type: str
    data_points: List[dict]
    avg_conversion_rate: float
    best_period: Optional[str]
    worst_period: Optional[str]


class SalesForecastResponse(BaseModel):
    """Sales forecast data."""

    forecast_period: str
    predicted_revenue: float
    confidence_level: float
    best_case: float
    worst_case: float
    by_month: List[dict]
    by_stage: List[dict]


class TeamActivitySummaryResponse(BaseModel):
    """Team activity summary for dashboard."""

    total_activities: int
    completed_today: int
    pending_today: int
    overdue: int
    by_type: dict
    by_rep: List[dict]
    completion_rate: float


class UpcomingTaskResponse(BaseModel):
    """Upcoming task/activity for dashboard."""

    id: int
    type: str
    subject: str
    due_date: str
    due_time: Optional[str]
    party_id: Optional[int]
    party_name: Optional[str]
    opportunity_id: Optional[int]
    opportunity_name: Optional[str]
    priority: str
    is_overdue: bool


class OverdueItemsResponse(BaseModel):
    """Overdue items summary."""

    overdue_activities: int
    overdue_opportunities: int
    overdue_quotes: int
    overdue_tasks: int
    total_overdue_value: float
    items: List[dict]


class SalesRepRankingResponse(BaseModel):
    """Sales rep ranking for leaderboard."""

    rank: int
    rep_id: int
    rep_name: str
    avatar_url: Optional[str]
    won_deals: int
    won_value: float
    activities: int
    win_rate: float
    trend: Optional[str]


def _kpi_to_response(kpi) -> KPICardResponse:
    """Convert KPICard to response."""
    return KPICardResponse(
        key=kpi.key,
        title=kpi.title,
        value=str(kpi.value),
        formatted_value=kpi.formatted_value,
        trend=kpi.trend,
        trend_direction=kpi.trend_direction,
        comparison_period=kpi.comparison_period,
        icon=kpi.icon,
        color=kpi.color,
    )


# ============= ENDPOINTS =============
@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    period: str = Query("month", description="Period: day, week, month, quarter, year"),
    owner_id: Optional[int] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get complete CRM dashboard summary with KPIs."""
    filters = DashboardFilters(period=period, owner_id=owner_id)
    summary = service.get_dashboard_summary(filters)

    return DashboardSummaryResponse(
        total_leads=summary.total_leads,
        new_leads_this_period=summary.new_leads_this_period,
        qualified_leads=summary.qualified_leads,
        lead_conversion_rate=summary.lead_conversion_rate,
        total_opportunities=summary.total_opportunities,
        open_opportunities=summary.open_opportunities,
        pipeline_value=float(summary.pipeline_value),
        weighted_pipeline_value=float(summary.weighted_pipeline_value),
        activities_due_today=summary.activities_due_today,
        overdue_activities=summary.overdue_activities,
        activities_completed_this_period=summary.activities_completed_this_period,
        won_deals_this_period=summary.won_deals_this_period,
        won_value_this_period=float(summary.won_value_this_period),
        avg_deal_size=float(summary.avg_deal_size),
        win_rate=summary.win_rate,
        kpi_cards=[_kpi_to_response(k) for k in summary.kpi_cards],
    )


@router.get("/kpis", response_model=List[KPICardResponse])
async def get_kpi_cards(
    period: str = Query("month"),
    owner_id: Optional[int] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get KPI cards for dashboard."""
    filters = DashboardFilters(period=period, owner_id=owner_id)
    kpis = service.get_kpi_cards(filters)
    return [_kpi_to_response(k) for k in kpis]


@router.get("/pipeline", response_model=PipelineChartResponse)
async def get_pipeline_chart(
    owner_id: Optional[int] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get pipeline chart data by stage."""
    filters = DashboardFilters(owner_id=owner_id)
    chart = service.get_pipeline_chart(filters)

    return PipelineChartResponse(
        stages=chart.stages,
        total_count=chart.total_count,
        total_value=float(chart.total_value),
        avg_per_stage=float(chart.avg_per_stage),
    )


@router.get("/funnel", response_model=FunnelChartResponse)
async def get_funnel_chart(
    period: str = Query("month"),
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get lead/opportunity funnel data."""
    filters = DashboardFilters(period=period)
    funnel = service.get_funnel_chart(filters)

    return FunnelChartResponse(
        levels=funnel.levels,
        overall_conversion=funnel.overall_conversion,
        drop_off_stages=funnel.drop_off_stages,
    )


@router.get("/stages", response_model=List[StageDistributionResponse])
async def get_stage_distribution(
    owner_id: Optional[int] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get opportunity distribution by stage."""
    filters = DashboardFilters(owner_id=owner_id)
    stages = service.get_stage_distribution(filters)

    return [
        StageDistributionResponse(
            stage_id=s.stage_id,
            stage_name=s.stage_name,
            opportunity_count=s.opportunity_count,
            total_value=float(s.total_value),
            avg_value=float(s.avg_value),
            avg_days_in_stage=s.avg_days_in_stage,
            percentage_of_pipeline=s.percentage_of_pipeline,
        )
        for s in stages
    ]


@router.get("/revenue-trend", response_model=RevenueTrendResponse)
async def get_revenue_trend(
    period: str = Query("monthly", description="Grouping: daily, weekly, monthly"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    owner_id: Optional[int] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get revenue trend over time."""
    filters = DashboardFilters(
        start_date=start_date,
        end_date=end_date,
        owner_id=owner_id,
    )
    trend = service.get_revenue_trend(filters, period=period)

    return RevenueTrendResponse(
        period_type=trend.period_type,
        data_points=trend.data_points,
        total_revenue=float(trend.total_revenue),
        avg_revenue=float(trend.avg_revenue),
        trend_direction=trend.trend_direction,
        trend_percentage=trend.trend_percentage,
    )


@router.get("/conversion-trend", response_model=ConversionTrendResponse)
async def get_conversion_trend(
    period: str = Query("weekly", description="Grouping: daily, weekly, monthly"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get conversion rate trend over time."""
    filters = DashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    trend = service.get_conversion_trend(filters, period=period)

    return ConversionTrendResponse(
        period_type=trend.period_type,
        data_points=trend.data_points,
        avg_conversion_rate=trend.avg_conversion_rate,
        best_period=trend.best_period,
        worst_period=trend.worst_period,
    )


@router.get("/forecast", response_model=SalesForecastResponse)
async def get_forecast(
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get sales forecast."""
    forecast = service.get_forecast()

    return SalesForecastResponse(
        forecast_period=forecast.forecast_period,
        predicted_revenue=float(forecast.predicted_revenue),
        confidence_level=forecast.confidence_level,
        best_case=float(forecast.best_case),
        worst_case=float(forecast.worst_case),
        by_month=forecast.by_month,
        by_stage=forecast.by_stage,
    )


@router.get("/team-activity", response_model=TeamActivitySummaryResponse)
async def get_team_activity_summary(
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get team activity summary."""
    summary = service.get_team_activity_summary()

    return TeamActivitySummaryResponse(
        total_activities=summary.total_activities,
        completed_today=summary.completed_today,
        pending_today=summary.pending_today,
        overdue=summary.overdue,
        by_type=summary.by_type,
        by_rep=summary.by_rep,
        completion_rate=summary.completion_rate,
    )


@router.get("/upcoming-tasks", response_model=List[UpcomingTaskResponse])
async def get_upcoming_tasks(
    user_id: int = Query(..., description="User ID to get tasks for"),
    limit: int = Query(10, ge=1, le=50),
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get upcoming tasks for a user."""
    tasks = service.get_upcoming_tasks(user_id, limit)

    return [
        UpcomingTaskResponse(
            id=t.id,
            type=t.type,
            subject=t.subject,
            due_date=t.due_date.isoformat() if t.due_date else "",
            due_time=t.due_time,
            party_id=t.party_id,
            party_name=t.party_name,
            opportunity_id=t.opportunity_id,
            opportunity_name=t.opportunity_name,
            priority=t.priority,
            is_overdue=t.is_overdue,
        )
        for t in tasks
    ]


@router.get("/overdue", response_model=OverdueItemsResponse)
async def get_overdue_items(
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get overdue items summary."""
    items = service.get_overdue_items()

    return OverdueItemsResponse(
        overdue_activities=items.overdue_activities,
        overdue_opportunities=items.overdue_opportunities,
        overdue_quotes=items.overdue_quotes,
        overdue_tasks=items.overdue_tasks,
        total_overdue_value=float(items.total_overdue_value),
        items=items.items,
    )


@router.get("/leaderboard", response_model=List[SalesRepRankingResponse])
async def get_sales_leaderboard(
    period: str = Query("month"),
    limit: int = Query(10, ge=1, le=50),
    service: CRMDashboardService = Depends(get_dashboard_service),
):
    """Get sales leaderboard."""
    filters = DashboardFilters(period=period)
    rankings = service.get_sales_leaderboard(filters, limit)

    return [
        SalesRepRankingResponse(
            rank=r.rank,
            rep_id=r.rep_id,
            rep_name=r.rep_name,
            avatar_url=r.avatar_url,
            won_deals=r.won_deals,
            won_value=float(r.won_value),
            activities=r.activities,
            win_rate=r.win_rate,
            trend=r.trend,
        )
        for r in rankings
    ]
