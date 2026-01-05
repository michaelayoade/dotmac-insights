"""
Field Service Analytics API

Performance metrics, completion rates, and utilization reports.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, timedelta

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.services.field_service import (
    FieldServiceAnalyticsService,
    AnalyticsFilters,
)

router = APIRouter()


def get_period_dates(period: str) -> tuple[date, date]:
    """Get start and end dates for a given period."""
    end = date.today()
    if period == "week":
        start = end - timedelta(days=7)
    elif period == "month":
        start = end - timedelta(days=30)
    elif period == "quarter":
        start = end - timedelta(days=90)
    elif period == "year":
        start = end - timedelta(days=365)
    else:
        start = end - timedelta(days=30)
    return start, end


# =============================================================================
# DASHBOARD (FRONTEND)
# =============================================================================


@router.get("/analytics/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("field-service-dashboard", ttl=CACHE_TTL["short"])
async def get_analytics_dashboard(
    period: str = "month",
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get dashboard metrics for field service analytics page."""
    start, end = get_period_dates(period)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)
    metrics = service.get_dashboard_metrics(filters)

    return {
        "period": {
            "name": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": metrics.total_orders,
            "completed_orders": metrics.completed_orders,
            "completion_rate": metrics.completion_rate,
            "cancellation_rate": round(
                metrics.cancelled_orders / metrics.total_orders * 100, 1
            ) if metrics.total_orders > 0 else 0,
            "avg_rating": metrics.avg_customer_rating if metrics.avg_customer_rating > 0 else None,
            "total_ratings": metrics.total_orders,  # Simplified
            "avg_response_time": None,  # Not tracked in service yet
            "avg_service_duration": round(metrics.avg_completion_time_hours * 60, 0) if metrics.avg_completion_time_hours else None,
            "avg_travel_time": None,  # Not tracked in service yet
            "total_revenue": float(metrics.total_revenue),
            "orders_trend": 0,  # Calculate if needed
        },
        "status_distribution": {},  # Can be added to service if needed
        "daily_trend": [],  # Can be added to service if needed
    }


@router.get("/analytics/order-type-breakdown", dependencies=[Depends(Require("analytics:read"))])
async def get_order_type_breakdown(
    period: str = "month",
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get breakdown of orders by type."""
    start, end = get_period_dates(period)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)
    breakdown = service.get_order_type_breakdown(filters)

    return {
        "period": period,
        "data": [
            {
                "order_type": b.order_type,
                "count": b.count,
                "completed": int(b.count * b.percentage / 100),  # Approximate
                "completion_rate": b.percentage,
                "avg_rating": None,  # Can be added if needed
            }
            for b in breakdown
        ],
    }


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================


@router.get("/analytics/performance", dependencies=[Depends(Require("analytics:read"))])
@cached("field-service-performance", ttl=CACHE_TTL["medium"])
async def get_performance_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get overall field service performance metrics."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)

    metrics = service.get_dashboard_metrics(filters)
    perf = service.get_performance_metrics(filters)
    breakdown = service.get_order_type_breakdown(filters)

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": metrics.total_orders,
            "completed": metrics.completed_orders,
            "cancelled": metrics.cancelled_orders,
            "completion_rate": metrics.completion_rate,
            "first_time_fix_rate": perf.first_time_fix_rate,
            "avg_duration_hours": perf.avg_work_time_hours,
        },
        "customer_satisfaction": {
            "avg_rating": metrics.avg_customer_rating,
            "total_ratings": metrics.completed_orders,  # Simplified
            "response_rate": 0,  # Can be calculated if needed
        },
        "by_priority": [],  # Can be added to service if needed
        "by_type": [
            {
                "order_type": b.order_type,
                "total": b.count,
                "completed": int(b.count * b.percentage / 100),
                "completion_rate": b.percentage,
            }
            for b in breakdown
        ],
    }


@router.get("/analytics/technician-performance", dependencies=[Depends(Require("analytics:read"))])
async def get_technician_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    team_id: Optional[int] = None,
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get performance metrics by technician."""
    # Support both period and explicit dates
    if period:
        start, end = get_period_dates(period)
    elif end_date:
        end = date.fromisoformat(end_date)
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=30)
    else:
        end = date.today()
        start = end - timedelta(days=30)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end, team_id=team_id)
    tech_perf = service.get_technician_performance(filters, team_id=team_id, limit=limit)

    performance = [
        {
            "id": t.technician_id,
            "technician_id": t.technician_id,
            "name": t.technician_name,
            "technician_name": t.technician_name,
            "team_name": None,  # Can be added if needed
            "total_orders": t.total_orders,
            "completed_orders": t.completed_orders,
            "completed": t.completed_orders,
            "completion_rate": t.completion_rate,
            "avg_rating": t.avg_rating,
            "rating_count": 0,  # Can be added if needed
            "avg_duration_hours": t.avg_completion_time_hours,
            "billable_hours": 0,  # Can be added if needed
        }
        for t in tech_perf
    ]

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "data": performance,
        "technicians": performance,
    }


@router.get("/analytics/team-performance", dependencies=[Depends(Require("analytics:read"))])
async def get_team_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get performance metrics by team."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)
    team_perf = service.get_team_performance(filters)

    performance = [
        {
            "team_id": t.team_id,
            "team_name": t.team_name,
            "member_count": t.member_count,
            "total_orders": t.total_orders,
            "completed": t.completed_orders,
            "completion_rate": t.completion_rate,
            "avg_rating": t.avg_rating,
            "total_billed": float(t.total_revenue),
            "total_cost": 0,  # Can be added if needed
            "profit": float(t.total_revenue),  # Simplified
        }
        for t in team_perf
    ]

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "teams": performance,
    }


# =============================================================================
# TRENDS
# =============================================================================

@router.get("/analytics/trends", dependencies=[Depends(Require("analytics:read"))])
async def get_trends(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get monthly trends for service orders."""
    service = FieldServiceAnalyticsService(db, principal)
    trends_data = service.get_monthly_trends(months=months)

    trends = [
        {
            "period": t.period,
            "total": t.total_orders,
            "completed": t.completed_orders,
            "cancelled": 0,  # Not tracked separately in service
            "completion_rate": round(
                (t.completed_orders / t.total_orders * 100), 1
            ) if t.total_orders > 0 else 0,
            "avg_rating": 0,  # Can be added to service if needed
        }
        for t in trends_data
    ]

    return {
        "months": months,
        "trends": trends,
    }


# =============================================================================
# COST ANALYSIS
# =============================================================================

@router.get("/analytics/costs", dependencies=[Depends(Require("analytics:read"))])
async def get_cost_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get cost analysis for field service operations."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)
    costs = service.get_cost_analysis(filters)

    total_cost = float(costs.total_labor_cost + costs.total_parts_cost + costs.total_travel_cost)
    total_revenue = float(costs.avg_revenue_per_order) * 1  # Simplified calculation

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": 0,  # Not directly available from cost analysis
            "total_cost": round(total_cost, 2),
            "total_billed": round(float(costs.avg_revenue_per_order), 2),
            "gross_profit": round(float(costs.profit_per_order), 2),
            "profit_margin": round(
                float(costs.profit_per_order) / float(costs.avg_revenue_per_order) * 100, 1
            ) if costs.avg_revenue_per_order > 0 else 0,
            "avg_cost_per_order": round(float(costs.avg_cost_per_order), 2),
            "avg_billed_per_order": round(float(costs.avg_revenue_per_order), 2),
        },
        "cost_breakdown": {
            "labor": round(float(costs.total_labor_cost), 2),
            "parts": round(float(costs.total_parts_cost), 2),
            "travel": round(float(costs.total_travel_cost), 2),
            "labor_pct": round(
                float(costs.total_labor_cost) / total_cost * 100, 1
            ) if total_cost > 0 else 0,
            "parts_pct": round(
                float(costs.total_parts_cost) / total_cost * 100, 1
            ) if total_cost > 0 else 0,
            "travel_pct": round(
                float(costs.total_travel_cost) / total_cost * 100, 1
            ) if total_cost > 0 else 0,
        },
        "by_type": [],  # Can be extended in service if needed
    }


# =============================================================================
# UTILIZATION
# =============================================================================

@router.get("/analytics/utilization", dependencies=[Depends(Require("analytics:read"))])
async def get_utilization(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get resource utilization metrics."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    service = FieldServiceAnalyticsService(db, principal)
    filters = AnalyticsFilters(start_date=start, end_date=end)
    util = service.get_utilization(filters)

    # Calculate working days in period
    working_days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday to Friday
            working_days += 1
        current += timedelta(days=1)

    # Estimate technician count from by_technician data
    technician_count = len(util.by_technician)

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "working_days": working_days,
        },
        "capacity": {
            "technician_count": technician_count,
            "total_available_hours": util.total_available_hours,
        },
        "utilization": {
            "work_hours": util.total_worked_hours,
            "travel_hours": 0,  # Not tracked separately in service
            "total_logged_hours": util.total_worked_hours,
            "utilization_rate": util.utilization_rate,
            "billable_hours": 0,  # Can be added to service if needed
            "billable_rate": 0,
        },
        "productivity": {
            "total_orders": 0,  # Can be added to service if needed
            "orders_per_tech_per_day": 0,
            "avg_hours_per_order": 0,
        },
    }
