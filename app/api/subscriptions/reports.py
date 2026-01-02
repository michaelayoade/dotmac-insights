"""
Subscription Reports API

Detailed analytics and reporting endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.cache import cached, CACHE_TTL
from app.services.subscriptions import (
    SubscriptionReportsService,
    ReportPeriod,
)

router = APIRouter()


def parse_period(period: str) -> ReportPeriod:
    """Parse period string to ReportPeriod enum."""
    try:
        return ReportPeriod(period)
    except ValueError:
        return ReportPeriod.THIS_MONTH


@router.get("/mrr", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-mrr-report", ttl=CACHE_TTL["medium"])
async def get_mrr_report(
    period: str = Query("this_month", description="Report period"),
    currency: str = Query("NGN", description="Currency"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get MRR (Monthly Recurring Revenue) analytics.

    Returns:
    - current_mrr, previous_mrr, mrr_growth
    - ARR (Annual Recurring Revenue)
    - Breakdown by service type, plan, billing cycle
    - 12-month trends with ARPU
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_mrr_summary(
        period=parse_period(period),
        currency=currency,
    )
    return service.export_to_dict(report)


@router.get("/churn", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-churn-report", ttl=CACHE_TTL["medium"])
async def get_churn_report(
    period: str = Query("this_month", description="Report period"),
    currency: str = Query("NGN", description="Currency"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get churn analysis report.

    Returns:
    - Churned count and rate (current vs previous)
    - MRR lost to churn
    - At-risk subscriptions (suspended)
    - Churn by reason breakdown
    - Retention cohorts
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_churn_summary(
        period=parse_period(period),
        currency=currency,
    )
    return service.export_to_dict(report)


@router.get("/revenue", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-revenue-report", ttl=CACHE_TTL["medium"])
async def get_revenue_report(
    period: str = Query("this_month", description="Report period"),
    currency: str = Query("NGN", description="Currency"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get revenue summary report.

    Returns:
    - Total revenue (subscription, usage, fees)
    - Period comparison with growth %
    - Breakdown by service type and plan
    - AR aging summary
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_revenue_summary(
        period=parse_period(period),
        currency=currency,
    )
    return service.export_to_dict(report)


@router.get("/usage", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-usage-report", ttl=CACHE_TTL["medium"])
async def get_usage_report(
    period: str = Query("this_month", description="Report period"),
    top_users_limit: int = Query(20, ge=5, le=100, description="Number of top users to include"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get usage analytics report.

    Returns:
    - Total upload/download in GB
    - Average per user, peak day
    - Active users count
    - Usage trends over time
    - Top users by bandwidth
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_usage_report(
        period=parse_period(period),
        limit_top_users=top_users_limit,
    )
    return service.export_to_dict(report)


@router.get("/provisioning", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-provisioning-report", ttl=CACHE_TTL["medium"])
async def get_provisioning_report(
    period: str = Query("this_month", description="Report period"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get provisioning analytics report.

    Returns:
    - Total operations, success/fail/pending counts
    - Overall success rate
    - Breakdown by action type, router, access method
    - Average provisioning duration
    - Recent failures list
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_provisioning_report(
        period=parse_period(period),
    )
    return service.export_to_dict(report)


@router.get("/ltv", dependencies=[Depends(Require("subscriptions:read"))])
@cached("subscription-ltv-report", ttl=CACHE_TTL["long"])
async def get_ltv_report(
    currency: str = Query("NGN", description="Currency"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get customer lifetime value report.

    Returns:
    - Average LTV, tenure, monthly revenue
    - LTV distribution brackets
    - LTV by service type
    - Customer segments (high_value, at_risk, new)
    - Top customers by LTV
    """
    service = SubscriptionReportsService(db, principal)
    report = service.get_customer_ltv_report(currency=currency)
    return service.export_to_dict(report)


@router.get("/export/{report_type}", dependencies=[Depends(Require("subscriptions:export"))])
async def export_report(
    report_type: str,
    period: str = Query("this_month", description="Report period"),
    format: str = Query("json", description="Export format (json, csv)"),
    currency: str = Query("NGN", description="Currency"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Export a report in specified format.

    Supported report types:
    - mrr, churn, revenue, usage, provisioning, ltv

    Supported formats:
    - json (default)
    - csv (flattened)
    """
    service = SubscriptionReportsService(db, principal)
    period_enum = parse_period(period)

    # Get report data
    if report_type == "mrr":
        report = service.get_mrr_summary(period=period_enum, currency=currency)
    elif report_type == "churn":
        report = service.get_churn_summary(period=period_enum, currency=currency)
    elif report_type == "revenue":
        report = service.get_revenue_summary(period=period_enum, currency=currency)
    elif report_type == "usage":
        report = service.get_usage_report(period=period_enum)
    elif report_type == "provisioning":
        report = service.get_provisioning_report(period=period_enum)
    elif report_type == "ltv":
        report = service.get_customer_ltv_report(currency=currency)
    else:
        return {"error": f"Unknown report type: {report_type}"}

    data = service.export_to_dict(report)

    if format == "csv":
        # For CSV, return data in flat format
        # Actual CSV generation would be handled by response
        return {
            "format": "csv",
            "data": data,
            "note": "Use Accept: text/csv header for actual CSV download",
        }

    return {
        "format": "json",
        "report_type": report_type,
        "period": period,
        "currency": currency,
        "data": data,
    }
