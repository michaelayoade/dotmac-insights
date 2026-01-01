"""
Sales Dashboard Endpoints
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
from app.api.dashboards.common import resolve_currency_or_raise, parse_date_param

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.customer import Customer, CustomerStatus
from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier, GLEntry, Account, AccountType, BankAccount
from app.models.sales import ERPNextLead, ERPNextLeadStatus
from app.models.crm import Opportunity, OpportunityStatus, OpportunityStage, Activity, ActivityType, ActivityStatus

router = APIRouter(tags=["dashboards"])

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
    currency = resolve_currency_or_raise(db, Subscription.currency, currency) or "NGN"
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
# LEADS DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/leads", dependencies=[Depends(Require("crm:read"))])
@cached("dashboard-leads", ttl=CACHE_TTL["short"])
async def get_leads_dashboard(
    status: Optional[str] = Query(default=None, description="Filter by lead status"),
    source: Optional[str] = Query(default=None, description="Filter by lead source"),
    limit: int = Query(default=50, ge=1, le=100, description="Number of leads to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Leads Dashboard endpoint.

    Combines data from:
    - Leads summary (total, by status)
    - Lead sources breakdown
    - Leads list with pagination
    - Recent conversions
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # =========== LEADS SUMMARY ===========
    total_leads = db.query(func.count(ERPNextLead.id)).scalar() or 0

    # By status
    status_counts = {}
    for row in db.query(
        ERPNextLead.status,
        func.count(ERPNextLead.id).label("count")
    ).group_by(ERPNextLead.status).all():
        status_counts[row.status.value if row.status else "unknown"] = row.count

    # New leads (last 30 days)
    new_leads_count = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.created_at >= thirty_days_ago
    ).scalar() or 0

    # Converted leads (last 30 days)
    converted_count = db.query(func.count(ERPNextLead.id)).filter(
        ERPNextLead.converted == True,
        ERPNextLead.updated_at >= thirty_days_ago
    ).scalar() or 0

    # =========== SOURCES ===========
    sources = []
    for source_row in db.query(
        ERPNextLead.source,
        func.count(ERPNextLead.id).label("count")
    ).filter(
        ERPNextLead.source.isnot(None)
    ).group_by(ERPNextLead.source).order_by(
        func.count(ERPNextLead.id).desc()
    ).limit(10).all():
        sources.append({
            "source": source_row.source,
            "count": source_row.count,
        })

    # =========== LEADS LIST ===========
    leads_query = db.query(ERPNextLead)

    # Apply filters
    if status:
        try:
            status_enum = ERPNextLeadStatus(status)
            leads_query = leads_query.filter(ERPNextLead.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter

    if source:
        leads_query = leads_query.filter(ERPNextLead.source == source)

    # Get total for pagination
    total_filtered = leads_query.count()

    # Get paginated leads
    leads_list = []
    for lead in leads_query.order_by(
        ERPNextLead.created_at.desc()
    ).offset(offset).limit(limit).all():
        leads_list.append({
            "id": lead.id,
            "lead_name": lead.lead_name,
            "company_name": lead.company_name,
            "email_id": lead.email_id,
            "phone": lead.phone or lead.mobile_no,
            "source": lead.source,
            "status": lead.status.value if lead.status else None,
            "lead_owner": lead.lead_owner,
            "territory": lead.territory,
            "industry": lead.industry,
            "city": lead.city,
            "state": lead.state,
            "converted": lead.converted,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        })

    # =========== RECENT CONVERSIONS ===========
    recent_conversions = []
    for lead in db.query(ERPNextLead).filter(
        ERPNextLead.converted == True
    ).order_by(ERPNextLead.updated_at.desc()).limit(5).all():
        recent_conversions.append({
            "id": lead.id,
            "lead_name": lead.lead_name,
            "company_name": lead.company_name,
            "source": lead.source,
            "converted_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "customer_id": lead.customer_id,
        })

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total": total_leads,
            "new_30d": new_leads_count,
            "converted_30d": converted_count,
            "by_status": status_counts,
        },

        "sources": sources,

        "leads": {
            "items": leads_list,
            "total": total_filtered,
            "limit": limit,
            "offset": offset,
        },

        "recent_conversions": recent_conversions,
    }
# =============================================================================
# CRM PIPELINE DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/crm-pipeline", dependencies=[Depends(Require("crm:read"))])
@cached("dashboard-crm-pipeline", ttl=CACHE_TTL["short"])
async def get_crm_pipeline_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated CRM Pipeline Dashboard endpoint.

    Combines data from:
    - Pipeline summary (open count, total value, weighted value, win rate)
    - Pipeline stages with opportunities
    - Kanban board view (opportunities by stage)
    - Recent activities
    """
    now = datetime.now(timezone.utc)
    currency = currency or "NGN"

    # =========== PIPELINE SUMMARY ===========
    # Open opportunities
    open_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.OPEN,
        *([Opportunity.currency == currency] if currency else [])
    ).scalar() or 0

    # Total value of open opportunities
    total_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.status == OpportunityStatus.OPEN,
        *([Opportunity.currency == currency] if currency else [])
    ).scalar() or 0

    # Weighted value
    weighted_value = db.query(func.sum(Opportunity.weighted_value)).filter(
        Opportunity.status == OpportunityStatus.OPEN,
        *([Opportunity.currency == currency] if currency else [])
    ).scalar() or 0

    # Won/Lost counts
    won_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.WON,
        *([Opportunity.currency == currency] if currency else [])
    ).scalar() or 0

    lost_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.LOST,
        *([Opportunity.currency == currency] if currency else [])
    ).scalar() or 0

    # Win rate
    total_closed = won_count + lost_count
    win_rate = round((won_count / total_closed * 100), 1) if total_closed > 0 else 0

    # =========== PIPELINE STAGES ===========
    stage_rows: list[dict[str, Any]] = []
    for stage in db.query(OpportunityStage).filter(
        OpportunityStage.is_active == True
    ).order_by(OpportunityStage.sequence).all():
        # Count opportunities in this stage
        stage_opps = db.query(
            func.count(Opportunity.id).label("count"),
            func.sum(Opportunity.deal_value).label("value"),
        ).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN,
            *([Opportunity.currency == currency] if currency else [])
        ).first()

        stage_rows.append({
            "id": stage.id,
            "name": stage.name,
            "sequence": stage.sequence,
            "probability": stage.probability,
            "is_won": stage.is_won,
            "is_lost": stage.is_lost,
            "color": stage.color,
            "opportunity_count": stage_opps.count if stage_opps else 0,
            "opportunity_value": float(stage_opps.value or 0) if stage_opps else 0,
        })

    # =========== KANBAN BOARD ===========
    kanban_columns: list[dict[str, Any]] = []
    for stage_row in stage_rows:
        # Get opportunities for this stage
        opportunities = db.query(Opportunity).filter(
            Opportunity.stage_id == stage_row["id"],
            Opportunity.status == OpportunityStatus.OPEN,
            *([Opportunity.currency == currency] if currency else [])
        ).order_by(Opportunity.deal_value.desc()).limit(20).all()

        cards: list[dict[str, Any]] = []
        for opp in opportunities:
            # Get contact name
            contact_name = None
            if opp.unified_contact:
                contact_name = opp.unified_contact.full_name
            elif opp.customer:
                contact_name = opp.customer.name
            elif opp.lead:
                contact_name = opp.lead.lead_name

            # Get owner name
            owner_name = None
            if opp.owner:
                owner_name = opp.owner.name

            cards.append({
                "id": opp.id,
                "title": opp.name,
                "subtitle": contact_name,
                "value": float(opp.deal_value),
                "currency": opp.currency,
                "probability": opp.probability,
                "expected_close_date": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                "owner_name": owner_name,
                "owner_id": opp.owner_id,
                "days_in_stage": None,  # Would need stage change tracking
            })

        kanban_columns.append({
            "id": str(stage_row["id"]),
            "title": stage_row["name"],
            "color": stage_row["color"] or "default",
            "count": stage_row["opportunity_count"],
            "value": stage_row["opportunity_value"],
            "cards": cards,
        })

    # =========== RECENT ACTIVITIES ===========
    recent_activities = []
    for activity in db.query(Activity).filter(
        Activity.opportunity_id.isnot(None),
        Activity.status != ActivityStatus.CANCELLED
    ).order_by(Activity.scheduled_at.desc().nullslast()).limit(10).all():
        # Get opportunity name
        opp_name = None
        if activity.opportunity:
            opp_name = activity.opportunity.name

        recent_activities.append({
            "id": activity.id,
            "activity_type": activity.activity_type.value if activity.activity_type else None,
            "subject": activity.subject,
            "status": activity.status.value if activity.status else None,
            "scheduled_at": activity.scheduled_at.isoformat() if activity.scheduled_at else None,
            "priority": activity.priority,
            "opportunity_id": activity.opportunity_id,
            "opportunity_name": opp_name,
        })

    return {
        "generated_at": now.isoformat(),
        "currency": currency,

        "summary": {
            "open_count": open_count,
            "total_value": float(total_value),
            "weighted_value": float(weighted_value),
            "win_rate": win_rate,
            "won_count": won_count,
            "lost_count": lost_count,
        },

        "stages": stage_rows,

        "kanban": {
            "columns": kanban_columns,
        },

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

