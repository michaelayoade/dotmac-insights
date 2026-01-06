"""
Finance Domain Router

Thin wrapper around FinanceService providing all finance-related endpoints:
- /dashboard - Revenue KPIs, collections, DSO
- /analytics/* - Revenue trends, aging, collections
- /insights/* - Payment behavior, forecasts
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.services.finance import FinanceService
from app.services.errors import ValidationError
from fastapi import HTTPException

router = APIRouter()


def _handle_validation_error(func):
    """Decorator to convert ValidationError to HTTPException."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=e.message)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# =============================================================================
# DASHBOARD
# =============================================================================


@router.get(
    "/dashboard",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Finance dashboard (single-currency)",
    description="Returns revenue KPIs (MRR/ARR), collections, outstanding, DSO, and invoice status counts. "
    "Requires a single currency; if data contains multiple currencies, pass ?currency=.",
)
@cached("finance-dashboard", ttl=CACHE_TTL["short"])
async def get_finance_dashboard(
    currency: Optional[str] = Query(
        default=None, description="Currency code (required if multiple currencies exist)"
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Finance dashboard with key revenue and collection metrics."""
    try:
        service = FinanceService(db)
        dashboard = service.get_dashboard(currency=currency)

        return {
            "revenue": {
                "mrr": dashboard.revenue.mrr,
                "arr": dashboard.revenue.arr,
                "active_subscriptions": dashboard.revenue.active_subscriptions,
            },
            "collections": {
                "last_30_days": dashboard.collections.collections_30d,
                "invoiced_30_days": dashboard.collections.invoiced_30d,
                "collection_rate": dashboard.collections.collection_rate,
            },
            "outstanding": {
                "total": dashboard.collections.outstanding_total,
                "overdue": dashboard.collections.outstanding_overdue,
            },
            "metrics": {
                "dso": dashboard.collections.dso,
            },
            "invoices_by_status": {
                status: {"count": summary.count, "total": summary.total}
                for status, summary in dashboard.invoices_by_status.items()
            },
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# =============================================================================
# NOTE: Invoice, Payment, and Credit Note CRUD endpoints have been removed.
# Use the accounting module instead:
#   - GET /api/v1/accounting/invoices
#   - GET /api/v1/accounting/ar-payments
#   - GET /api/v1/accounting/notes
# The accounting module is the single source of truth for this data.
# =============================================================================


# =============================================================================
# ANALYTICS
# =============================================================================


@router.get(
    "/analytics/revenue-trend",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Revenue trend (month/week) - single currency",
)
async def get_revenue_trend(
    months: int = Query(default=12, le=36, description="Fallback window if start/end not provided"),
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    interval: str = Query(default="month", description="Aggregation interval: month or week"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue trend from completed payments (single-currency)."""
    try:
        service = FinanceService(db)

        # Parse dates
        start_dt = service._parse_iso_utc(start_date, "start_date")
        end_dt = service._parse_iso_utc(end_date, "end_date")

        result = service.get_revenue_trend(
            start_date=start_dt,
            end_date=end_dt,
            interval=interval,
            currency=currency,
            months=months,
        )

        return {
            "meta": {
                "interval": result.interval,
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "currency": result.currency,
            },
            "data": [
                {
                    "year": r.year,
                    "month": r.month,
                    "period": r.period,
                    "period_start": r.period_start.isoformat() if r.period_start else None,
                    "period_end": r.period_end.isoformat() if r.period_end else None,
                    "revenue": r.revenue,
                    "payment_count": r.payment_count,
                }
                for r in result.data
            ],
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/analytics/collections", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-collections", ttl=CACHE_TTL["medium"])
async def get_collections_analytics(
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get collection analytics including payment methods, timing, and daily totals (single-currency)."""
    try:
        service = FinanceService(db)

        # Parse dates
        start_dt = service._parse_iso_utc(start_date, "start_date")
        end_dt = service._parse_iso_utc(end_date, "end_date")

        result = service.get_collections_analytics(
            start_date=start_dt,
            end_date=end_dt,
            currency=currency,
        )

        return {
            "meta": {
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "currency": result.currency,
            },
            "by_method": [
                {
                    "method": m.method,
                    "count": m.count,
                    "total": m.total,
                }
                for m in result.by_method
            ],
            "payment_timing": {
                "early": result.payment_timing.early,
                "on_time": result.payment_timing.on_time,
                "late": result.payment_timing.late,
                "total": result.payment_timing.total,
            },
            "daily_totals": [
                {"date": d.date, "total": d.total} for d in result.daily_totals
            ],
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/analytics/aging", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-aging", ttl=CACHE_TTL["short"])
async def get_invoice_aging(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoice aging analysis by bucket."""
    try:
        service = FinanceService(db)
        result = service.get_invoice_aging_analysis(currency=currency)

        return {
            "buckets": [
                {
                    "bucket": b.bucket,
                    "count": b.count,
                    "outstanding": b.outstanding,
                }
                for b in result.buckets
            ],
            "summary": {
                "total_outstanding": result.total_outstanding,
                "at_risk": result.at_risk,
                "at_risk_percent": result.at_risk_percent,
                "total_invoices": result.total_invoices,
            },
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/analytics/by-currency", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_by_currency(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue breakdown by currency."""
    service = FinanceService(db)
    result = service.get_revenue_by_currency()

    return {
        "by_currency": [
            {
                "currency": r.currency,
                "mrr": r.mrr,
                "arr": r.arr,
                "subscription_count": r.subscription_count,
                "outstanding": r.outstanding,
            }
            for r in result
        ],
    }


# =============================================================================
# INSIGHTS
# =============================================================================


@router.get("/insights/payment-behavior", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-payment-behavior", ttl=CACHE_TTL["medium"])
async def get_payment_behavior_insights(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze customer payment behavior patterns."""
    try:
        service = FinanceService(db)
        result = service.analyze_payment_behavior(currency=currency)

        return {
            "summary": {
                "customers_with_payments": result.summary.customers_with_payments,
                "customers_with_overdue": result.summary.customers_with_overdue,
                "avg_late_payment_delay_days": result.summary.avg_late_payment_delay_days,
                "late_payments_percent": result.summary.late_payments_percent,
            },
            "recommendations": result.recommendations,
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/insights/forecasts", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-forecasts", ttl=CACHE_TTL["medium"])
async def get_revenue_forecasts(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simple revenue projections based on current MRR and trends."""
    try:
        service = FinanceService(db)
        result = service.forecast_revenue(currency=currency)

        return {
            "currency": result.currency,
            "current": {
                "mrr": result.current_mrr,
                "arr": result.current_arr,
            },
            "activity_30d": {
                "new_subscriptions": result.new_subscriptions_30d,
            },
            "projections": {
                "month_1": result.month_1_projection,
                "month_2": result.month_2_projection,
                "month_3": result.month_3_projection,
                "quarter_total": result.quarter_total_projection,
            },
            "assumptions": result.assumptions,
            "notes": "Projections assume current MRR remains stable. Adjust for expected growth/churn.",
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
