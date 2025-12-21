"""
Consolidated Dashboard Endpoints

Provides single-payload dashboard endpoints for improved frontend performance.
Each dashboard endpoint aggregates all data needed for its respective page.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL

# Models
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.customer import Customer
from app.models.accounting import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
    GLEntry,
    Account,
    AccountType,
    BankAccount,
    FiscalYear,
)
from app.models.sales import ERPNextLead, ERPNextLeadStatus
from app.models.crm import (
    Opportunity,
    OpportunityStatus,
    OpportunityStage,
    Activity,
    ActivityType,
    ActivityStatus,
)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


def _resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, return first."""
    if requested:
        return requested
    currencies = [row[0] for row in db.query(distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    first = currencies[0]
    return str(first) if first is not None else None


def _parse_date_param(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}") from exc


# =============================================================================
# SALES DASHBOARD - Consolidated (13 calls → 1)
# =============================================================================

@router.get("/sales", dependencies=[Depends(Require("analytics:read"))])
@cached("dashboard-sales", ttl=CACHE_TTL["short"])
async def get_sales_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Sales Dashboard endpoint.

    Combines data from:
    - Finance dashboard (MRR, ARR, collections, outstanding, DSO)
    - AR Aging analysis
    - Revenue trend (12 months)
    - Recent invoices (5)
    - Recent payments (5)
    - Recent credit notes (5)
    - Recent bills (5)
    - Recent purchase payments (5)
    - CRM Leads summary
    - Pipeline summary
    - Pipeline stages view
    - Upcoming activities (5)
    - Overdue activities
    """
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency) or "NGN"
    now = datetime.now(timezone.utc)
    today = date.today()
    thirty_days_ago = now - timedelta(days=30)

    # =========== FINANCE DASHBOARD DATA ===========
    # MRR calculation
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
        *([Subscription.currency == currency] if currency else []),
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
    outstanding = float(outstanding_query.scalar() or 0)
    overdue_amount = float(overdue_query.scalar() or 0)

    # Collections last 30 days
    # Note: DB enum has mixed case - COMPLETED (uppercase) and posted (lowercase)
    collections_30d_query = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= thirty_days_ago
    )
    invoiced_30d_query = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= thirty_days_ago
    )
    if currency:
        collections_30d_query = collections_30d_query.filter(Payment.currency == currency)
        invoiced_30d_query = invoiced_30d_query.filter(Invoice.currency == currency)
    collections_30d = float(collections_30d_query.scalar() or 0)
    invoiced_30d = float(invoiced_30d_query.scalar() or 0)
    collection_rate = round(collections_30d / invoiced_30d, 3) if invoiced_30d else 0

    # DSO
    avg_daily_revenue = collections_30d / 30 if collections_30d else 0
    dso = round(outstanding / avg_daily_revenue, 1) if avg_daily_revenue > 0 else 0

    # =========== AGING DATA ===========
    days_overdue = func.date_part("day", func.current_date() - Invoice.due_date)
    aging_bucket = case(
        (Invoice.due_date >= func.current_date(), 'current'),
        (days_overdue <= 30, '1_30'),
        (days_overdue <= 60, '31_60'),
        (days_overdue <= 90, '61_90'),
        else_='over_90'
    )
    aging_query = db.query(
        aging_bucket.label("bucket"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.due_date.isnot(None),
    )
    if currency:
        aging_query = aging_query.filter(Invoice.currency == currency)
    aging_results = aging_query.group_by(aging_bucket).all()

    aging_map = {row.bucket: {"count": row.count, "total": float(row.outstanding or 0)} for row in aging_results}
    aging_buckets = {
        "current": aging_map.get("current", {"count": 0, "total": 0}),
        "1_30": aging_map.get("1_30", {"count": 0, "total": 0}),
        "31_60": aging_map.get("31_60", {"count": 0, "total": 0}),
        "61_90": aging_map.get("61_90", {"count": 0, "total": 0}),
        "over_90": aging_map.get("over_90", {"count": 0, "total": 0}),
    }

    # =========== REVENUE TREND (last 6 months) ===========
    six_months_ago = now - timedelta(days=180)
    trunc = func.date_trunc("month", Payment.payment_date)
    revenue_trend_query = db.query(
        func.to_char(trunc, "YYYY-MM").label("period"),
        func.sum(Payment.amount).label("revenue"),
        func.count(Payment.id).label("payment_count"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= six_months_ago,
    )
    if currency:
        revenue_trend_query = revenue_trend_query.filter(Payment.currency == currency)
    revenue_trend = [
        {"period": r.period, "revenue": float(r.revenue or 0), "payment_count": r.payment_count}
        for r in revenue_trend_query.group_by(trunc).order_by(trunc).all()
    ]

    # =========== RECENT INVOICES (5) ===========
    recent_invoices_query = db.query(Invoice).outerjoin(
        Customer, Invoice.customer_id == Customer.id
    ).add_columns(Customer.name.label("customer_name"))
    if currency:
        recent_invoices_query = recent_invoices_query.filter(Invoice.currency == currency)
    recent_invoices_rows = recent_invoices_query.order_by(
        Invoice.invoice_date.desc()
    ).limit(5).all()
    recent_invoices = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_name": cname,
            "total_amount": float(inv.total_amount),
            "currency": inv.currency,
            "status": inv.status.value if inv.status else None,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        }
        for inv, cname in recent_invoices_rows
    ]

    # =========== RECENT PAYMENTS (5) ===========
    recent_payments_query = db.query(Payment).outerjoin(
        Customer, Payment.customer_id == Customer.id
    ).add_columns(Customer.name.label("customer_name"))
    if currency:
        recent_payments_query = recent_payments_query.filter(Payment.currency == currency)
    recent_payments_rows = recent_payments_query.order_by(
        Payment.payment_date.desc()
    ).limit(5).all()
    recent_payments = [
        {
            "id": pay.id,
            "receipt_number": pay.receipt_number,
            "customer_name": cname,
            "amount": float(pay.amount),
            "currency": pay.currency,
            "status": pay.status.value if pay.status else None,
            "payment_date": pay.payment_date.isoformat() if pay.payment_date else None,
        }
        for pay, cname in recent_payments_rows
    ]

    # =========== RECENT CREDIT NOTES (5) ===========
    recent_credits_query = db.query(CreditNote).outerjoin(
        Customer, CreditNote.customer_id == Customer.id
    ).add_columns(Customer.name.label("customer_name"))
    if currency:
        recent_credits_query = recent_credits_query.filter(CreditNote.currency == currency)
    recent_credits_rows = recent_credits_query.order_by(
        CreditNote.issue_date.desc()
    ).limit(5).all()
    recent_credit_notes = [
        {
            "id": cn.id,
            "credit_number": cn.credit_number,
            "customer_name": cname,
            "amount": float(cn.amount) if cn.amount else 0,
            "currency": cn.currency,
            "status": cn.status.value if cn.status else None,
            "issue_date": cn.issue_date.isoformat() if cn.issue_date else None,
        }
        for cn, cname in recent_credits_rows
    ]

    # =========== RECENT BILLS (5) ===========
    recent_bills_query = db.query(PurchaseInvoice)
    if currency:
        recent_bills_query = recent_bills_query.filter(PurchaseInvoice.currency == currency)
    recent_bills_rows = recent_bills_query.order_by(
        PurchaseInvoice.posting_date.desc()
    ).limit(5).all()
    recent_bills = [
        {
            "id": b.id,
            "supplier_name": b.supplier_name or b.supplier,
            "grand_total": float(b.grand_total),
            "currency": b.currency,
            "status": b.status.value if b.status else None,
            "posting_date": b.posting_date.isoformat() if b.posting_date else None,
        }
        for b in recent_bills_rows
    ]

    # =========== RECENT PURCHASE PAYMENTS (5) ===========
    purchase_payments_query = db.query(GLEntry).filter(
        GLEntry.voucher_type == "Payment Entry",
        GLEntry.party_type == "Supplier",
        GLEntry.is_cancelled == False,
    ).order_by(GLEntry.posting_date.desc()).limit(5)
    purchase_payments_rows = purchase_payments_query.all()
    recent_purchase_payments = [
        {
            "id": p.id,
            "supplier": p.party,
            "amount": float(p.credit - p.debit),
            "posting_date": p.posting_date.isoformat() if p.posting_date else None,
        }
        for p in purchase_payments_rows
    ]

    # =========== CRM: LEADS SUMMARY ===========
    total_leads = db.query(func.count(ERPNextLead.id)).scalar() or 0
    new_leads = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.status == ERPNextLeadStatus.LEAD
    ).scalar() or 0
    contacted_leads = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.status == ERPNextLeadStatus.INTERESTED
    ).scalar() or 0
    qualified_leads = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.status == ERPNextLeadStatus.OPPORTUNITY
    ).scalar() or 0
    converted_leads = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.converted == True
    ).scalar() or 0

    leads_summary = {
        "total": total_leads,
        "new": new_leads,
        "contacted": contacted_leads,
        "qualified": qualified_leads,
        "converted": converted_leads,
    }

    # =========== CRM: PIPELINE SUMMARY ===========
    open_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0
    total_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0
    weighted_value = db.query(func.sum(Opportunity.weighted_value)).filter(
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0

    won_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.WON
    ).scalar() or 0
    lost_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.LOST
    ).scalar() or 0
    total_closed = won_count + lost_count
    win_rate = won_count / total_closed if total_closed > 0 else 0

    pipeline_summary = {
        "open_count": open_count,
        "total_value": float(total_value or 0),
        "weighted_value": float(weighted_value or 0),
        "win_rate": round(win_rate, 2),
        "won_count": won_count,
        "lost_count": lost_count,
    }

    # =========== CRM: PIPELINE STAGES ===========
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.is_active == True
    ).order_by(OpportunityStage.sequence).all()

    pipeline_stages = []
    for stage in stages:
        stage_count = db.query(func.count(Opportunity.id)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        stage_value = db.query(func.sum(Opportunity.deal_value)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0

        pipeline_stages.append({
            "id": stage.id,
            "name": stage.name,
            "sequence": stage.sequence,
            "probability": stage.probability,
            "is_won": stage.is_won,
            "is_lost": stage.is_lost,
            "color": stage.color,
            "opportunity_count": stage_count,
            "opportunity_value": float(stage_value or 0),
        })

    # =========== CRM: ACTIVITIES ===========
    upcoming_activities_query = db.query(Activity).filter(
        Activity.status == ActivityStatus.PLANNED,
        Activity.scheduled_at >= now,
    ).order_by(Activity.scheduled_at.asc()).limit(5)
    upcoming_activities = [
        {
            "id": a.id,
            "activity_type": a.activity_type.value if a.activity_type else None,
            "subject": a.subject,
            "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
            "priority": a.priority,
        }
        for a in upcoming_activities_query.all()
    ]

    overdue_activities_query = db.query(Activity).filter(
        Activity.status == ActivityStatus.PLANNED,
        Activity.scheduled_at < now,
    ).order_by(Activity.scheduled_at.desc())
    overdue_activities = [
        {
            "id": a.id,
            "activity_type": a.activity_type.value if a.activity_type else None,
            "subject": a.subject,
            "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
            "priority": a.priority,
        }
        for a in overdue_activities_query.all()
    ]

    return {
        "currency": currency,
        "generated_at": now.isoformat(),

        # Finance metrics
        "finance": {
            "revenue": {
                "mrr": mrr,
                "arr": arr,
                "active_subscriptions": active_subscriptions,
            },
            "collections": {
                "last_30_days": collections_30d,
                "invoiced_30_days": invoiced_30d,
                "collection_rate": collection_rate,
            },
            "outstanding": {
                "total": outstanding,
                "overdue": overdue_amount,
            },
            "metrics": {
                "dso": dso,
            },
            "invoices_by_status": invoice_by_status,
        },

        # Aging
        "aging": {
            "buckets": aging_buckets,
        },

        # Revenue trend
        "revenue_trend": revenue_trend,

        # Recent transactions
        "recent": {
            "invoices": recent_invoices,
            "payments": recent_payments,
            "credit_notes": recent_credit_notes,
            "bills": recent_bills,
            "purchase_payments": recent_purchase_payments,
        },

        # CRM data
        "crm": {
            "leads": leads_summary,
            "pipeline": pipeline_summary,
            "stages": pipeline_stages,
            "upcoming_activities": upcoming_activities,
            "overdue_activities": overdue_activities,
        },
    }


# =============================================================================
# PURCHASING DASHBOARD - Consolidated (8 calls → 1)
# =============================================================================

@router.get("/purchasing", dependencies=[Depends(Require("purchasing:read"))])
@cached("dashboard-purchasing", ttl=CACHE_TTL["short"])
async def get_purchasing_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Purchasing Dashboard endpoint.

    Combines data from:
    - Purchasing dashboard (AP metrics)
    - Suppliers count
    - Bills count
    - AP Aging analysis
    - Top suppliers by spend
    - Recent payments
    - Recent orders
    - Recent debit notes
    """
    today = date.today()
    start_dt = _parse_date_param(start_date, "start_date")
    end_dt = _parse_date_param(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    range_start = datetime.combine(start_dt, datetime.min.time()) if start_dt else None
    range_end = datetime.combine(end_dt, datetime.max.time()) if end_dt else None

    def apply_range_filter(query, column):
        if range_start:
            query = query.filter(column >= range_start)
        if range_end:
            query = query.filter(column <= range_end)
        return query

    # =========== MAIN DASHBOARD METRICS ===========
    overdue_cutoff = datetime.combine((end_dt or today), datetime.max.time())
    outstanding_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    if currency:
        outstanding_query = outstanding_query.filter(PurchaseInvoice.currency == currency)
    outstanding_query = apply_range_filter(outstanding_query, PurchaseInvoice.posting_date)
    total_outstanding = float(outstanding_query.scalar() or 0)

    overdue_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date < overdue_cutoff,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    if currency:
        overdue_query = overdue_query.filter(PurchaseInvoice.currency == currency)
    overdue_query = apply_range_filter(overdue_query, PurchaseInvoice.posting_date)
    total_overdue = float(overdue_query.scalar() or 0)
    overdue_percentage = round(total_overdue / total_outstanding * 100, 1) if total_outstanding > 0 else 0

    # Bills by status
    bills_by_status = db.query(
        PurchaseInvoice.status,
        func.count(PurchaseInvoice.id).label("count"),
        func.sum(PurchaseInvoice.grand_total).label("total"),
    )
    if currency:
        bills_by_status = bills_by_status.filter(PurchaseInvoice.currency == currency)
    bills_by_status = apply_range_filter(bills_by_status, PurchaseInvoice.posting_date)
    bills_by_status = bills_by_status.group_by(PurchaseInvoice.status).all()
    status_breakdown = {
        row.status.value if row.status else "unknown": {
            "count": row.count,
            "total": float(row.total or 0),
        }
        for row in bills_by_status
    }

    # Due this week (relative to range end if provided)
    due_base_date = end_dt or today
    week_end = due_base_date + timedelta(days=7)
    due_start = datetime.combine(due_base_date, datetime.min.time())
    due_end = datetime.combine(week_end, datetime.max.time())
    due_this_week = db.query(
        func.count(PurchaseInvoice.id),
        func.sum(PurchaseInvoice.outstanding_amount),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date >= due_start,
        PurchaseInvoice.due_date <= due_end,
    )
    if currency:
        due_this_week = due_this_week.filter(PurchaseInvoice.currency == currency)
    due_this_week = apply_range_filter(due_this_week, PurchaseInvoice.posting_date)
    due_result = due_this_week.first()
    due_this_week_data = {
        "count": int(due_result[0] or 0) if due_result else 0,
        "total": float(due_result[1] or 0) if due_result else 0,
    }

    # Supplier count
    if range_start or range_end:
        supplier_count_query = db.query(
            func.count(distinct(PurchaseInvoice.supplier_name))
        ).filter(PurchaseInvoice.supplier_name.isnot(None))
        supplier_count_query = apply_range_filter(supplier_count_query, PurchaseInvoice.posting_date)
        if currency:
            supplier_count_query = supplier_count_query.filter(PurchaseInvoice.currency == currency)
        supplier_count = supplier_count_query.scalar() or 0
    else:
        supplier_count = db.query(func.count(Supplier.id)).filter(
            Supplier.disabled == False
        ).scalar() or 0

    # Total bills count
    bills_count_query = db.query(func.count(PurchaseInvoice.id))
    if currency:
        bills_count_query = bills_count_query.filter(PurchaseInvoice.currency == currency)
    bills_count_query = apply_range_filter(bills_count_query, PurchaseInvoice.posting_date)
    total_bills = bills_count_query.scalar() or 0

    # =========== AP AGING ===========
    aging_query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )
    if currency:
        aging_query = aging_query.filter(PurchaseInvoice.currency == currency)
    aging_query = apply_range_filter(aging_query, PurchaseInvoice.posting_date)
    invoices = aging_query.all()

    aging_buckets = {
        "current": {"count": 0, "total": 0.0},
        "1_30": {"count": 0, "total": 0.0},
        "31_60": {"count": 0, "total": 0.0},
        "61_90": {"count": 0, "total": 0.0},
        "over_90": {"count": 0, "total": 0.0},
    }

    aging_base_date = end_dt or today
    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else aging_base_date)
        days = (aging_base_date - due).days if aging_base_date > due else 0

        if days <= 0:
            bucket = "current"
        elif days <= 30:
            bucket = "1_30"
        elif days <= 60:
            bucket = "31_60"
        elif days <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        aging_buckets[bucket]["count"] += 1
        aging_buckets[bucket]["total"] += float(inv.outstanding_amount or 0)

    # =========== TOP SUPPLIERS (5) ===========
    top_suppliers_query = db.query(
        PurchaseInvoice.supplier_name,
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        func.count(PurchaseInvoice.id).label("bill_count"),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
    )
    if currency:
        top_suppliers_query = top_suppliers_query.filter(PurchaseInvoice.currency == currency)
    top_suppliers_query = apply_range_filter(top_suppliers_query, PurchaseInvoice.posting_date)
    top_suppliers_query = top_suppliers_query.group_by(
        PurchaseInvoice.supplier_name
    ).order_by(
        func.sum(PurchaseInvoice.outstanding_amount).desc()
    ).limit(5)

    top_suppliers = [
        {
            "name": row.supplier_name,
            "outstanding": float(row.outstanding),
            "bill_count": row.bill_count,
        }
        for row in top_suppliers_query.all()
    ]

    # =========== RECENT BILLS (5) ===========
    recent_bills_query = db.query(PurchaseInvoice)
    if currency:
        recent_bills_query = recent_bills_query.filter(PurchaseInvoice.currency == currency)
    recent_bills_query = apply_range_filter(recent_bills_query, PurchaseInvoice.posting_date)
    recent_bills = [
        {
            "id": b.id,
            "supplier_name": b.supplier_name or b.supplier,
            "grand_total": float(b.grand_total),
            "outstanding_amount": float(b.outstanding_amount),
            "currency": b.currency,
            "status": b.status.value if b.status else None,
            "posting_date": b.posting_date.isoformat() if b.posting_date else None,
            "due_date": b.due_date.isoformat() if b.due_date else None,
        }
        for b in recent_bills_query.order_by(PurchaseInvoice.posting_date.desc()).limit(5).all()
    ]

    # =========== RECENT PAYMENTS (5) ===========
    recent_payments = [
        {
            "id": p.id,
            "supplier": p.party,
            "amount": float(p.credit - p.debit),
            "posting_date": p.posting_date.isoformat() if p.posting_date else None,
            "voucher_no": p.voucher_no,
        }
        for p in apply_range_filter(
            db.query(GLEntry).filter(
            GLEntry.voucher_type == "Payment Entry",
            GLEntry.party_type == "Supplier",
            GLEntry.is_cancelled == False,
            ),
            GLEntry.posting_date,
        ).order_by(GLEntry.posting_date.desc()).limit(5).all()
    ]

    # =========== RECENT ORDERS (5) ===========
    orders_query = db.query(
        GLEntry.voucher_no,
        GLEntry.party,
        func.min(GLEntry.posting_date).label("date"),
        func.sum(GLEntry.debit).label("total"),
    ).filter(
        GLEntry.voucher_type == "Purchase Order",
        GLEntry.is_cancelled == False,
    )
    orders_query = apply_range_filter(orders_query, GLEntry.posting_date).group_by(
        GLEntry.voucher_no, GLEntry.party
    ).order_by(
        func.min(GLEntry.posting_date).desc()
    ).limit(5)

    recent_orders = [
        {
            "order_no": o.voucher_no,
            "supplier": o.party,
            "date": o.date.isoformat() if o.date else None,
            "total": float(o.total or 0),
        }
        for o in orders_query.all()
    ]

    # =========== RECENT DEBIT NOTES (5) ===========
    debit_notes_query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.is_return == True,
    )
    if currency:
        debit_notes_query = debit_notes_query.filter(PurchaseInvoice.currency == currency)
    debit_notes_query = apply_range_filter(debit_notes_query, PurchaseInvoice.posting_date)

    recent_debit_notes = [
        {
            "id": n.id,
            "supplier": n.supplier_name or n.supplier,
            "grand_total": float(n.grand_total),
            "posting_date": n.posting_date.isoformat() if n.posting_date else None,
            "status": n.status.value if n.status else None,
        }
        for n in debit_notes_query.order_by(PurchaseInvoice.posting_date.desc()).limit(5).all()
    ]

    return {
        "currency": currency,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "summary": {
            "total_outstanding": total_outstanding,
            "total_overdue": total_overdue,
            "overdue_percentage": overdue_percentage,
            "supplier_count": supplier_count,
            "total_bills": total_bills,
            "due_this_week": due_this_week_data,
            "status_breakdown": status_breakdown,
        },

        "aging": {
            "buckets": aging_buckets,
        },

        "top_suppliers": top_suppliers,

        "recent": {
            "bills": recent_bills,
            "payments": recent_payments,
            "orders": recent_orders,
            "debit_notes": recent_debit_notes,
        },
    }


# =============================================================================
# SUPPORT DASHBOARD - Consolidated (7 calls → 1)
# =============================================================================

@router.get("/support", dependencies=[Depends(Require("support:read"))])
@cached("dashboard-support", ttl=CACHE_TTL["short"])
async def get_support_dashboard(
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Support Dashboard endpoint.

    Combines data from:
    - Support dashboard (open, resolved, overdue tickets)
    - Volume trend (6 months)
    - SLA performance
    - Tickets by category
    - Queue health
    - SLA breaches summary
    - Teams and agents count
    """
    # Import ticket models dynamically to avoid circular imports
    from app.models.unified_ticket import UnifiedTicket as Ticket, TicketStatus, TicketPriority
    from app.models.agent import Team, Agent

    now = datetime.now(timezone.utc)
    today = date.today()
    thirty_days_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)
    start_dt = _parse_date_param(start_date, "start_date")
    end_dt = _parse_date_param(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    range_start = datetime.combine(start_dt, datetime.min.time()) if start_dt else None
    range_end = datetime.combine(end_dt, datetime.max.time()) if end_dt else None

    def apply_range_filter(query, column):
        if range_start:
            query = query.filter(column >= range_start)
        if range_end:
            query = query.filter(column <= range_end)
        return query

    # =========== MAIN METRICS ===========
    # Note: Database enum uses lowercase values, so we use the enum .value attribute
    open_status_values = ["open", "in_progress", "waiting"]
    resolved_status_values = ["resolved", "closed"]

    open_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values)
    )
    open_tickets_query = apply_range_filter(open_tickets_query, Ticket.created_at)
    open_tickets = open_tickets_query.scalar() or 0

    resolved_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(resolved_status_values)
    )
    resolved_tickets_query = apply_range_filter(resolved_tickets_query, Ticket.created_at)
    resolved_tickets = resolved_tickets_query.scalar() or 0

    overdue_cutoff = range_end or now
    overdue_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values),
        Ticket.resolution_by < overdue_cutoff,
    )
    overdue_tickets_query = apply_range_filter(overdue_tickets_query, Ticket.created_at)
    overdue_tickets = overdue_tickets_query.scalar() or 0

    unassigned_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values),
        Ticket.assigned_to_id.is_(None),
    )
    unassigned_tickets_query = apply_range_filter(unassigned_tickets_query, Ticket.created_at)
    unassigned_tickets = unassigned_tickets_query.scalar() or 0

    # Average resolution time (hours)
    avg_resolution_query = db.query(
        func.avg(func.extract('epoch', Ticket.resolved_at - Ticket.created_at) / 3600)
    ).filter(
        Ticket.resolved_at.isnot(None),
        Ticket.created_at.isnot(None),
    )
    avg_resolution_query = apply_range_filter(avg_resolution_query, Ticket.created_at)
    avg_resolution = avg_resolution_query.scalar()
    avg_resolution_hours = round(float(avg_resolution or 0), 1)

    # SLA attainment (use resolution_by as indicator that SLA applies)
    total_with_sla_query = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.status.in_(resolved_status_values)
    )
    total_with_sla_query = apply_range_filter(total_with_sla_query, Ticket.created_at)
    total_with_sla = total_with_sla_query.scalar() or 0

    sla_met_query = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.status.in_(resolved_status_values),
        Ticket.resolution_sla_breached == False,
    )
    sla_met_query = apply_range_filter(sla_met_query, Ticket.created_at)
    sla_met = sla_met_query.scalar() or 0

    sla_attainment = round(sla_met / total_with_sla * 100, 1) if total_with_sla > 0 else 100

    # =========== VOLUME TREND (6 months) ===========
    trunc = func.date_trunc("month", Ticket.created_at)
    trend_start = range_start or six_months_ago
    volume_query = db.query(
        func.to_char(trunc, "YYYY-MM").label("period"),
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= trend_start,
    )
    if range_end:
        volume_query = volume_query.filter(Ticket.created_at <= range_end)
    volume_query = volume_query.group_by(trunc).order_by(trunc)
    volume_trend = [
        {
            "period": r.period,
            "count": r.count,
        }
        for r in volume_query.all()
    ]

    # =========== SLA PERFORMANCE (6 months) ===========
    sla_performance = []
    sla_query = db.query(
        func.to_char(trunc, "YYYY-MM").label("period"),
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.resolution_sla_breached == False, 1), else_=0)).label("met"),
        func.sum(case((Ticket.resolution_sla_breached == True, 1), else_=0)).label("breached"),
    ).filter(
        Ticket.created_at >= trend_start,
        Ticket.resolution_by.isnot(None),
    )
    if range_end:
        sla_query = sla_query.filter(Ticket.created_at <= range_end)
    for r in sla_query.group_by(trunc).order_by(trunc).all():
        total = r.total or 0
        met = int(r.met or 0)
        breached = int(r.breached or 0)
        sla_performance.append({
            "period": r.period,
            "total": total,
            "met": met,
            "breached": breached,
            "rate": round(met / total * 100, 1) if total > 0 else 100,
        })

    # =========== BY CATEGORY (30 days) ===========
    category_start = range_start or thirty_days_ago
    by_category_query = db.query(
        Ticket.category,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= category_start,
    )
    if range_end:
        by_category_query = by_category_query.filter(Ticket.created_at <= range_end)
    by_category = [
        {
            "category": r.category or "Uncategorized",
            "count": r.count,
        }
        for r in by_category_query.group_by(Ticket.category).order_by(func.count(Ticket.id).desc()).limit(10).all()
    ]

    # =========== QUEUE HEALTH ===========
    # Avg wait time for unassigned tickets
    avg_wait_query = db.query(
        func.avg(func.extract('epoch', func.now() - Ticket.created_at) / 3600)
    ).filter(
        Ticket.assigned_to_id.is_(None),
        Ticket.status == "open",
    )
    avg_wait_query = apply_range_filter(avg_wait_query, Ticket.created_at)
    avg_wait = avg_wait_query.scalar()

    # Agent capacity
    total_agents = db.query(func.count(Agent.id)).filter(Agent.is_active == True).scalar() or 0

    # Current load (open tickets per agent)
    current_load = round(open_tickets / total_agents, 1) if total_agents > 0 else 0

    queue_health = {
        "unassigned_count": unassigned_tickets,
        "avg_wait_hours": round(float(avg_wait or 0), 1),
        "total_agents": total_agents,
        "current_load": current_load,
    }

    # =========== SLA BREACHES (30 days) ===========
    breaches_query = db.query(
        Ticket.priority,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.resolution_sla_breached == True,
        Ticket.created_at >= category_start,
    ).group_by(Ticket.priority)
    if range_end:
        breaches_query = breaches_query.filter(Ticket.created_at <= range_end)

    sla_breaches = {
        r.priority.value if r.priority else "unknown": r.count
        for r in breaches_query.all()
    }
    total_breaches = sum(sla_breaches.values())

    # =========== TEAMS & AGENTS ===========
    team_count = db.query(func.count(Team.id)).filter(Team.is_active == True).scalar() or 0
    active_agents = total_agents

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
            "overdue_tickets": overdue_tickets,
            "unassigned_tickets": unassigned_tickets,
            "avg_resolution_hours": avg_resolution_hours,
            "sla_attainment": sla_attainment,
            "team_count": team_count,
            "agent_count": active_agents,
        },

        "volume_trend": volume_trend,
        "sla_performance": sla_performance,
        "by_category": by_category,
        "queue_health": queue_health,

        "sla_breaches": {
            "total": total_breaches,
            "by_priority": sla_breaches,
        },
    }


# =============================================================================
# FIELD SERVICE DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/field-service", dependencies=[Depends(Require("field_service:read"))])
@cached("dashboard-field-service", ttl=CACHE_TTL["short"])
async def get_field_service_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Field Service Dashboard endpoint.

    Combines data from:
    - Dashboard summary (today's orders, completion, etc.)
    - Today's orders list
    """
    from app.models.field_service import ServiceOrder, ServiceOrderStatus

    now = datetime.now(timezone.utc)
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # =========== SUMMARY METRICS ===========
    today_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
    ).scalar() or 0

    completed_today = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).scalar() or 0

    unassigned = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.DISPATCHED]),
        ServiceOrder.assigned_technician_id.is_(None),
    ).scalar() or 0

    overdue = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.DISPATCHED, ServiceOrderStatus.IN_PROGRESS]),
        ServiceOrder.scheduled_date < today_start,
    ).scalar() or 0

    # Week completion rate
    week_total = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= datetime.combine(week_start, datetime.min.time()),
        ServiceOrder.scheduled_date <= datetime.combine(week_end, datetime.max.time()),
    ).scalar() or 0

    week_completed = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= datetime.combine(week_start, datetime.min.time()),
        ServiceOrder.scheduled_date <= datetime.combine(week_end, datetime.max.time()),
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).scalar() or 0

    week_completion_rate = round(week_completed / week_total * 100, 1) if week_total > 0 else 0

    # Avg customer rating
    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.customer_rating.isnot(None),
    ).scalar()
    avg_customer_rating = round(float(avg_rating or 0), 1)

    # By status
    by_status = {
        row.status.value if row.status else "unknown": row.count
        for row in db.query(
            ServiceOrder.status,
            func.count(ServiceOrder.id).label("count"),
        ).group_by(ServiceOrder.status).all()
    }

    # By type
    by_type = {
        row.order_type.value if row.order_type else "unknown": row.count
        for row in db.query(
            ServiceOrder.order_type,
            func.count(ServiceOrder.id).label("count"),
        ).group_by(ServiceOrder.order_type).all()
    }

    # =========== TODAY'S ORDERS ===========
    today_orders_list = []
    for order in db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
    ).order_by(ServiceOrder.scheduled_date.asc()).limit(10).all():
        # Use the technician relationship from ServiceOrder
        technician_name = order.technician.name if order.technician else None

        today_orders_list.append({
            "id": order.id,
            "order_number": order.order_number,
            "order_type": order.order_type.value if order.order_type else None,
            "status": order.status.value if order.status else None,
            "customer_name": order.customer.name if order.customer else None,
            "customer_address": order.service_address,
            "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
            "technician_name": technician_name,
            "priority": order.priority.value if order.priority else None,
        })

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "today_orders": today_orders,
            "completed_today": completed_today,
            "unassigned": unassigned,
            "overdue": overdue,
            "week_completion_rate": week_completion_rate,
            "avg_customer_rating": avg_customer_rating,
        },

        "by_status": by_status,
        "by_type": by_type,

        "today_schedule": today_orders_list,
    }


# =============================================================================
# ACCOUNTING DASHBOARD - Consolidated (11 calls → 1)
# =============================================================================

@router.get("/accounting", dependencies=[Depends(Require("accounting:read"))])
@cached("dashboard-accounting", ttl=CACHE_TTL["short"])
async def get_accounting_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Accounting Dashboard endpoint.

    Combines data from:
    - Main dashboard (assets, liabilities, equity, net income)
    - Balance sheet
    - Income statement
    - Suppliers count
    - Bank accounts
    - General ledger count
    - Receivables
    - Fiscal years
    - Receivables outstanding (top 5)
    - Payables outstanding (top 5)
    - Cash flow
    """
    now = datetime.now(timezone.utc)
    today = date.today()
    currency = currency or "NGN"

    # Get current fiscal year
    fiscal_year = db.query(FiscalYear).filter(
        FiscalYear.year_start_date <= today,
        FiscalYear.year_end_date >= today,
    ).first()

    fy_start = (
        fiscal_year.year_start_date if fiscal_year and fiscal_year.year_start_date else date(today.year, 1, 1)
    )
    fy_end = (
        fiscal_year.year_end_date if fiscal_year and fiscal_year.year_end_date else date(today.year, 12, 31)
    )

    # =========== BALANCE SHEET SUMMARY ===========
    # Assets
    asset_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.ASSET,
        Account.disabled == False,
    ).all()
    asset_ids = [a[0] for a in asset_accounts]

    total_assets = 0.0
    if asset_ids:
        assets_sum = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(asset_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_assets = float(assets_sum or 0)

    # Liabilities
    liability_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.LIABILITY,
        Account.disabled == False,
    ).all()
    liability_ids = [a[0] for a in liability_accounts]

    total_liabilities = 0.0
    if liability_ids:
        liab_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(liability_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_liabilities = float(liab_sum or 0)

    # Equity
    equity_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EQUITY,
        Account.disabled == False,
    ).all()
    equity_ids = [a[0] for a in equity_accounts]

    total_equity = 0.0
    if equity_ids:
        equity_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(equity_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_equity = float(equity_sum or 0)

    # =========== INCOME STATEMENT (YTD) ===========
    # Income
    income_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.INCOME,
        Account.disabled == False,
    ).all()
    income_ids = [a[0] for a in income_accounts]

    total_income = 0.0
    if income_ids:
        income_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(income_ids),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= fy_start,
            GLEntry.posting_date <= today,
        ).scalar()
        total_income = float(income_sum or 0)

    # Expenses
    expense_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EXPENSE,
        Account.disabled == False,
    ).all()
    expense_ids = [a[0] for a in expense_accounts]

    total_expenses = 0.0
    if expense_ids:
        expense_sum = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(expense_ids),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= fy_start,
            GLEntry.posting_date <= today,
        ).scalar()
        total_expenses = float(expense_sum or 0)

    net_income = total_income - total_expenses

    # =========== BANK ACCOUNTS ===========
    bank_accounts_query = db.query(BankAccount).filter(
        BankAccount.disabled == False,
    ).all()

    def get_bank_balance(account: BankAccount) -> float:
        if not account.account:
            return 0.0
        balance = db.query(func.sum(GLEntry.debit - GLEntry.credit)).filter(
            GLEntry.account == account.account,
            GLEntry.is_cancelled == False,
        ).scalar()
        return float(balance or 0)

    bank_accounts = [
        {
            "id": ba.id,
            "account_name": ba.account_name,
            "bank_name": ba.bank,
            "account_number": ba.bank_account_no[-4:] if ba.bank_account_no and len(ba.bank_account_no) >= 4 else "****",
            "balance": get_bank_balance(ba),
            "currency": ba.currency,
        }
        for ba in bank_accounts_query[:5]
    ]

    total_cash = sum((get_bank_balance(ba) for ba in bank_accounts_query), 0.0)

    # =========== COUNTS ===========
    supplier_count = db.query(func.count(Supplier.id)).filter(
        Supplier.disabled == False
    ).scalar() or 0

    gl_entries_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= fy_start,
    ).scalar() or 0

    # =========== RECEIVABLES ===========
    total_receivable_query = db.query(
        func.sum(Invoice.total_amount - Invoice.amount_paid)
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
    )
    if currency:
        total_receivable_query = total_receivable_query.filter(Invoice.currency == currency)
    total_receivable = float(total_receivable_query.scalar() or 0)

    # =========== PAYABLES ===========
    total_payable_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
    )
    if currency:
        total_payable_query = total_payable_query.filter(PurchaseInvoice.currency == currency)
    total_payable = float(total_payable_query.scalar() or 0)

    # =========== TOP RECEIVABLES (5) ===========
    top_receivables = [
        {
            "customer_name": r.customer_name,
            "outstanding": float(r.outstanding),
            "invoice_count": r.count,
        }
        for r in db.query(
            Customer.name.label("customer_name"),
            func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
            func.count(Invoice.id).label("count"),
        ).join(Customer, Invoice.customer_id == Customer.id).filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
            *([Invoice.currency == currency] if currency else []),
        ).group_by(Customer.name).order_by(
            func.sum(Invoice.total_amount - Invoice.amount_paid).desc()
        ).limit(5).all()
    ]

    # =========== TOP PAYABLES (5) ===========
    top_payables = [
        {
            "supplier_name": r.supplier_name,
            "outstanding": float(r.outstanding),
            "bill_count": r.count,
        }
        for r in db.query(
            PurchaseInvoice.supplier_name,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.count(PurchaseInvoice.id).label("count"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            *([PurchaseInvoice.currency == currency] if currency else []),
        ).group_by(PurchaseInvoice.supplier_name).order_by(
            func.sum(PurchaseInvoice.outstanding_amount).desc()
        ).limit(5).all()
    ]

    # =========== FISCAL YEARS ===========
    fiscal_years = [
        {
            "id": fy.id,
            "name": fy.year,
            "start_date": fy.year_start_date.isoformat() if fy.year_start_date else None,
            "end_date": fy.year_end_date.isoformat() if fy.year_end_date else None,
            "is_closed": fy.disabled,
        }
        for fy in db.query(FiscalYear).order_by(FiscalYear.year_start_date.desc()).limit(5).all()
    ]

    # =========== FINANCIAL RATIOS ===========
    current_ratio = round(total_assets / total_liabilities, 2) if total_liabilities > 0 else 0
    debt_to_equity = round(total_liabilities / total_equity, 2) if total_equity > 0 else 0
    profit_margin = round(net_income / total_income * 100, 1) if total_income > 0 else 0

    return {
        "currency": currency,
        "generated_at": now.isoformat(),
        "fiscal_year": {
            "start": fy_start.isoformat(),
            "end": fy_end.isoformat(),
        },

        "balance_sheet": {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "net_worth": total_assets - total_liabilities,
        },

        "income_statement": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_income": net_income,
        },

        "cash": {
            "total": total_cash,
            "bank_accounts": bank_accounts,
        },

        "receivables": {
            "total": total_receivable,
            "top_customers": top_receivables,
        },

        "payables": {
            "total": total_payable,
            "top_suppliers": top_payables,
        },

        "ratios": {
            "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity,
            "profit_margin": profit_margin,
        },

        "counts": {
            "suppliers": supplier_count,
            "gl_entries": gl_entries_count,
        },

        "fiscal_years": fiscal_years,
    }
