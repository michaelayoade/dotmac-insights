"""
Dashboard Endpoints - Sales dashboard with KPIs, metrics, and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup,
    Territory, SalesPerson
)
from app.api.sales_pkg.common import _resolve_currency_or_raise
from app.services.sales.dashboard import SalesDashboardService
from app.services.sales.dashboard_types import SalesDashboardFilters

router = APIRouter()


def get_dashboard_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> SalesDashboardService:
    """Create a SalesDashboardService instance for dependency injection."""
    return SalesDashboardService(db, principal)

# =============================================================================
# DASHBOARD
# =============================================================================

class RevenueTrendPoint(BaseModel):
    year: int
    month: int
    period: str
    revenue: float
    payment_count: int

@router.get(
    "/dashboard",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Finance dashboard (single-currency)",
    description="Returns revenue KPIs (MRR/ARR), collections, outstanding, DSO, and invoice status counts. "
                "Requires a single currency; if data contains multiple currencies, pass ?currency=.",
)
@cached("finance-dashboard", ttl=CACHE_TTL["short"])
async def get_finance_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code (required if multiple currencies exist)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Finance dashboard with key revenue and collection metrics.
    Enforces a single currency to avoid mixing figures.
    """
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency)
    # MRR calculation from active subscriptions
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    mrr_query = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if currency:
        mrr_query = mrr_query.filter(Subscription.currency == currency)

    mrr = float(mrr_query.scalar() or 0)
    arr = mrr * 12

    active_subscriptions = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *( [Subscription.currency == currency] if currency else [] ),
    ).scalar() or 0

    # Invoice summary
    invoice_summary_query = db.query(
        Invoice.status,
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount).label("total")
    )
    if currency:
        invoice_summary_query = invoice_summary_query.filter(Invoice.currency == currency)
    invoice_summary = invoice_summary_query.group_by(Invoice.status).all()

    invoice_by_status = {
        row.status.value: {"count": row.count, "total": float(row.total or 0)}
        for row in invoice_summary
    }

    # Outstanding balance
    outstanding_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    overdue_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    if currency:
        outstanding_query = outstanding_query.filter(Invoice.currency == currency)
        overdue_query = overdue_query.filter(Invoice.currency == currency)

    outstanding = outstanding_query.scalar() or 0
    overdue_amount = overdue_query.scalar() or 0

    # Collections last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    collections_30d_query = db.query(func.sum(Payment.amount)).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= thirty_days_ago
    )
    invoiced_30d_query = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= thirty_days_ago
    )
    if currency:
        collections_30d_query = collections_30d_query.filter(Payment.currency == currency)
        invoiced_30d_query = invoiced_30d_query.filter(Invoice.currency == currency)

    collections_30d = collections_30d_query.scalar() or 0
    invoiced_30d = invoiced_30d_query.scalar() or 0

    collection_rate = round(float(collections_30d) / float(invoiced_30d) * 100, 1) if invoiced_30d else 0

    # DSO (Days Sales Outstanding) - simplified calculation
    avg_daily_revenue = float(collections_30d) / 30 if collections_30d else 0
    dso = round(float(outstanding) / avg_daily_revenue, 1) if avg_daily_revenue > 0 else 0

    return {
        "revenue": {
            "mrr": mrr,
            "arr": arr,
            "active_subscriptions": active_subscriptions,
        },
        "collections": {
            "last_30_days": float(collections_30d),
            "invoiced_30_days": float(invoiced_30d),
            "collection_rate": collection_rate,
        },
        "outstanding": {
            "total": float(outstanding),
            "overdue": float(overdue_amount),
        },
        "metrics": {
            "dso": dso,
        },
        "invoices_by_status": invoice_by_status,
    }


# =============================================================================
# DATA ENDPOINTS
# =============================================================================


# =============================================================================
# SALES DASHBOARD SERVICE ENDPOINTS
# =============================================================================

class SalesKPICardResponse(BaseModel):
    """Single KPI card for sales dashboard."""

    key: str
    title: str
    value: str
    formatted_value: str
    trend: Optional[float]
    trend_direction: Optional[str]
    comparison_period: Optional[str]
    icon: Optional[str]
    color: Optional[str]


class SalesDashboardSummaryResponse(BaseModel):
    """Complete Sales dashboard summary."""

    total_quotes: int
    open_quotes: int
    open_quote_value: float
    quote_conversion_rate: float
    total_orders: int
    pending_orders: int
    pending_order_value: float
    completed_orders: int
    total_revenue_this_period: float
    avg_order_value: float
    items_sold: int
    fulfillment_rate: float
    billing_rate: float
    kpi_cards: List[SalesKPICardResponse]


class OrderMetricsResponse(BaseModel):
    """Sales order metrics for dashboard."""

    total_orders: int
    by_status: dict
    by_status_value: dict
    orders_this_week: int
    orders_this_month: int
    avg_processing_days: Optional[float]
    on_time_rate: float


class QuoteSummaryResponse(BaseModel):
    """Quotation summary for dashboard."""

    total_quotes: int
    open_quotes: int
    ordered_quotes: int
    lost_quotes: int
    expired_quotes: int
    open_value: float
    ordered_value: float
    conversion_rate: float
    avg_days_to_convert: Optional[float]
    expiring_soon: int


class AgingChartResponse(BaseModel):
    """Aging analysis chart data."""

    entity_type: str
    buckets: List[dict]
    total_count: int
    total_value: float
    avg_age_days: float


class FulfillmentStatusResponse(BaseModel):
    """Order fulfillment status breakdown."""

    total_orders: int
    not_delivered: int
    partially_delivered: int
    fully_delivered: int
    not_billed: int
    partially_billed: int
    fully_billed: int
    delivery_progress: float
    billing_progress: float
    pending_delivery: List[dict]
    pending_billing: List[dict]


class DeliveryTimelineResponse(BaseModel):
    """Delivery timeline for upcoming deliveries."""

    upcoming_deliveries: List[dict]
    overdue_deliveries: List[dict]
    today_count: int
    this_week_count: int
    this_month_count: int


class ProductRevenueResponse(BaseModel):
    """Revenue breakdown by product/item."""

    rank: int
    item_id: int
    item_code: str
    item_name: str
    item_group: Optional[str]
    quantity_sold: float
    revenue: float
    order_count: int
    percentage_of_total: float


class CustomerRevenueResponse(BaseModel):
    """Revenue breakdown by customer."""

    rank: int
    party_id: int
    party_name: str
    order_count: int
    revenue: float
    avg_order_value: float
    percentage_of_total: float
    last_order_date: Optional[date]


class SalesMonthlyComparisonResponse(BaseModel):
    """Month-over-month sales comparison."""

    current_month: str
    current_orders: int
    current_revenue: float
    current_avg_value: float
    previous_month: str
    previous_orders: int
    previous_revenue: float
    previous_avg_value: float
    order_change: int
    order_change_percent: float
    revenue_change: float
    revenue_change_percent: float


class RevenueChartResponse(BaseModel):
    """Revenue chart data over time."""

    period_type: str
    data_points: List[dict]
    total_revenue: float
    avg_revenue: float
    trend_direction: str
    trend_percentage: float


def _kpi_to_response(kpi) -> SalesKPICardResponse:
    """Convert SalesKPICard to response."""
    return SalesKPICardResponse(
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


@router.get("/sales-summary", response_model=SalesDashboardSummaryResponse)
async def get_sales_dashboard_summary(
    period: str = Query("month", description="Period: day, week, month, quarter, year"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sales_person_id: Optional[int] = None,
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get complete sales dashboard summary with KPIs."""
    filters = SalesDashboardFilters(
        period=period,
        start_date=start_date,
        end_date=end_date,
        sales_person_id=sales_person_id,
    )
    summary = service.get_dashboard_summary(filters)

    return SalesDashboardSummaryResponse(
        total_quotes=summary.total_quotes,
        open_quotes=summary.open_quotes,
        open_quote_value=float(summary.open_quote_value),
        quote_conversion_rate=summary.quote_conversion_rate,
        total_orders=summary.total_orders,
        pending_orders=summary.pending_orders,
        pending_order_value=float(summary.pending_order_value),
        completed_orders=summary.completed_orders,
        total_revenue_this_period=float(summary.total_revenue_this_period),
        avg_order_value=float(summary.avg_order_value),
        items_sold=summary.items_sold,
        fulfillment_rate=summary.fulfillment_rate,
        billing_rate=summary.billing_rate,
        kpi_cards=[_kpi_to_response(k) for k in summary.kpi_cards],
    )


@router.get("/order-metrics", response_model=OrderMetricsResponse)
async def get_order_metrics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sales_person_id: Optional[int] = None,
    territory_id: Optional[int] = None,
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get detailed order metrics."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
        sales_person_id=sales_person_id,
        territory_id=territory_id,
    )
    metrics = service.get_order_metrics(filters)

    by_status_value_float = {
        k: float(v) for k, v in metrics.by_status_value.items()
    }

    return OrderMetricsResponse(
        total_orders=metrics.total_orders,
        by_status=metrics.by_status,
        by_status_value=by_status_value_float,
        orders_this_week=metrics.orders_this_week,
        orders_this_month=metrics.orders_this_month,
        avg_processing_days=metrics.avg_processing_days,
        on_time_rate=metrics.on_time_rate,
    )


@router.get("/quote-summary", response_model=QuoteSummaryResponse)
async def get_quote_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get quotation summary for dashboard."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    summary = service.get_quote_summary(filters)

    return QuoteSummaryResponse(
        total_quotes=summary.total_quotes,
        open_quotes=summary.open_quotes,
        ordered_quotes=summary.ordered_quotes,
        lost_quotes=summary.lost_quotes,
        expired_quotes=summary.expired_quotes,
        open_value=float(summary.open_value),
        ordered_value=float(summary.ordered_value),
        conversion_rate=summary.conversion_rate,
        avg_days_to_convert=summary.avg_days_to_convert,
        expiring_soon=summary.expiring_soon,
    )


@router.get("/quote-aging", response_model=AgingChartResponse)
async def get_quote_aging_chart(
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get quote aging chart data."""
    chart = service.get_quote_aging_chart()

    return AgingChartResponse(
        entity_type=chart.entity_type,
        buckets=chart.buckets,
        total_count=chart.total_count,
        total_value=float(chart.total_value),
        avg_age_days=chart.avg_age_days,
    )


@router.get("/fulfillment", response_model=FulfillmentStatusResponse)
async def get_fulfillment_status(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get order fulfillment status breakdown."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    status = service.get_fulfillment_status(filters)

    return FulfillmentStatusResponse(
        total_orders=status.total_orders,
        not_delivered=status.not_delivered,
        partially_delivered=status.partially_delivered,
        fully_delivered=status.fully_delivered,
        not_billed=status.not_billed,
        partially_billed=status.partially_billed,
        fully_billed=status.fully_billed,
        delivery_progress=status.delivery_progress,
        billing_progress=status.billing_progress,
        pending_delivery=status.pending_delivery,
        pending_billing=status.pending_billing,
    )


@router.get("/delivery-timeline", response_model=DeliveryTimelineResponse)
async def get_delivery_timeline(
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get delivery timeline for upcoming deliveries."""
    timeline = service.get_delivery_timeline()

    return DeliveryTimelineResponse(
        upcoming_deliveries=timeline.upcoming_deliveries,
        overdue_deliveries=timeline.overdue_deliveries,
        today_count=timeline.today_count,
        this_week_count=timeline.this_week_count,
        this_month_count=timeline.this_month_count,
    )


@router.get("/top-products", response_model=List[ProductRevenueResponse])
async def get_revenue_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(10, ge=1, le=50),
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get top products by revenue."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    products = service.get_revenue_by_product(filters, limit)

    return [
        ProductRevenueResponse(
            rank=p.rank,
            item_id=p.item_id,
            item_code=p.item_code,
            item_name=p.item_name,
            item_group=p.item_group,
            quantity_sold=float(p.quantity_sold),
            revenue=float(p.revenue),
            order_count=p.order_count,
            percentage_of_total=p.percentage_of_total,
        )
        for p in products
    ]


@router.get("/top-customers", response_model=List[CustomerRevenueResponse])
async def get_revenue_by_customer(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(10, ge=1, le=50),
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get top customers by revenue."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    customers = service.get_revenue_by_customer(filters, limit)

    return [
        CustomerRevenueResponse(
            rank=c.rank,
            party_id=c.party_id,
            party_name=c.party_name,
            order_count=c.order_count,
            revenue=float(c.revenue),
            avg_order_value=float(c.avg_order_value),
            percentage_of_total=c.percentage_of_total,
            last_order_date=c.last_order_date,
        )
        for c in customers
    ]


@router.get("/monthly-comparison", response_model=SalesMonthlyComparisonResponse)
async def get_monthly_comparison(
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get month-over-month sales comparison."""
    comparison = service.get_monthly_comparison()

    return SalesMonthlyComparisonResponse(
        current_month=comparison.current_month,
        current_orders=comparison.current_orders,
        current_revenue=float(comparison.current_revenue),
        current_avg_value=float(comparison.current_avg_value),
        previous_month=comparison.previous_month,
        previous_orders=comparison.previous_orders,
        previous_revenue=float(comparison.previous_revenue),
        previous_avg_value=float(comparison.previous_avg_value),
        order_change=comparison.order_change,
        order_change_percent=comparison.order_change_percent,
        revenue_change=float(comparison.revenue_change),
        revenue_change_percent=comparison.revenue_change_percent,
    )


@router.get("/revenue-chart", response_model=RevenueChartResponse)
async def get_revenue_chart(
    period: str = Query("monthly", description="Grouping: daily, weekly, monthly"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: SalesDashboardService = Depends(get_dashboard_service),
):
    """Get revenue chart data over time."""
    filters = SalesDashboardFilters(
        start_date=start_date,
        end_date=end_date,
    )
    chart = service.get_revenue_chart(filters, period=period)

    return RevenueChartResponse(
        period_type=chart.period_type,
        data_points=chart.data_points,
        total_revenue=float(chart.total_revenue),
        avg_revenue=float(chart.avg_revenue),
        trend_direction=chart.trend_direction,
        trend_percentage=chart.trend_percentage,
    )
