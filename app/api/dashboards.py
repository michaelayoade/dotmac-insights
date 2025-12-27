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
from app.models.customer import Customer, CustomerStatus
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
        func.count(Ticket.id).label("breach_count"),
    ).filter(
        Ticket.resolution_sla_breached == True,
        Ticket.created_at >= category_start,
    ).group_by(Ticket.priority)
    if range_end:
        breaches_query = breaches_query.filter(Ticket.created_at <= range_end)

    sla_breaches = {
        r.priority.value if r.priority else "unknown": int(r.breach_count or 0)
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

@router.get("/field-service", dependencies=[Depends(Require("field-service:read"))])
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


# =============================================================================
# HR DASHBOARD - Consolidated (11 calls → 1)
# =============================================================================

@router.get("/hr", dependencies=[Depends(Require("hr:read"))])
@cached("dashboard-hr", ttl=CACHE_TTL["short"])
async def get_hr_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated HR Dashboard endpoint.

    Combines data from:
    - Employee summary (total, active, on leave)
    - Leave applications (pending, by status, trend)
    - Attendance summary (30 days)
    - Payroll summary (last 30 days)
    - Recruitment (open positions, funnel)
    - Training events (scheduled)
    - Onboarding (active)
    """
    from app.models.employee import Employee, EmploymentStatus
    from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus
    from app.models.hr_attendance import Attendance
    from app.models.hr_payroll import SalarySlip, SalarySlipStatus
    from app.models.hr_recruitment import JobOpening, JobApplicant
    from app.models.hr_training import TrainingEvent
    from app.models.hr_lifecycle import EmployeeOnboarding, BoardingStatus

    now = datetime.now(timezone.utc)
    today = date.today()
    thirty_days_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)

    # =========== EMPLOYEE SUMMARY ===========
    total_employees = db.query(func.count(Employee.id)).scalar() or 0
    active_employees = db.query(func.count(Employee.id)).filter(
        Employee.status == EmploymentStatus.ACTIVE
    ).scalar() or 0

    # On leave today (check active leave applications)
    on_leave_today = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= today,
    ).scalar() or 0

    # =========== LEAVE DATA ===========
    pending_leave = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).scalar() or 0

    leave_by_status = db.query(
        LeaveApplication.status,
        func.count(LeaveApplication.id).label("count")
    ).group_by(LeaveApplication.status).all()
    leave_status_map = {
        row.status.value if row.status else "unknown": row.count
        for row in leave_by_status
    }

    # Leave trend (last 6 months)
    trunc_month = func.date_trunc("month", LeaveApplication.posting_date)
    leave_trend = [
        {"month": r.period, "count": r.count}
        for r in db.query(
            func.to_char(trunc_month, "YYYY-MM").label("period"),
            func.count(LeaveApplication.id).label("count")
        ).filter(
            LeaveApplication.posting_date >= six_months_ago
        ).group_by(trunc_month).order_by(trunc_month).all()
    ]

    # =========== ATTENDANCE (30 days) ===========
    attendance_summary = db.query(
        Attendance.status,
        func.count(Attendance.id).label("count")
    ).filter(
        Attendance.attendance_date >= (today - timedelta(days=30))
    ).group_by(Attendance.status).all()
    attendance_30d = {
        row.status.value if hasattr(row.status, 'value') else str(row.status): row.count
        for row in attendance_summary
    }

    # Present today
    present_today = db.query(func.count(Attendance.id)).filter(
        Attendance.attendance_date == today,
        Attendance.status.in_(["Present", "present", "PRESENT"])
    ).scalar() or 0

    # Attendance trend (14 days)
    attendance_trend = []
    for i in range(14):
        day = today - timedelta(days=13 - i)
        day_counts = db.query(
            Attendance.status,
            func.count(Attendance.id).label("count")
        ).filter(
            Attendance.attendance_date == day
        ).group_by(Attendance.status).all()
        status_counts = {
            row.status.value if hasattr(row.status, 'value') else str(row.status): row.count
            for row in day_counts
        }
        attendance_trend.append({
            "date": day.isoformat(),
            "status_counts": status_counts
        })

    # =========== PAYROLL (30 days) ===========
    payroll_summary = db.query(
        func.count(SalarySlip.id).label("slip_count"),
        func.sum(SalarySlip.gross_pay).label("gross_total"),
        func.sum(SalarySlip.total_deduction).label("deduction_total"),
        func.sum(SalarySlip.net_pay).label("net_total"),
    ).filter(
        SalarySlip.posting_date >= thirty_days_ago,
        SalarySlip.docstatus == 1,
    ).first()

    payroll_30d = {
        "slip_count": payroll_summary.slip_count or 0 if payroll_summary else 0,
        "gross_total": float(payroll_summary.gross_total or 0) if payroll_summary else 0,
        "deduction_total": float(payroll_summary.deduction_total or 0) if payroll_summary else 0,
        "net_total": float(payroll_summary.net_total or 0) if payroll_summary else 0,
    }

    # =========== RECRUITMENT ===========
    open_positions = db.query(func.count(JobOpening.id)).filter(
        JobOpening.status == "Open"
    ).scalar() or 0

    # Recruitment funnel
    total_applicants = db.query(func.count(JobApplicant.id)).scalar() or 0
    screened = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Screening", "Interview Scheduled", "Selected", "Offer Sent", "Accepted", "Rejected"])
    ).scalar() or 0
    interviewed = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Interview Scheduled", "Selected", "Offer Sent", "Accepted", "Rejected"])
    ).scalar() or 0
    offered = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Offer Sent", "Accepted"])
    ).scalar() or 0
    hired = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status == "Accepted"
    ).scalar() or 0

    recruitment_funnel = {
        "applications": total_applicants,
        "screened": screened,
        "interviewed": interviewed,
        "offered": offered,
        "hired": hired,
    }

    # =========== TRAINING ===========
    scheduled_training = db.query(func.count(TrainingEvent.id)).filter(
        TrainingEvent.start_time >= now
    ).scalar() or 0

    upcoming_training = [
        {
            "id": t.id,
            "event_name": t.event_name,
            "start_time": t.start_time.isoformat() if t.start_time else None,
            "type": t.type,
        }
        for t in db.query(TrainingEvent).filter(
            TrainingEvent.start_time >= now
        ).order_by(TrainingEvent.start_time.asc()).limit(5).all()
    ]

    # =========== ONBOARDING ===========
    active_onboardings = db.query(func.count(EmployeeOnboarding.id)).filter(
        EmployeeOnboarding.boarding_status.in_(
            [BoardingStatus.PENDING, BoardingStatus.IN_PROGRESS]
        )
    ).scalar() or 0

    recent_onboardings = [
        {
            "id": o.id,
            "employee_name": o.employee_name,
            "status": o.boarding_status.value if o.boarding_status else None,
            "date_of_joining": o.date_of_joining.isoformat() if o.date_of_joining else None,
        }
        for o in db.query(EmployeeOnboarding).filter(
            EmployeeOnboarding.boarding_status.in_(
                [BoardingStatus.PENDING, BoardingStatus.IN_PROGRESS]
            )
        ).order_by(EmployeeOnboarding.date_of_joining.desc()).limit(5).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "on_leave_today": on_leave_today,
            "present_today": present_today,
        },

        "leave": {
            "pending_approvals": pending_leave,
            "by_status": leave_status_map,
            "trend": leave_trend,
        },

        "attendance": {
            "status_30d": attendance_30d,
            "trend": attendance_trend,
        },

        "payroll_30d": payroll_30d,

        "recruitment": {
            "open_positions": open_positions,
            "funnel": recruitment_funnel,
        },

        "training": {
            "scheduled_events": scheduled_training,
            "upcoming": upcoming_training,
        },

        "onboarding": {
            "active_count": active_onboardings,
            "recent": recent_onboardings,
        },
    }


# =============================================================================
# INVENTORY DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/inventory", dependencies=[Depends(Require("inventory:read"))])
@cached("dashboard-inventory", ttl=CACHE_TTL["short"])
async def get_inventory_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Inventory Dashboard endpoint.

    Combines data from:
    - Stock summary (total value, item count)
    - Warehouse breakdown
    - Recent stock entries
    - Items with stock
    - Low stock alerts (coming soon)
    """
    from app.models.inventory import (
        Warehouse, StockEntry, StockLedgerEntry
    )
    from app.models.sales import Item

    now = datetime.now(timezone.utc)

    # =========== STOCK SUMMARY ===========
    # Get total stock value from stock ledger (latest entry per item/warehouse)
    stock_value_query = db.query(
        func.sum(StockLedgerEntry.stock_value)
    ).filter(
        StockLedgerEntry.is_cancelled == False
    )
    # This is a simplification - ideally we'd get the latest balance per item/warehouse
    total_stock_value = float(stock_value_query.scalar() or 0)

    # Total items with stock
    items_with_stock = db.query(
        func.count(distinct(StockLedgerEntry.item_code))
    ).filter(
        StockLedgerEntry.qty_after_transaction > 0,
        StockLedgerEntry.is_cancelled == False
    ).scalar() or 0

    # Total warehouses
    total_warehouses = db.query(func.count(Warehouse.id)).filter(
        Warehouse.disabled == False,
        Warehouse.is_group == False
    ).scalar() or 0

    # =========== WAREHOUSE BREAKDOWN ===========
    warehouse_summary = db.query(
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.stock_value).label("value"),
        func.count(distinct(StockLedgerEntry.item_code)).label("items")
    ).filter(
        StockLedgerEntry.is_cancelled == False
    ).group_by(
        StockLedgerEntry.warehouse
    ).order_by(
        func.sum(StockLedgerEntry.stock_value).desc()
    ).limit(10).all()

    stock_by_warehouse = [
        {
            "warehouse": row.warehouse,
            "value": float(row.value or 0),
            "items": row.items
        }
        for row in warehouse_summary
    ]

    # =========== RECENT STOCK ENTRIES ===========
    recent_entries = [
        {
            "id": e.id,
            "stock_entry_type": e.stock_entry_type,
            "posting_date": e.posting_date.isoformat() if e.posting_date else None,
            "total_amount": float(e.total_amount or 0),
            "from_warehouse": e.from_warehouse,
            "to_warehouse": e.to_warehouse,
            "docstatus": e.docstatus,
        }
        for e in db.query(StockEntry).filter(
            StockEntry.is_deleted == False
        ).order_by(
            StockEntry.posting_date.desc()
        ).limit(5).all()
    ]

    # =========== RECENT ITEMS ===========
    # Get items with actual stock
    recent_items = [
        {
            "id": i.id,
            "item_code": i.item_code,
            "item_name": i.item_name,
            "stock_uom": i.stock_uom,
            "total_stock_qty": 0,  # Would need aggregation from SLE
        }
        for i in db.query(Item).filter(
            Item.is_stock_item == True,
            Item.disabled == False
        ).order_by(
            Item.updated_at.desc()
        ).limit(5).all()
    ]

    # =========== ENTRY COUNTS ===========
    total_entries = db.query(func.count(StockEntry.id)).filter(
        StockEntry.is_deleted == False
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_value": total_stock_value,
            "total_items": items_with_stock,
            "total_warehouses": total_warehouses,
            "low_stock_alerts": 0,  # TODO: Implement reorder level check
        },

        "stock_by_warehouse": stock_by_warehouse,

        "recent": {
            "entries": recent_entries,
            "items": recent_items,
        },

        "counts": {
            "total_entries": total_entries,
        },
    }


# =============================================================================
# ASSETS DASHBOARD - Consolidated (5 calls → 1)
# =============================================================================

@router.get("/assets", dependencies=[Depends(Require("assets:read"))])
@cached("dashboard-assets", ttl=CACHE_TTL["short"])
async def get_assets_dashboard(
    days_ahead: int = 30,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Assets Dashboard endpoint.

    Combines data from:
    - Asset totals (count, purchase value, book value, depreciation)
    - Assets by status
    - Pending depreciation entries
    - Maintenance due
    - Warranty expiring
    - Insurance expiring
    """
    from app.models.asset import Asset, AssetStatus, AssetDepreciationSchedule

    now = datetime.now(timezone.utc)
    today = date.today()
    future_date = today + timedelta(days=days_ahead)

    # =========== TOTALS ===========
    totals = db.query(
        func.count(Asset.id).label("asset_count"),
        func.sum(Asset.gross_purchase_amount).label("purchase_value"),
        func.sum(Asset.asset_value).label("book_value"),
        func.sum(Asset.opening_accumulated_depreciation).label("accumulated_depreciation"),
    ).filter(
        Asset.status != AssetStatus.SCRAPPED
    ).first()

    totals_data = {
        "count": int(totals.asset_count) if totals and totals.asset_count is not None else 0,
        "purchase_value": float(totals.purchase_value or 0) if totals else 0,
        "book_value": float(totals.book_value or 0) if totals else 0,
        "accumulated_depreciation": float(totals.accumulated_depreciation or 0) if totals else 0,
    }

    # =========== BY STATUS ===========
    by_status = [
        {"status": row.status.value if row.status else "unknown", "count": int(row.status_count or 0)}
        for row in db.query(
            Asset.status,
            func.count(Asset.id).label("status_count")
        ).group_by(Asset.status).all()
    ]

    # =========== PENDING DEPRECIATION ===========
    pending_depreciation = db.query(AssetDepreciationSchedule).join(Asset).filter(
        AssetDepreciationSchedule.depreciation_booked == False,
        AssetDepreciationSchedule.schedule_date <= today,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(AssetDepreciationSchedule.schedule_date.asc()).limit(10).all()

    pending_dep_entries = [
        {
            "asset_id": d.asset_id,
            "asset_name": d.asset.asset_name if d.asset else None,
            "schedule_date": d.schedule_date.isoformat() if d.schedule_date else None,
            "depreciation_amount": float(d.depreciation_amount or 0),
        }
        for d in pending_depreciation
    ]

    pending_dep_total = db.query(
        func.count(AssetDepreciationSchedule.id),
        func.sum(AssetDepreciationSchedule.depreciation_amount)
    ).join(Asset).filter(
        AssetDepreciationSchedule.depreciation_booked == False,
        AssetDepreciationSchedule.schedule_date <= today,
        Asset.status == AssetStatus.SUBMITTED,
    ).first()

    # =========== MAINTENANCE DUE ===========
    maintenance_due = db.query(Asset).filter(
        Asset.maintenance_required == True,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.asset_name).limit(10).all()

    maintenance_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "location": a.location,
            "last_maintenance": None,  # Would need maintenance log
        }
        for a in maintenance_due
    ]

    # =========== WARRANTY EXPIRING ===========
    warranty_expiring = db.query(Asset).filter(
        Asset.warranty_expiry_date.isnot(None),
        Asset.warranty_expiry_date >= today,
        Asset.warranty_expiry_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.warranty_expiry_date.asc()).limit(10).all()

    warranty_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "warranty_expiry_date": a.warranty_expiry_date.isoformat() if a.warranty_expiry_date else None,
            "days_remaining": (a.warranty_expiry_date - today).days if a.warranty_expiry_date else 0,
        }
        for a in warranty_expiring
    ]

    warranty_count = db.query(func.count(Asset.id)).filter(
        Asset.warranty_expiry_date.isnot(None),
        Asset.warranty_expiry_date >= today,
        Asset.warranty_expiry_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).scalar() or 0

    # =========== INSURANCE EXPIRING ===========
    insurance_expiring = db.query(Asset).filter(
        Asset.insurance_end_date.isnot(None),
        Asset.insurance_end_date >= today,
        Asset.insurance_end_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.insurance_end_date.asc()).limit(10).all()

    insurance_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "insurance_end_date": a.insurance_end_date.isoformat() if a.insurance_end_date else None,
            "days_remaining": (a.insurance_end_date - today).days if a.insurance_end_date else 0,
        }
        for a in insurance_expiring
    ]

    insurance_count = db.query(func.count(Asset.id)).filter(
        Asset.insurance_end_date.isnot(None),
        Asset.insurance_end_date >= today,
        Asset.insurance_end_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "totals": totals_data,
        "by_status": by_status,

        "depreciation": {
            "pending_count": pending_dep_total[0] if pending_dep_total else 0,
            "pending_amount": float(pending_dep_total[1] or 0) if pending_dep_total else 0,
            "entries": pending_dep_entries,
        },

        "maintenance": {
            "due_count": len(maintenance_due),
            "assets": maintenance_assets,
        },

        "expiring": {
            "warranty": {
                "count": warranty_count,
                "assets": warranty_assets,
            },
            "insurance": {
                "count": insurance_count,
                "assets": insurance_assets,
            },
        },
    }


# =============================================================================
# EXPENSES DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/expenses", dependencies=[Depends(Require("expenses:read"))])
@cached("dashboard-expenses", ttl=CACHE_TTL["short"])
async def get_expenses_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Expenses Dashboard endpoint.

    Combines data from:
    - Expense claims summary (by status, totals)
    - Cash advances summary (by status, outstanding)
    - Recent claims and advances
    - Trend data
    """
    from app.models.expense_management import (
        ExpenseClaim, ExpenseClaimStatus,
        CashAdvance, CashAdvanceStatus
    )

    now = datetime.now(timezone.utc)
    today = date.today()
    six_months_ago = now - timedelta(days=180)

    # =========== EXPENSE CLAIMS ===========
    claims_by_status = db.query(
        ExpenseClaim.status,
        func.count(ExpenseClaim.id).label("status_count"),
        func.sum(ExpenseClaim.total_claimed_amount).label("status_total")
    ).group_by(ExpenseClaim.status).all()

    claims_status_map: Dict[str, Dict[str, float | int]] = {}
    for row in claims_by_status:
        status_key = row.status.value if row.status else "unknown"
        claims_status_map[status_key] = {
            "count": int(row.status_count or 0),
            "total": float(row.status_total or 0),
        }

    total_claims = sum(value["count"] for value in claims_status_map.values())
    total_claimed_amount = sum(value["total"] for value in claims_status_map.values())

    pending_claim_approvals = db.query(func.count(ExpenseClaim.id)).filter(
        ExpenseClaim.status == ExpenseClaimStatus.PENDING_APPROVAL
    ).scalar() or 0
    pending_advance_approvals = db.query(func.count(CashAdvance.id)).filter(
        CashAdvance.status == CashAdvanceStatus.PENDING_APPROVAL
    ).scalar() or 0
    pending_approvals = pending_claim_approvals + pending_advance_approvals

    # Recent claims
    recent_claims = [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "title": c.title,
            "total_claimed_amount": float(c.total_claimed_amount or 0),
            "status": c.status.value if c.status else None,
            "claim_date": c.claim_date.isoformat() if c.claim_date else None,
        }
        for c in db.query(ExpenseClaim).order_by(
            ExpenseClaim.claim_date.desc()
        ).limit(5).all()
    ]

    # =========== CASH ADVANCES ===========
    advances_by_status = db.query(
        CashAdvance.status,
        func.count(CashAdvance.id).label("status_count"),
        func.sum(CashAdvance.outstanding_amount).label("status_outstanding")
    ).group_by(CashAdvance.status).all()

    advances_status_map: Dict[str, Dict[str, float | int]] = {}
    for advance_row in advances_by_status:
        status_key = advance_row.status.value if advance_row.status else "unknown"
        advances_status_map[status_key] = {
            "count": int(advance_row.status_count or 0),
            "outstanding": float(advance_row.status_outstanding or 0),
        }

    total_advances = sum(value["count"] for value in advances_status_map.values())
    total_outstanding = sum(value["outstanding"] for value in advances_status_map.values())

    # Recent advances
    recent_advances = [
        {
            "id": a.id,
            "advance_number": a.advance_number,
            "purpose": a.purpose,
            "requested_amount": float(a.requested_amount or 0),
            "outstanding_amount": float(a.outstanding_amount or 0),
            "status": a.status.value if a.status else None,
            "request_date": a.request_date.isoformat() if a.request_date else None,
        }
        for a in db.query(CashAdvance).order_by(
            CashAdvance.request_date.desc()
        ).limit(5).all()
    ]

    # =========== TREND (6 months) ===========
    trunc_month = func.date_trunc("month", ExpenseClaim.claim_date)
    claims_trend = [
        {
            "month": r.period,
            "claims": r.count,
            "amount": float(r.total or 0)
        }
        for r in db.query(
            func.to_char(trunc_month, "YYYY-MM").label("period"),
            func.count(ExpenseClaim.id).label("count"),
            func.sum(ExpenseClaim.total_claimed_amount).label("total")
        ).filter(
            ExpenseClaim.claim_date >= six_months_ago
        ).group_by(trunc_month).order_by(trunc_month).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "claims": {
            "total": total_claims,
            "by_status": claims_status_map,
            "total_claimed_amount": total_claimed_amount,
            "recent": recent_claims,
        },

        "advances": {
            "total": total_advances,
            "by_status": advances_status_map,
            "outstanding_amount": total_outstanding,
            "recent": recent_advances,
        },

        "pending_approvals": pending_approvals,
        "trend": claims_trend,
    }


# =============================================================================
# PROJECTS DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/projects", dependencies=[Depends(Require("projects:read"))])
@cached("dashboard-projects", ttl=CACHE_TTL["short"])
async def get_projects_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Projects Dashboard endpoint.

    Combines data from:
    - Project summary (by status, totals)
    - Task metrics
    - Financial summary
    - Recent projects
    """
    from app.models.project import Project, ProjectStatus
    from app.models.task import Task

    now = datetime.now(timezone.utc)
    today = date.today()
    week_end = today + timedelta(days=7)

    # =========== PROJECT COUNTS ===========
    total_projects = db.query(func.count(Project.id)).filter(
        Project.is_deleted == False
    ).scalar() or 0

    active_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar() or 0

    completed_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.is_deleted == False
    ).scalar() or 0

    on_hold_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.ON_HOLD,
        Project.is_deleted == False
    ).scalar() or 0

    cancelled_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.CANCELLED,
        Project.is_deleted == False
    ).scalar() or 0

    # =========== TASK METRICS ===========
    total_tasks = db.query(func.count(Task.id)).scalar() or 0
    open_tasks = db.query(func.count(Task.id)).filter(
        Task.status.in_(["Open", "Working", "Pending Review", "open", "working"])
    ).scalar() or 0
    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.status.in_(["Open", "Working", "open", "working"]),
        Task.exp_end_date < today
    ).scalar() or 0

    # =========== COMPLETION METRICS ===========
    avg_completion = db.query(
        func.avg(Project.percent_complete)
    ).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar()
    avg_completion_percent = float(avg_completion or 0)

    # Due this week
    due_this_week = db.query(func.count(Project.id)).filter(
        Project.expected_end_date >= today,
        Project.expected_end_date <= week_end,
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar() or 0

    # =========== FINANCIALS ===========
    financials = db.query(
        func.sum(Project.total_billed_amount).label("billed"),
        func.sum(Project.total_costing_amount).label("cost"),
        func.sum(Project.gross_margin).label("margin")
    ).filter(
        Project.is_deleted == False
    ).first()

    financials_data = {
        "total_billed": float(financials.billed or 0) if financials else 0,
        "total_cost": float(financials.cost or 0) if financials else 0,
        "total_margin": float(financials.margin or 0) if financials else 0,
    }

    # =========== RECENT PROJECTS ===========
    recent_projects = [
        {
            "id": p.id,
            "project_name": p.project_name,
            "status": p.status.value if p.status else None,
            "percent_complete": float(p.percent_complete or 0),
            "expected_end_date": p.expected_end_date.isoformat() if p.expected_end_date else None,
            "department": p.department,
        }
        for p in db.query(Project).filter(
            Project.is_deleted == False
        ).order_by(
            Project.updated_at.desc()
        ).limit(5).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": completed_projects,
            "on_hold": on_hold_projects,
            "cancelled": cancelled_projects,
        },

        "tasks": {
            "total": total_tasks,
            "open": open_tasks,
            "overdue": overdue_tasks,
        },

        "metrics": {
            "avg_completion_percent": round(avg_completion_percent, 1),
            "due_this_week": due_this_week,
        },

        "financials": financials_data,

        "recent": recent_projects,
    }


# =============================================================================
# INBOX DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/inbox", dependencies=[Depends(Require("inbox:read"))])
@cached("dashboard-inbox", ttl=CACHE_TTL["short"])
async def get_inbox_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Inbox Dashboard endpoint.

    Combines data from:
    - Conversation summary (open, pending, resolved)
    - By channel breakdown
    - By priority breakdown
    - Recent conversations
    """
    from app.models.omni import OmniConversation, OmniChannel

    now = datetime.now(timezone.utc)
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # =========== CONVERSATION COUNTS ===========
    open_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "open"
    ).scalar() or 0

    pending_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "pending"
    ).scalar() or 0

    resolved_today = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "resolved",
        OmniConversation.resolved_at >= today_start
    ).scalar() or 0

    total_unread = db.query(func.sum(OmniConversation.unread_count)).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).scalar() or 0

    # =========== BY CHANNEL ===========
    by_channel = db.query(
        OmniChannel.type,
        func.count(OmniConversation.id).label("count")
    ).join(OmniChannel, OmniConversation.channel_id == OmniChannel.id).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).group_by(OmniChannel.type).all()

    channel_breakdown = {
        row.type: row.count
        for row in by_channel
    }

    # =========== BY PRIORITY ===========
    by_priority = db.query(
        OmniConversation.priority,
        func.count(OmniConversation.id).label("count")
    ).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).group_by(OmniConversation.priority).all()

    priority_breakdown = {
        row.priority: row.count
        for row in by_priority
    }

    # =========== RECENT CONVERSATIONS ===========
    recent_conversations = [
        {
            "id": c.id,
            "subject": c.subject,
            "contact_name": c.contact_name,
            "contact_email": c.contact_email,
            "status": c.status,
            "priority": c.priority,
            "unread_count": c.unread_count,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        }
        for c in db.query(OmniConversation).filter(
            OmniConversation.status.in_(["open", "pending"])
        ).order_by(
            OmniConversation.last_message_at.desc()
        ).limit(10).all()
    ]

    # =========== AVG RESPONSE TIME ===========
    avg_response = db.query(
        func.avg(
            func.extract(
                "epoch",
                OmniConversation.first_response_at - OmniConversation.created_at,
            )
        )
    ).filter(
        OmniConversation.first_response_at.isnot(None)
    ).scalar()
    avg_response_hours = round(float(avg_response or 0) / 3600, 1)

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "open_count": open_count,
            "pending_count": pending_count,
            "resolved_today": resolved_today,
            "total_unread": int(total_unread or 0),
        },

        "by_channel": channel_breakdown,
        "by_priority": priority_breakdown,
        "avg_response_time_hours": avg_response_hours,

        "recent": recent_conversations,
    }


# =============================================================================
# CONTACTS DASHBOARD - Consolidated
# =============================================================================

@router.get("/contacts", dependencies=[Depends(Require("contacts:read"))])
@cached("dashboard-contacts", ttl=CACHE_TTL["short"])
async def get_contacts_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Contacts Dashboard endpoint.

    Combines data from:
    - Contact summary (total, by type)
    - Pipeline/funnel data
    - Source distribution
    - Recent activities
    """
    from app.models.unified_contact import UnifiedContact
    from app.models.crm import Activity, ActivityStatus

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # =========== CONTACT COUNTS ===========
    total_contacts = db.query(func.count(UnifiedContact.id)).scalar() or 0

    # By type/stage
    by_stage = db.query(
        UnifiedContact.contact_type,
        func.count(UnifiedContact.id).label("count")
    ).group_by(UnifiedContact.contact_type).all()

    stage_breakdown = {
        row.contact_type.value if row.contact_type else "unknown": row.count
        for row in by_stage
    }

    # =========== SOURCE DISTRIBUTION ===========
    by_source = db.query(
        UnifiedContact.source,
        func.count(UnifiedContact.id).label("count")
    ).filter(
        UnifiedContact.source.isnot(None)
    ).group_by(UnifiedContact.source).order_by(
        func.count(UnifiedContact.id).desc()
    ).limit(10).all()

    source_breakdown = [
        {"source": row.source, "count": row.count}
        for row in by_source
    ]

    # =========== RECENT ACTIVITIES ===========
    recent_activities = [
        {
            "id": a.id,
            "activity_type": a.activity_type.value if a.activity_type else None,
            "subject": a.subject,
            "status": a.status.value if a.status else None,
            "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
        }
        for a in db.query(Activity).filter(
            Activity.status.in_([ActivityStatus.PLANNED, ActivityStatus.COMPLETED])
        ).order_by(Activity.scheduled_at.desc()).limit(5).all()
    ]

    # =========== NEW CONTACTS (30 days) ===========
    new_contacts_30d = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.created_at >= thirty_days_ago
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_contacts": total_contacts,
            "new_30d": new_contacts_30d,
            "by_stage": stage_breakdown,
        },

        "sources": source_breakdown,
        "recent_activities": recent_activities,
    }


# =============================================================================
# CUSTOMERS DASHBOARD - Consolidated
# =============================================================================

@router.get("/customers", dependencies=[Depends(Require("customers:read"))])
@cached("dashboard-customers", ttl=CACHE_TTL["short"])
async def get_customers_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Customers Dashboard endpoint.

    Combines data from:
    - Customer summary (total, active, at-risk)
    - Billing health (outstanding, overdue)
    - Subscription breakdown
    - Recent customers
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    currency = currency or "NGN"

    # =========== CUSTOMER COUNTS ===========
    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.status != CustomerStatus.INACTIVE
    ).scalar() or 0

    # Active (has active subscription or invoice in 30 days)
    active_customers = db.query(func.count(distinct(Subscription.customer_id))).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *([Subscription.currency == currency] if currency else [])
    ).scalar() or 0

    # =========== BILLING HEALTH ===========
    outstanding = db.query(
        func.sum(Invoice.total_amount - Invoice.amount_paid)
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        *([Invoice.currency == currency] if currency else [])
    ).scalar() or 0

    overdue = db.query(
        func.sum(Invoice.total_amount - Invoice.amount_paid)
    ).filter(
        Invoice.status == InvoiceStatus.OVERDUE,
        *([Invoice.currency == currency] if currency else [])
    ).scalar() or 0

    avg_invoice = db.query(
        func.avg(Invoice.total_amount)
    ).filter(
        *([Invoice.currency == currency] if currency else [])
    ).scalar() or 0

    # =========== SUBSCRIPTIONS ===========
    active_subscriptions = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *([Subscription.currency == currency] if currency else [])
    ).scalar() or 0

    # MRR calculation
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )
    mrr = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *([Subscription.currency == currency] if currency else [])
    ).scalar() or 0

    # By plan
    by_plan = db.query(
        Subscription.plan_name,
        func.count(Subscription.id).label("count")
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Subscription.plan_name).order_by(
        func.count(Subscription.id).desc()
    ).limit(5).all()

    plan_breakdown = [
        {"plan": row.plan_name or "Unknown", "count": row.count}
        for row in by_plan
    ]

    # =========== CHURNED (30 days) ===========
    churned_30d = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.CANCELLED,
        Subscription.updated_at >= thirty_days_ago
    ).scalar() or 0

    # =========== RECENT CUSTOMERS ===========
    recent_customers = [
        {
            "id": c.id,
            "name": c.name,
            "customer_name": c.name,
            "territory": None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in db.query(Customer).filter(
            Customer.status != CustomerStatus.INACTIVE
        ).order_by(Customer.created_at.desc()).limit(5).all()
    ]

    return {
        "generated_at": now.isoformat(),
        "currency": currency,

        "summary": {
            "total_customers": total_customers,
            "active": active_customers,
            "churned_30d": churned_30d,
        },

        "billing": {
            "outstanding": float(outstanding),
            "overdue": float(overdue),
            "avg_invoice_value": float(avg_invoice),
        },

        "subscriptions": {
            "active": active_subscriptions,
            "mrr": float(mrr),
            "by_plan": plan_breakdown,
        },

        "recent": recent_customers,
    }
