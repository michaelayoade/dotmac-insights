from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case, and_, or_, desc, asc, exists, text
from typing import Dict, Any, List, Optional, cast
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.config import settings
from app.models.party import PartyRole, CustomerAccount
from app.models.router import Router
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.pop import Pop
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus, Territory
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.expense import Expense, ExpenseStatus
from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier, CostCenter
from app.models.employee import Employee, EmploymentStatus
from app.models.network_monitor import NetworkMonitor, MonitorState
from app.models.ipv4_network import IPv4Network
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.services.analytics.service import AnalyticsService
from app.services.analytics.export_service import AnalyticsExportService, AnalyticsExportError, WEASYPRINT_AVAILABLE
from app.services.field_service import FieldServiceAnalyticsService, AnalyticsFilters
from app.services.hr import HRAnalyticsService
from app.services.insights import InsightsService

router = APIRouter()


def _apply_statement_timeout(db: Session) -> None:
    """Apply per-request statement timeout for Postgres connections."""
    timeout_ms = getattr(settings, "analytics_statement_timeout_ms", None)
    if not timeout_ms or not db.bind or db.bind.dialect.name != "postgresql":
        return
    try:
        db.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": timeout_ms})
    except Exception:
        db.rollback()
        return


def get_db_with_timeout(db: Session = Depends(get_db)) -> Session:
    """Dependency that applies statement timeout for analytics-heavy queries."""
    _apply_statement_timeout(db)
    return db


def get_analytics_service(
    db: Session = Depends(get_db_with_timeout),
    principal: Principal = Depends(get_current_principal),
) -> AnalyticsService:
    """Dependency for analytics service with statement timeout and principal."""
    return AnalyticsService(db, principal)


def _export_headers(base_filename: str, extension: str) -> Dict[str, str]:
    """Build Content-Disposition headers for streamed exports."""
    filename = base_filename or "analytics-export"
    filename = filename.replace(" ", "_").lower()
    return {
        "Content-Disposition": f"attachment; filename={filename}.{extension}",
        "Cache-Control": "no-store",
    }


def _stream_export(content: bytes, media_type: str, base_filename: str, extension: str) -> StreamingResponse:
    """Create a streaming response for file export."""
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers=_export_headers(base_filename, extension),
    )


def _parse_date_param(date_str: Optional[str], field: str) -> Optional[datetime]:
    """Parse ISO date string to datetime or raise HTTP 400 for invalid input."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {date_str}")


def _get_active_currencies(db: Session, filters: Optional[List[Any]] = None) -> set[str]:
    """Return distinct currencies for active subscriptions after filters."""
    query = (
        db.query(Subscription.currency)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    if filters:
        for f in filters:
            query = query.filter(f)
    return {row.currency for row in query.distinct().all() if row.currency}


def _resolve_currency(db: Session, filters: List, currency: Optional[str]) -> Optional[str]:
    """
    Ensure MRR calculations do not mix currencies.
    - If caller supplies currency, use it.
    - If multiple currencies exist after filters and none supplied, raise 400.
    """
    currencies = _get_active_currencies(db, filters)

    if currency:
        return currency

    if len(currencies) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple subscription currencies detected. Provide the 'currency' query parameter to choose one.",
        )

    return currencies.pop() if currencies else None


def calculate_mrr(db: Session, filters: Optional[List[Any]] = None, currency: Optional[str] = None) -> float:
    """
    Calculate Monthly Recurring Revenue normalized by billing cycle and currency.

    - Monthly plans: price as-is
    - Quarterly plans: price / 3
    - Yearly plans: price / 12
    - If multiple currencies exist and none provided, HTTP 400 is raised.
    """
    filters = filters or []
    resolved_currency = _resolve_currency(db, filters, currency)

    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price,
    )

    query = (
        db.query(func.sum(mrr_case))
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    if resolved_currency:
        query = query.filter(Subscription.currency == resolved_currency)

    for f in filters:
        query = query.filter(f)

    result = query.scalar()
    return float(result or 0)


@cached("overview", ttl=CACHE_TTL["short"], include_principal=True)
async def _get_overview_impl(currency: Optional[str], db: Session, principal: Principal) -> Dict[str, Any]:
    """Implementation of overview metrics (cached)."""
    # Customer counts
    total_customers = db.query(CustomerAccount).count()
    active_customers = db.query(CustomerAccount).filter(CustomerAccount.status == "active").count()
    churned_customers = db.query(CustomerAccount).filter(CustomerAccount.status == "cancelled").count()

    resolved_currency = _resolve_currency(db, [], currency)

    # Revenue (MRR from active subscriptions - properly normalized by billing cycle)
    mrr = calculate_mrr(db, currency=resolved_currency)

    # Outstanding balance
    outstanding_result = (
        db.query(func.sum(Invoice.balance))
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
        .scalar()
    )
    outstanding = float(outstanding_result or 0)

    # Open support tickets
    open_tickets = db.query(Conversation).filter(
        Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING])
    ).count()

    # Overdue invoices
    overdue_invoices = db.query(Invoice).filter(Invoice.status == InvoiceStatus.OVERDUE).count()

    # POP count
    pop_count = db.query(Pop).filter(Pop.is_active.is_(True)).count()

    return {
        "customers": {
            "total": total_customers,
            "active": active_customers,
            "churned": churned_customers,
            "churn_rate": round(churned_customers / total_customers * 100, 2) if total_customers > 0 else 0,
        },
        "revenue": {
            "mrr": mrr,
            "outstanding": outstanding,
            "overdue_invoices": overdue_invoices,
            "currency": resolved_currency,
        },
        "support": {
            "open_tickets": open_tickets,
        },
        "operations": {
            "pop_count": pop_count,
        },
    }


@router.get("/overview", dependencies=[Depends(Require("analytics:read"))])
async def get_overview(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get high-level overview metrics."""
    return await service.get_overview(currency)


@router.get("/revenue", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_summary(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    months: int = Query(default=12, le=36),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Revenue summary alias endpoint (avoids 404)."""
    return await service.get_revenue_summary(currency=currency, months=months)


@router.get("/revenue/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[Dict[str, Any]]:
    """Get monthly revenue trend from payments."""
    return await service.get_revenue_trend(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/churn/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_churn_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get monthly churn trend with churn rates based on subscription expiration (no active renewal)."""
    return await service.get_churn_trend(months=months, start_date=start_date, end_date=end_date)


@cached("pop_performance", ttl=CACHE_TTL["long"], include_principal=True)
async def _get_pop_performance_impl(currency: Optional[str], db: Session, principal: Principal) -> List[Dict[str, Any]]:
    """Implementation of POP performance metrics (cached - single aggregated query)."""
    # Guard against mixed currencies globally unless caller specifies which to use
    resolved_currency = _resolve_currency(db, [], currency)

    # MRR normalized by billing cycle
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price,
    )

    # Build currency filter for MRR
    mrr_currency_filter = Subscription.currency == resolved_currency if resolved_currency else Subscription.id.isnot(None)

    party_pop = (
        db.query(
            Subscription.party_id.label("party_id"),
            func.min(Router.pop_id).label("pop_id"),
        )
        .join(Router, Subscription.router_id == Router.id)
        .filter(Router.pop_id.isnot(None))
        .group_by(Subscription.party_id)
        .subquery()
    )

    active_party_pop = (
        db.query(
            Subscription.party_id.label("party_id"),
            func.min(Router.pop_id).label("pop_id"),
        )
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Router.pop_id.isnot(None),
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .group_by(Subscription.party_id)
        .subquery()
    )

    pop_metrics = (
        db.query(
            Pop.id,
            Pop.name,
            Pop.code,
            Pop.city,
            func.count(func.distinct(party_pop.c.party_id)).label("total_customers"),
            func.count(func.distinct(active_party_pop.c.party_id)).label("active_customers"),
        )
        .outerjoin(party_pop, party_pop.c.pop_id == Pop.id)
        .outerjoin(active_party_pop, active_party_pop.c.pop_id == Pop.id)
        .filter(Pop.is_active.is_(True))
        .group_by(Pop.id, Pop.name, Pop.code, Pop.city)
        .all()
    )

    # MRR by POP (separate query to handle currency filtering properly)
    mrr_by_pop = (
        db.query(
            Router.pop_id,
            func.sum(mrr_case).label("mrr"),
        )
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            mrr_currency_filter,
        )
        .group_by(Router.pop_id)
        .all()
    )
    mrr_map = {row.pop_id: float(row.mrr or 0) for row in mrr_by_pop}

    # Open tickets by POP
    tickets_by_pop = (
        db.query(
            party_pop.c.pop_id,
            func.count(Conversation.id).label("open_tickets"),
        )
        .join(CustomerAccount, CustomerAccount.id == Conversation.customer_account_id)
        .join(party_pop, party_pop.c.party_id == CustomerAccount.party_id)
        .filter(Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]))
        .group_by(party_pop.c.pop_id)
        .all()
    )
    tickets_map = {row.pop_id: row.open_tickets for row in tickets_by_pop}

    # Outstanding by POP
    outstanding_by_pop = (
        db.query(
            party_pop.c.pop_id,
            func.sum(Invoice.balance).label("outstanding"),
        )
        .join(CustomerAccount, CustomerAccount.id == Invoice.customer_account_id)
        .join(party_pop, party_pop.c.party_id == CustomerAccount.party_id)
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]))
        .group_by(party_pop.c.pop_id)
        .all()
    )
    outstanding_map = {row.pop_id: float(row.outstanding or 0) for row in outstanding_by_pop}

    results = []
    for pop in pop_metrics:
        total = pop.total_customers or 0
        churned = max(total - (pop.active_customers or 0), 0)
        churn_rate = (churned / total * 100) if total > 0 else 0

        results.append({
            "id": pop.id,
            "name": pop.name,
            "code": pop.code,
            "city": pop.city,
            "total_customers": total,
            "active_customers": pop.active_customers or 0,
            "churned_customers": churned,
            "churn_rate": round(churn_rate, 2),
            "mrr": mrr_map.get(pop.id, 0.0),
            "open_tickets": tickets_map.get(pop.id, 0),
            "outstanding": outstanding_map.get(pop.id, 0.0),
            "currency": resolved_currency,
        })

    # Sort by MRR descending
    results.sort(key=lambda x: cast(float, x.get("mrr", 0.0)), reverse=True)

    return results


@router.get("/pop/performance", dependencies=[Depends(Require("analytics:read"))])
async def get_pop_performance(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db_with_timeout),
    principal: Principal = Depends(get_current_principal),
) -> List[Dict[str, Any]]:
    """Get performance metrics by POP."""
    return cast(List[Dict[str, Any]], await _get_pop_performance_impl(currency, db, principal))


@router.get("/customers", dependencies=[Depends(Require("analytics:read"))])
async def get_customer_summary(
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Customer summary alias endpoint (avoids 404)."""
    return await service.get_customer_summary()


@router.get("/support/metrics", dependencies=[Depends(Require("analytics:read"))])
async def get_support_metrics(
    days: int = Query(default=30, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get support/ticket metrics."""
    return await service.get_support_metrics(days=days)


@router.get("/invoices/aging", dependencies=[Depends(Require("analytics:read"))])
async def get_invoice_aging(
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get invoice aging report using SQL-based bucket calculation."""
    return await service.get_invoice_aging()


@router.get("/customers/by-plan", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_plan(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[Dict[str, Any]]:
    """Get customer distribution by plan."""
    return await service.get_customers_by_plan(currency=currency)


# ==============================================================================
# Revenue Quality Analytics
# ==============================================================================


@cached("dso", ttl=CACHE_TTL["long"], include_principal=True)
async def _get_dso_impl(months: int, db: Session, principal: Principal) -> Dict[str, Any]:
    """Implementation of DSO calculation (cached - expensive monthly iteration)."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=months * 30)

    results = []

    for i in range(months):
        period_start = start_date + timedelta(days=i * 30)
        period_end = period_start + timedelta(days=30)

        # Total invoiced in period
        invoiced = (
            db.query(func.sum(Invoice.total_amount))
            .filter(
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date < period_end,
            )
            .scalar()
        ) or Decimal("0")

        # Average receivables (outstanding balance at period end)
        avg_receivables = (
            db.query(func.sum(Invoice.balance))
            .filter(
                Invoice.invoice_date < period_end,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
            )
            .scalar()
        ) or Decimal("0")

        # DSO = (Average Receivables / Revenue) * Days in Period
        dso = float((avg_receivables / invoiced) * 30) if invoiced > 0 else 0

        results.append({
            "year": period_start.year,
            "month": period_start.month,
            "period": f"{period_start.year}-{period_start.month:02d}",
            "dso": round(dso, 1),
            "invoiced": float(invoiced),
            "outstanding": float(avg_receivables),
        })

    dso_values = [float(cast(Any, r["dso"])) for r in results]
    return {
        "trend": results,
        "current_dso": dso_values[-1] if dso_values else 0,
        "average_dso": round(sum(dso_values) / len(dso_values), 1) if dso_values else 0,
    }


@router.get("/revenue/dso", dependencies=[Depends(Require("analytics:read"))])
async def get_days_sales_outstanding(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Calculate Days Sales Outstanding (DSO) trend - measures collection efficiency."""
    return await service.get_dso(months=months, start_date=start_date, end_date=end_date)


@router.get("/revenue/by-territory", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_by_territory(
    months: int = Query(default=12, le=24),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[Dict[str, Any]]:
    """Get MRR and customer distribution by territory/region."""
    return await service.get_revenue_by_territory(months=months)


@router.get("/revenue/cohort", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_cohort(
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Analyze revenue by customer signup cohort."""
    return await service.get_revenue_cohort()


# ==============================================================================
# Collections & Risk Analytics
# ==============================================================================


@router.get("/collections/aging-by-segment", dependencies=[Depends(Require("analytics:read"))])
async def get_aging_by_segment(db: Session = Depends(get_db_with_timeout)) -> Dict[str, Any]:
    """Get invoice aging breakdown by customer segment (type)."""
    segments: Dict[str, Dict[str, Any]] = {}

    # Get all unpaid invoices with customer info
    segment_expr = func.coalesce(PartyRole.metadata_["customer_type"].astext, "Unknown")
    unpaid = (
        db.query(Invoice, segment_expr)
        .join(CustomerAccount, CustomerAccount.id == Invoice.customer_account_id)
        .outerjoin(
            PartyRole,
            and_(PartyRole.party_id == CustomerAccount.party_id, PartyRole.role == "customer"),
        )
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
        .all()
    )

    for inv, customer_type in unpaid:
        segment = customer_type or "Unknown"
        if segment not in segments:
            segments[segment] = {
                "current": {"count": 0, "amount": 0.0},
                "1_30_days": {"count": 0, "amount": 0.0},
                "31_60_days": {"count": 0, "amount": 0.0},
                "61_90_days": {"count": 0, "amount": 0.0},
                "over_90_days": {"count": 0, "amount": 0.0},
                "total": {"count": 0, "amount": 0.0},
            }

        balance = float(inv.balance or inv.total_amount or 0)
        days = inv.days_overdue

        segments[segment]["total"]["count"] += 1
        segments[segment]["total"]["amount"] += balance

        if days == 0:
            bucket = "current"
        elif days <= 30:
            bucket = "1_30_days"
        elif days <= 60:
            bucket = "31_60_days"
        elif days <= 90:
            bucket = "61_90_days"
        else:
            bucket = "over_90_days"

        segments[segment][bucket]["count"] += 1
        segments[segment][bucket]["amount"] += balance

    return {
        "by_segment": segments,
        "total_outstanding": sum(s["total"]["amount"] for s in segments.values()),
    }


@router.get("/collections/credit-notes", dependencies=[Depends(Require("analytics:read"))])
async def get_credit_notes_summary(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db_with_timeout),
) -> Dict[str, Any]:
    """Get credit notes issued trend and summary."""
    start_date = datetime.now(timezone.utc) - timedelta(days=months * 30)

    # Monthly trend
    trend = (
        db.query(
            extract("year", CreditNote.issue_date).label("year"),
            extract("month", CreditNote.issue_date).label("month"),
            func.count(CreditNote.id).label("count"),
            func.sum(CreditNote.amount).label("total"),
        )
        .filter(CreditNote.issue_date >= start_date)
        .group_by(
            extract("year", CreditNote.issue_date),
            extract("month", CreditNote.issue_date),
        )
        .order_by(
            extract("year", CreditNote.issue_date),
            extract("month", CreditNote.issue_date),
        )
        .all()
    )

    # Summary by status
    by_status = (
        db.query(
            CreditNote.status,
            func.count(CreditNote.id).label("count"),
            func.sum(CreditNote.amount).label("total"),
        )
        .group_by(CreditNote.status)
        .all()
    )

    return {
        "trend": [
            {
                "year": int(t.year),
                "month": int(t.month),
                "period": f"{int(t.year)}-{int(t.month):02d}",
                "count": t.count,
                "total": float(t.total or 0),
            }
            for t in trend
        ],
        "by_status": {s.status.value: {"count": s.count, "total": float(s.total or 0)} for s in by_status},
        "total_issued": sum(float(t.total or 0) for t in trend),
    }


# ==============================================================================
# Sales Pipeline Analytics
# ==============================================================================


@cached("sales_pipeline", ttl=CACHE_TTL["medium"], include_principal=True)
async def _get_sales_pipeline_impl(db: Session, principal: Principal) -> Dict[str, Any]:
    """Implementation of sales pipeline metrics (cached)."""
    # Quotations summary
    quotations = (
        db.query(
            Quotation.status,
            func.count(Quotation.id).label("count"),
            func.sum(Quotation.grand_total).label("value"),
        )
        .group_by(Quotation.status)
        .all()
    )

    # Sales Orders summary
    orders = (
        db.query(
            SalesOrder.status,
            func.count(SalesOrder.id).label("count"),
            func.sum(SalesOrder.grand_total).label("value"),
        )
        .group_by(SalesOrder.status)
        .all()
    )

    # Calculate conversion rates
    total_quotations = sum(int(getattr(q, "count", 0) or 0) for q in quotations)
    ordered_quotations = sum(int(getattr(q, "count", 0) or 0) for q in quotations if q.status == QuotationStatus.ORDERED)
    completed_orders = sum(int(getattr(o, "count", 0) or 0) for o in orders if o.status == SalesOrderStatus.COMPLETED)

    return {
        "quotations": {
            "by_status": {q.status.value: {"count": q.count, "value": float(q.value or 0)} for q in quotations},
            "total": total_quotations,
            "total_value": sum(float(q.value or 0) for q in quotations),
        },
        "orders": {
            "by_status": {o.status.value: {"count": o.count, "value": float(o.value or 0)} for o in orders},
            "total": sum(o.count for o in orders),
            "total_value": sum(float(o.value or 0) for o in orders),
        },
        "conversion": {
            "quotation_to_order_rate": round(ordered_quotations / total_quotations * 100, 1) if total_quotations > 0 else 0,
            "orders_completed": completed_orders,
        },
    }


@router.get("/sales/pipeline", dependencies=[Depends(Require("analytics:read"))])
async def get_sales_pipeline(
    db: Session = Depends(get_db_with_timeout),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get sales pipeline funnel: Quotations → Orders → Invoices."""
    return cast(Dict[str, Any], await _get_sales_pipeline_impl(db, principal))


@router.get("/sales/quotation-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_quotation_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db_with_timeout),
) -> List[Dict[str, Any]]:
    """Get monthly quotation creation and conversion trend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=months * 30)

    trend = (
        db.query(
            extract("year", Quotation.transaction_date).label("year"),
            extract("month", Quotation.transaction_date).label("month"),
            func.count(Quotation.id).label("total"),
            func.sum(case((Quotation.status == QuotationStatus.ORDERED, 1), else_=0)).label("converted"),
            func.sum(case((Quotation.status == QuotationStatus.LOST, 1), else_=0)).label("lost"),
            func.sum(Quotation.grand_total).label("value"),
        )
        .filter(Quotation.transaction_date >= start_dt, Quotation.transaction_date <= end_dt)
        .group_by(
            extract("year", Quotation.transaction_date),
            extract("month", Quotation.transaction_date),
        )
        .order_by(
            extract("year", Quotation.transaction_date),
            extract("month", Quotation.transaction_date),
        )
        .all()
    )

    return [
        {
            "year": int(t.year),
            "month": int(t.month),
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "total": t.total,
            "converted": t.converted,
            "lost": t.lost,
            "value": float(t.value or 0),
            "conversion_rate": round(t.converted / t.total * 100, 1) if t.total > 0 else 0,
        }
        for t in trend
    ]


# ==============================================================================
# Support/SLA Analytics
# ==============================================================================


@cached("sla_attainment", ttl=CACHE_TTL["medium"], include_principal=True)
async def _get_sla_attainment_impl(days: int, db: Session, principal: Principal) -> Dict[str, Any]:
    """Implementation of SLA attainment metrics (cached - SQL aggregation)."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Calculate resolution hours in SQL (time_to_resolution_hours is a Python property)
    resolution_hours_expr = func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600

    # Single aggregated query for SLA metrics
    sla_metrics = (
        db.query(
            func.count(Ticket.id).label("total"),
            func.sum(case(
                (and_(Ticket.resolution_by.isnot(None), Ticket.resolution_date.isnot(None), Ticket.resolution_date <= Ticket.resolution_by), 1),
                else_=0
            )).label("met_sla"),
            func.sum(case(
                (and_(Ticket.resolution_by.isnot(None), Ticket.resolution_date.isnot(None), Ticket.resolution_date > Ticket.resolution_by), 1),
                else_=0
            )).label("breached_sla"),
            func.avg(resolution_hours_expr).filter(
                Ticket.resolution_date.isnot(None),
                Ticket.opening_date.isnot(None)
            ).label("avg_resolution_hours"),
            func.avg(
                func.extract('epoch', Ticket.first_responded_on - Ticket.opening_date) / 3600
            ).filter(
                Ticket.first_responded_on.isnot(None),
                Ticket.opening_date.isnot(None)
            ).label("avg_response_hours"),
        )
        .filter(Ticket.created_at >= start_date)
        .first()
    )

    # By priority breakdown
    by_priority = (
        db.query(
            Ticket.priority,
            func.count(Ticket.id).label("count"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(Ticket.priority)
        .all()
    )

    total = sla_metrics.total or 0
    met = sla_metrics.met_sla or 0
    breached = sla_metrics.breached_sla or 0
    sla_total = met + breached

    return {
        "period_days": days,
        "total_tickets": total,
        "sla_attainment": {
            "met": met,
            "breached": breached,
            "rate": round(met / sla_total * 100, 1) if sla_total > 0 else 0,
        },
        "avg_response_hours": round(float(sla_metrics.avg_response_hours or 0), 2),
        "avg_resolution_hours": round(float(sla_metrics.avg_resolution_hours or 0), 2),
        "by_priority": {p.priority.value: p.count for p in by_priority if p.priority},
    }


@router.get("/support/sla-attainment", dependencies=[Depends(Require("analytics:read"))])
async def get_sla_attainment(
    days: int = Query(default=30, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get SLA attainment metrics for tickets."""
    return await service.get_sla_attainment(days=days)


@router.get("/support/agent-productivity", dependencies=[Depends(Require("analytics:read"))])
async def get_agent_productivity(
    days: int = Query(default=30, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[Dict[str, Any]]:
    """Get ticket handling metrics by assigned employee/agent."""
    return await service.get_agent_productivity(days=days)


@router.get("/support/by-type", dependencies=[Depends(Require("analytics:read"))])
async def get_tickets_by_type(
    days: int = Query(default=30, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get ticket distribution by type/category."""
    return await service.get_tickets_by_type(days=days)


# ==============================================================================
# Network/Service Analytics
# ==============================================================================


@router.get("/network/device-status", dependencies=[Depends(Require("analytics:read"))])
async def get_network_device_status(db: Session = Depends(get_db_with_timeout)) -> Dict[str, Any]:
    """Get network device status summary using SQL aggregation."""
    # Single aggregated query for device status
    status_summary = (
        db.query(
            func.count(NetworkMonitor.id).label("total"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.UP, 1), else_=0)).label("up"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.DOWN, 1), else_=0)).label("down"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.UNKNOWN, 1), else_=0)).label("unknown"),
        )
        .filter(NetworkMonitor.active.is_(True))
        .first()
    )

    total = int(status_summary.total) if status_summary and status_summary.total else 0
    up = int(status_summary.up) if status_summary and status_summary.up else 0
    down = int(status_summary.down) if status_summary and status_summary.down else 0
    unknown = int(status_summary.unknown) if status_summary and status_summary.unknown else 0

    # By location
    by_location = (
        db.query(
            NetworkMonitor.location_id,
            func.count(NetworkMonitor.id).label("total"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.UP, 1), else_=0)).label("up"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.DOWN, 1), else_=0)).label("down"),
        )
        .filter(NetworkMonitor.active.is_(True))
        .group_by(NetworkMonitor.location_id)
        .all()
    )

    return {
        "summary": {
            "total": total,
            "up": up,
            "down": down,
            "unknown": unknown,
            "uptime_percent": round(up / total * 100, 1) if total > 0 else 0,
        },
        "by_location": [
            {
                "location_id": loc.location_id,
                "total": loc.total,
                "up": loc.up or 0,
                "down": loc.down or 0,
            }
            for loc in by_location if loc.location_id
        ],
    }


@router.get("/network/ip-utilization", dependencies=[Depends(Require("analytics:read"))])
async def get_ip_utilization(db: Session = Depends(get_db_with_timeout)) -> Dict[str, Any]:
    """Get IP address pool utilization."""
    networks = db.query(IPv4Network).all()

    results = []
    total_capacity = 0
    total_used = 0

    for net in networks:
        # Calculate capacity based on mask
        capacity = 2 ** (32 - net.mask) - 2 if net.mask < 31 else 2 ** (32 - net.mask)
        used = net.used or 0

        total_capacity += capacity
        total_used += used

        results.append({
            "network": net.cidr,
            "title": net.title,
            "type": net.type_of_usage,
            "capacity": capacity,
            "used": used,
            "available": capacity - used,
            "utilization_percent": round(used / capacity * 100, 1) if capacity > 0 else 0,
        })

    # Sort by utilization
    results.sort(key=lambda x: x["utilization_percent"], reverse=True)

    return {
        "networks": results[:20],  # Top 20 by utilization
        "summary": {
            "total_networks": len(networks),
            "total_capacity": total_capacity,
            "total_used": total_used,
            "total_available": total_capacity - total_used,
            "overall_utilization": round(total_used / total_capacity * 100, 1) if total_capacity > 0 else 0,
        },
    }


# ==============================================================================
# Expense/Cost Analytics
# ==============================================================================


@router.get("/expenses/by-category", dependencies=[Depends(Require("analytics:read"))])
async def get_expenses_by_category(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get expense breakdown by category."""
    return await service.get_expenses_by_category(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/expenses/by-cost-center", dependencies=[Depends(Require("analytics:read"))])
async def get_expenses_by_cost_center(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get expense breakdown by cost center (department)."""
    return await service.get_expenses_by_cost_center(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/expenses/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_expense_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db_with_timeout),
) -> List[Dict[str, Any]]:
    """Get monthly expense trend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=months * 30)

    trend = (
        db.query(
            extract("year", Expense.expense_date).label("year"),
            extract("month", Expense.expense_date).label("month"),
            func.count(Expense.id).label("count"),
            func.sum(Expense.total_sanctioned_amount).label("total"),
        )
        .filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(
            extract("year", Expense.expense_date),
            extract("month", Expense.expense_date),
        )
        .order_by(
            extract("year", Expense.expense_date),
            extract("month", Expense.expense_date),
        )
        .all()
    )

    return [
        {
            "year": int(t.year),
            "month": int(t.month),
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "count": t.count,
            "total": float(t.total or 0),
        }
        for t in trend
    ]


@router.get("/expenses/vendor-spend", dependencies=[Depends(Require("analytics:read"))])
async def get_vendor_spend(
    months: int = Query(default=12, le=24),
    limit: int = Query(default=20, le=50),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db_with_timeout),
) -> Dict[str, Any]:
    """Get top vendors by purchase invoice spend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=months * 30)

    vendors = (
        db.query(
            PurchaseInvoice.supplier,
            PurchaseInvoice.supplier_name,
            func.count(PurchaseInvoice.id).label("invoice_count"),
            func.sum(PurchaseInvoice.grand_total).label("total_spend"),
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        )
        .filter(
            PurchaseInvoice.posting_date >= start_dt,
            PurchaseInvoice.posting_date <= end_dt,
            PurchaseInvoice.docstatus == 1,  # Submitted
        )
        .group_by(PurchaseInvoice.supplier, PurchaseInvoice.supplier_name)
        .order_by(desc("total_spend"))
        .limit(limit)
        .all()
    )

    return {
        "vendors": [
            {
                "supplier": v.supplier,
                "supplier_name": v.supplier_name,
                "invoice_count": v.invoice_count,
                "total_spend": float(v.total_spend or 0),
                "outstanding": float(v.outstanding or 0),
            }
            for v in vendors
        ],
        "total_spend": sum(float(v.total_spend or 0) for v in vendors),
    }


# ==============================================================================
# People/Operations Analytics
# ==============================================================================


@router.get("/people/tickets-per-employee", dependencies=[Depends(Require("analytics:read"))])
async def get_tickets_per_employee(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_with_timeout),
) -> Dict[str, Any]:
    """Get ticket handling distribution per employee."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    by_employee = (
        db.query(
            Employee.id,
            Employee.name,
            Employee.department,
            func.count(Ticket.id).label("total_tickets"),
            func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label("open"),
        )
        .outerjoin(Ticket, and_(
            Ticket.assigned_employee_id == Employee.id,
            Ticket.created_at >= start_date,
        ))
        .filter(Employee.status == EmploymentStatus.ACTIVE)
        .group_by(Employee.id, Employee.name, Employee.department)
        .order_by(desc("total_tickets"))
        .all()
    )

    # Calculate averages
    total_tickets = sum(e.total_tickets or 0 for e in by_employee)
    active_employees = len([e for e in by_employee if (e.total_tickets or 0) > 0])

    return {
        "by_employee": [
            {
                "employee_id": e.id,
                "name": e.name,
                "department": e.department,
                "total_tickets": e.total_tickets or 0,
                "resolved": e.resolved or 0,
                "open": e.open or 0,
            }
            for e in by_employee[:20]  # Top 20
        ],
        "summary": {
            "total_tickets": total_tickets,
            "active_employees": active_employees,
            "avg_tickets_per_employee": round(total_tickets / active_employees, 1) if active_employees > 0 else 0,
        },
    }


@router.get("/people/by-department", dependencies=[Depends(Require("analytics:read"))])
async def get_metrics_by_department(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_with_timeout),
) -> List[Dict[str, Any]]:
    """Get ticket and expense metrics aggregated by department."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Employee counts by department
    employee_counts = (
        db.query(
            Employee.department,
            func.count(Employee.id).label("employee_count"),
        )
        .filter(Employee.status == EmploymentStatus.ACTIVE)
        .group_by(Employee.department)
        .all()
    )

    # Tickets by department (through assigned employee)
    ticket_counts = (
        db.query(
            Employee.department,
            func.count(Ticket.id).label("ticket_count"),
        )
        .join(Ticket, Ticket.assigned_employee_id == Employee.id)
        .filter(Ticket.created_at >= start_date)
        .group_by(Employee.department)
        .all()
    )

    # Expenses by department (cost center approximation)
    expense_totals = (
        db.query(
            Expense.cost_center,
            func.sum(Expense.total_sanctioned_amount).label("expense_total"),
        )
        .filter(
            Expense.expense_date >= start_date,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(Expense.cost_center)
        .all()
    )

    # Combine data
    departments: Dict[str, Dict[str, Any]] = {}

    for ec in employee_counts:
        dept = ec.department or "Unassigned"
        departments[dept] = {
            "department": dept,
            "employee_count": ec.employee_count,
            "ticket_count": 0,
            "expense_total": 0.0,
        }

    for tc in ticket_counts:
        dept = tc.department or "Unassigned"
        if dept in departments:
            departments[dept]["ticket_count"] = tc.ticket_count

    for et in expense_totals:
        # Try to match cost center to department
        cost_center = et.cost_center or "Unassigned"
        if cost_center in departments:
            departments[cost_center]["expense_total"] = float(et.expense_total or 0)

    return list(departments.values())


# ==============================================================================
# Analytics Exports
# ==============================================================================


@router.get("/exports/{report}", dependencies=[Depends(Require("analytics:read"))])
async def export_analytics_report(
    report: str,
    format: str = Query("csv", description="Export format: csv or pdf"),
    days: int = Query(30, le=90),
    months: int = Query(12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db_with_timeout),
    principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """Export analytics reports to CSV or PDF."""
    export_format = format.lower()
    if export_format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be csv or pdf")

    if export_format == "pdf" and not WEASYPRINT_AVAILABLE:
        raise HTTPException(status_code=400, detail="PDF export not available (install weasyprint)")

    analytics = AnalyticsService(db, principal)
    insights = InsightsService(db, principal=principal)
    export_service = AnalyticsExportService()

    sections: List[Dict[str, Any]] = []
    title = "Analytics Export"

    if report == "revenue":
        title = "Revenue Analytics"
        overview = await analytics.get_overview()
        dso = await analytics.get_dso(months=months, start_date=start_date, end_date=end_date)
        aging = await analytics.get_invoice_aging()
        territories = await analytics.get_revenue_by_territory(months=months)
        trend = await analytics.get_revenue_trend(months=months, start_date=start_date, end_date=end_date)
        plans = await analytics.get_customers_by_plan()
        cohorts = await analytics.get_revenue_cohort()

        sections = [
            {
                "title": "Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "MRR", "Value": overview.get("revenue", {}).get("mrr", 0)},
                    {"Metric": "Outstanding", "Value": overview.get("revenue", {}).get("outstanding", 0)},
                    {"Metric": "Overdue Invoices", "Value": overview.get("revenue", {}).get("overdue_invoices", 0)},
                    {"Metric": "Currency", "Value": overview.get("revenue", {}).get("currency", "")},
                ],
            },
            {
                "title": "DSO Trend",
                "columns": ["Period", "DSO", "Invoiced", "Outstanding"],
                "rows": [
                    {
                        "Period": row["period"],
                        "DSO": row["dso"],
                        "Invoiced": row["invoiced"],
                        "Outstanding": row["outstanding"],
                    }
                    for row in dso.get("trend", [])
                ],
            },
            {
                "title": "Invoice Aging",
                "columns": ["Bucket", "Count", "Amount"],
                "rows": [
                    {
                        "Bucket": bucket.replace("_", " "),
                        "Count": data.get("count", 0),
                        "Amount": data.get("amount", 0),
                    }
                    for bucket, data in aging.get("aging", {}).items()
                ],
            },
            {
                "title": "Revenue by Territory",
                "columns": ["Territory", "Customers", "MRR"],
                "rows": [
                    {
                        "Territory": row.get("territory", "Unknown"),
                        "Customers": row.get("customer_count", 0),
                        "MRR": row.get("mrr", 0),
                    }
                    for row in territories
                ],
            },
            {
                "title": "Revenue Trend",
                "columns": ["Period", "Payments", "Revenue"],
                "rows": [
                    {
                        "Period": row.get("period"),
                        "Payments": row.get("payment_count", 0),
                        "Revenue": row.get("revenue", 0),
                    }
                    for row in trend
                ],
            },
            {
                "title": "Customers by Plan",
                "columns": ["Plan", "Customers", "Subscriptions", "MRR"],
                "rows": [
                    {
                        "Plan": row.get("plan_name") or "Unspecified",
                        "Customers": row.get("customer_count", 0),
                        "Subscriptions": row.get("subscription_count", 0),
                        "MRR": row.get("mrr", 0),
                    }
                    for row in plans
                ],
            },
            {
                "title": "Cohort Retention",
                "columns": ["Cohort", "Total", "Active", "Churned", "Retention Rate"],
                "rows": [
                    {
                        "Cohort": row.get("cohort"),
                        "Total": row.get("total_customers"),
                        "Active": row.get("active"),
                        "Churned": row.get("churned"),
                        "Retention Rate": row.get("retention_rate"),
                    }
                    for row in cohorts.get("cohorts", [])
                ],
            },
        ]

    elif report == "customers":
        title = "Customer Analytics"
        customers = await analytics.get_customer_summary()
        segments = insights.get_customer_segments()
        health = insights.get_customer_health()
        churn = await analytics.get_churn_trend(months=months, start_date=start_date, end_date=end_date)

        sections = [
            {
                "title": "Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Total Customers", "Value": customers.get("total_customers", 0)},
                    {"Metric": "Active Customers", "Value": customers.get("active_customers", 0)},
                    {"Metric": "Churned Customers", "Value": customers.get("churned_customers", 0)},
                    {"Metric": "New Customers (30d)", "Value": customers.get("new_last_30_days", 0)},
                ],
            },
            {
                "title": "Health Indicators",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Overdue Customers", "Value": health.payment_behavior.customers_with_overdue},
                    {"Metric": "High Support Customers", "Value": health.support_intensity.high_support_customers},
                    {"Metric": "Recent Cancellations", "Value": health.churn_indicators.recently_cancelled_30d},
                ],
            },
            {
                "title": "Segments by Status",
                "columns": ["Status", "Customers", "MRR"],
                "rows": [
                    {"Status": row["status"], "Customers": row["count"], "MRR": row.get("mrr", 0)}
                    for row in segments.by_status
                ],
            },
            {
                "title": "Segments by Type",
                "columns": ["Type", "Customers", "MRR"],
                "rows": [
                    {"Type": row["type"], "Customers": row["count"], "MRR": row.get("mrr", 0)}
                    for row in segments.by_type
                ],
            },
            {
                "title": "Tenure Segments",
                "columns": ["Segment", "Customers"],
                "rows": [
                    {"Segment": row["segment"], "Customers": row["count"]}
                    for row in segments.by_tenure
                ],
            },
            {
                "title": "MRR Tiers",
                "columns": ["Tier", "Customers"],
                "rows": [
                    {"Tier": row["segment"], "Customers": row["count"]}
                    for row in segments.by_mrr_tier
                ],
            },
            {
                "title": "Top Cities",
                "columns": ["City", "Customers", "MRR"],
                "rows": [
                    {"City": row["city"], "Customers": row["count"], "MRR": row.get("mrr", 0)}
                    for row in segments.by_city
                ],
            },
            {
                "title": "POP Distribution",
                "columns": ["POP", "City", "Customers", "MRR"],
                "rows": [
                    {
                        "POP": row["pop_name"],
                        "City": row.get("city") or "",
                        "Customers": row.get("customer_count", 0),
                        "MRR": row.get("mrr", 0),
                    }
                    for row in segments.by_pop
                ],
            },
            {
                "title": "Churn Trend",
                "columns": ["Period", "Churned", "Churn Rate", "Active Base"],
                "rows": [
                    {
                        "Period": row["period"],
                        "Churned": row["churned_count"],
                        "Churn Rate": row["churn_rate"],
                        "Active Base": row["active_base"],
                    }
                    for row in churn.get("data", [])
                ],
            },
        ]

    elif report == "support":
        title = "Support Analytics"
        parsed_start = _parse_date_param(start_date, "start_date")
        parsed_end = _parse_date_param(end_date, "end_date")
        if parsed_end:
            parsed_end = parsed_end.replace(hour=23, minute=59, second=59)
        metrics = await analytics.get_support_metrics(days=days, start_date=parsed_start, end_date=parsed_end)
        sla = await analytics.get_sla_attainment(days=days)
        agents = await analytics.get_agent_productivity(days=days)
        ticket_types = await analytics.get_tickets_by_type(days=days)

        sections = [
            {
                "title": "Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Total Conversations", "Value": metrics.get("total_conversations", 0)},
                    {"Metric": "Open", "Value": metrics.get("open", 0)},
                    {"Metric": "Resolved", "Value": metrics.get("resolved", 0)},
                    {"Metric": "Resolution Rate", "Value": metrics.get("resolution_rate", 0)},
                    {"Metric": "Avg First Response (hrs)", "Value": metrics.get("avg_first_response_hours", 0)},
                    {"Metric": "Avg Resolution (hrs)", "Value": metrics.get("avg_resolution_hours", 0)},
                ],
            },
            {
                "title": "SLA Attainment",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "SLA Met", "Value": sla.get("sla_attainment", {}).get("met", 0)},
                    {"Metric": "SLA Breached", "Value": sla.get("sla_attainment", {}).get("breached", 0)},
                    {"Metric": "Attainment Rate", "Value": sla.get("sla_attainment", {}).get("rate", 0)},
                ],
            },
            {
                "title": "Channels",
                "columns": ["Channel", "Count"],
                "rows": [
                    {"Channel": channel, "Count": count}
                    for channel, count in (metrics.get("by_channel") or {}).items()
                ],
            },
            {
                "title": "Ticket Types",
                "columns": ["Type", "Total", "Resolved", "Resolution Rate"],
                "rows": [
                    {
                        "Type": row.get("type"),
                        "Total": row.get("count", 0),
                        "Resolved": row.get("resolved", 0),
                        "Resolution Rate": row.get("resolution_rate", 0),
                    }
                    for row in ticket_types.get("by_type", [])
                ],
            },
            {
                "title": "Agent Productivity",
                "columns": ["Agent", "Department", "Tickets", "Resolved", "Resolution Rate", "Avg Hours"],
                "rows": [
                    {
                        "Agent": row.get("name"),
                        "Department": row.get("department") or "",
                        "Tickets": row.get("total_tickets", 0),
                        "Resolved": row.get("resolved", 0),
                        "Resolution Rate": row.get("resolution_rate", 0),
                        "Avg Hours": row.get("avg_resolution_hours", 0),
                    }
                    for row in agents
                ],
            },
        ]

    elif report == "operations":
        title = "Operations Analytics"
        field_service = FieldServiceAnalyticsService(db, principal=principal)
        parsed_start = _parse_date_param(start_date, "start_date")
        parsed_end = _parse_date_param(end_date, "end_date")
        if parsed_end:
            parsed_end = parsed_end.replace(hour=23, minute=59, second=59)
        if parsed_start and parsed_end:
            start_dt = parsed_start.date()
            end_dt = parsed_end.date()
        else:
            end_dt = datetime.now(timezone.utc).date()
            start_dt = end_dt - timedelta(days=months * 30)
        filters = AnalyticsFilters(start_date=start_dt, end_date=end_dt)
        dashboard = field_service.get_dashboard_metrics(filters)
        order_breakdown = field_service.get_order_type_breakdown(filters)
        expenses = await analytics.get_expenses_by_category(months=months, start_date=start_date, end_date=end_date)
        cost_centers = await analytics.get_expenses_by_cost_center(months=months, start_date=start_date, end_date=end_date)

        sections = [
            {
                "title": "Field Service Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Completion Rate", "Value": dashboard.completion_rate},
                    {"Metric": "Avg Rating", "Value": dashboard.avg_customer_rating},
                    {"Metric": "Avg Completion Time (hrs)", "Value": dashboard.avg_completion_time_hours},
                    {"Metric": "Total Revenue", "Value": float(dashboard.total_revenue or 0)},
                ],
            },
            {
                "title": "Service Order Types",
                "columns": ["Type", "Orders", "Share", "Revenue"],
                "rows": [
                    {
                        "Type": row.order_type,
                        "Orders": row.count,
                        "Share": row.percentage,
                        "Revenue": float(row.revenue or 0),
                    }
                    for row in order_breakdown
                ],
            },
            {
                "title": "Expenses by Category",
                "columns": ["Category", "Count", "Total"],
                "rows": [
                    {
                        "Category": row.get("category"),
                        "Count": row.get("count", 0),
                        "Total": row.get("total", 0),
                    }
                    for row in expenses.get("by_category", [])
                ],
            },
            {
                "title": "Expenses by Cost Center",
                "columns": ["Cost Center", "Count", "Total"],
                "rows": [
                    {
                        "Cost Center": row.get("cost_center"),
                        "Count": row.get("count", 0),
                        "Total": row.get("total", 0),
                    }
                    for row in cost_centers.get("by_cost_center", [])
                ],
            },
        ]

    elif report == "hr":
        title = "HR Analytics"
        hr_service = HRAnalyticsService(db, principal=principal)
        workforce = hr_service.get_workforce_analytics()
        turnover = hr_service.get_turnover_analytics()

        sections = [
            {
                "title": "Workforce Snapshot",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Total Headcount", "Value": workforce.total_headcount},
                    {"Metric": "Active Employees", "Value": workforce.active_employees},
                    {"Metric": "On Leave", "Value": workforce.on_leave},
                    {"Metric": "Terminated", "Value": workforce.terminated},
                    {"Metric": "Avg Tenure (months)", "Value": workforce.avg_tenure_months},
                    {"Metric": "New Hires (30d)", "Value": workforce.new_hires_30d},
                    {"Metric": "Separations (30d)", "Value": workforce.separations_30d},
                ],
            },
            {
                "title": "Headcount by Department",
                "columns": ["Department", "Count"],
                "rows": [
                    {"Department": row.department_name, "Count": row.total_employees}
                    for row in workforce.headcount_by_department
                ],
            },
            {
                "title": "Headcount by Designation",
                "columns": ["Designation", "Count"],
                "rows": [
                    {"Designation": row.designation_name, "Count": row.employee_count}
                    for row in workforce.headcount_by_designation
                ],
            },
            {
                "title": "Turnover Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Total Separations", "Value": turnover.total_separations},
                    {"Metric": "Voluntary", "Value": turnover.voluntary_separations},
                    {"Metric": "Involuntary", "Value": turnover.involuntary_separations},
                    {"Metric": "Turnover Rate", "Value": turnover.turnover_rate},
                    {"Metric": "Avg Tenure at Exit (months)", "Value": turnover.avg_tenure_at_exit_months},
                ],
            },
        ]

    elif report == "insights":
        title = "Data Insights"
        completeness = insights.get_data_completeness()
        anomalies = insights.detect_anomalies()
        availability = insights.get_data_availability()

        sections = [
            {
                "title": "Data Completeness",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"Metric": "Total Customers", "Value": completeness.summary.get("total_customers", 0)},
                    {"Metric": "Critical Completeness", "Value": completeness.summary.get("critical_completeness_score", 0)},
                    {"Metric": "Overall Completeness", "Value": completeness.summary.get("overall_completeness_score", 0)},
                    {"Metric": "Grade", "Value": completeness.summary.get("grade", "")},
                ],
            },
            {
                "title": "Recommendations",
                "columns": ["Priority", "Category", "Issue", "Action"],
                "rows": [
                    {
                        "Priority": rec.priority,
                        "Category": rec.category,
                        "Issue": rec.issue,
                        "Action": rec.action,
                    }
                    for rec in completeness.recommendations
                ],
            },
            {
                "title": "Anomalies",
                "columns": ["Type", "Severity", "Description"],
                "rows": [
                    {
                        "Type": anomaly.type,
                        "Severity": anomaly.severity,
                        "Description": anomaly.description,
                    }
                    for anomaly in anomalies.anomalies
                ],
            },
            {
                "title": "Patterns",
                "columns": ["Type", "Insight"],
                "rows": [
                    {
                        "Type": pattern.type,
                        "Insight": pattern.description,
                    }
                    for pattern in anomalies.patterns
                ],
            },
            {
                "title": "Source Coverage",
                "columns": ["Source", "Metric", "Count"],
                "rows": [
                    {
                        "Source": source,
                        "Metric": metric.replace("_", " "),
                        "Count": count,
                    }
                    for source, data in availability.data_by_source.items()
                    for metric, count in data.items()
                ],
            },
            {
                "title": "Missing Critical Data",
                "columns": ["Entity", "Field", "Count", "Impact", "Description"],
                "rows": [
                    {
                        "Entity": item.entity,
                        "Field": item.field,
                        "Count": item.count,
                        "Impact": item.impact,
                        "Description": item.description,
                    }
                    for item in availability.missing_critical_data
                ],
            },
        ]

    else:
        raise HTTPException(status_code=404, detail="Unknown analytics report")

    try:
        if export_format == "csv":
            csv_content = export_service.export_csv(title, sections)
            return _stream_export(
                csv_content.encode("utf-8"),
                "text/csv",
                f"{report}-analytics",
                "csv",
            )

        pdf_content = export_service.export_pdf(title, sections)
        return _stream_export(
            pdf_content,
            "application/pdf",
            f"{report}-analytics",
            "pdf",
        )
    except AnalyticsExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
