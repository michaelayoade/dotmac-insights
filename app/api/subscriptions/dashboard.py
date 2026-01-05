"""
Subscription Dashboard API

Dashboard endpoints for subscription analytics and KPIs.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.cache import cached, CACHE_TTL
from app.services.subscriptions import (
    SubscriptionReportsService,
    ReportPeriod,
)

router = APIRouter()


@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-dashboard", ttl=CACHE_TTL["short"])
async def get_dashboard(
    currency: str = Query("NGN", description="Currency for financial metrics"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get complete subscription dashboard with KPIs and chart data.

    Returns:
        - kpis: Key performance indicators
        - charts: Chart data for visualizations
        - generated_at: Timestamp
        - currency: Currency used
    """
    service = SubscriptionReportsService(db, principal)
    summary = service.get_dashboard_summary(currency=currency)
    return service.export_to_dict(summary)


@router.get("/kpis", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-kpis", ttl=CACHE_TTL["short"])
async def get_kpis(
    currency: str = Query("NGN", description="Currency for financial metrics"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscription KPIs only.

    Returns metrics like:
    - Total/active/suspended subscriptions
    - MRR, ARR, ARPU
    - Growth and churn rates
    - Provisioning stats
    """
    service = SubscriptionReportsService(db, principal)
    kpis = service._get_dashboard_kpis(currency=currency)
    return service.export_to_dict(kpis)


@router.get("/charts", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-charts", ttl=CACHE_TTL["short"])
async def get_charts(
    currency: str = Query("NGN", description="Currency for financial metrics"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscription chart data only.

    Returns:
    - mrr_trend: MRR over last 12 months
    - by_status: Subscriptions by status (pie chart)
    - by_service_type: Subscriptions by type (pie chart)
    - growth_vs_churn: New vs churned (bar chart)
    - top_plans: Top plans by subscriber count
    - revenue_by_type: Revenue breakdown by service type
    """
    service = SubscriptionReportsService(db, principal)
    charts = service._get_dashboard_charts(currency=currency)
    return service.export_to_dict(charts)


@router.get("/quick-stats", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-quick-stats", ttl=CACHE_TTL["very_short"])
async def get_quick_stats(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get quick stats for widgets/tiles.

    Returns minimal data for dashboard tiles:
    - total_active
    - mrr
    - churn_rate
    - new_this_month
    """
    from app.services.subscriptions import SubscriptionService

    sub_service = SubscriptionService(db, principal)
    stats = sub_service.get_stats()

    return {
        "total_active": stats.active,
        "total_suspended": stats.suspended,
        "total_pending": stats.pending,
        "mrr": float(stats.mrr),
        "new_this_month": stats.new_this_month,
    }
