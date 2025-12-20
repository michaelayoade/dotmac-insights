"""
Contact Analytics Endpoints

Dashboard metrics, distribution analysis, funnel analytics
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactCategory, ContactStatus, LeadQualification
)
from app.auth import Require

router = APIRouter()


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/analytics/dashboard", dependencies=[Depends(Require("contacts:read"))])
def get_contacts_dashboard(
    period_days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """
    Unified contacts dashboard with key metrics.
    """
    now = datetime.utcnow()
    period_start = now - timedelta(days=period_days)
    prev_period_start = period_start - timedelta(days=period_days)

    # Total counts by type
    type_counts = db.query(
        UnifiedContact.contact_type,
        func.count(UnifiedContact.id).label("count"),
    ).group_by(UnifiedContact.contact_type).all()

    type_map = {t.contact_type.value: t.count for t in type_counts}

    # Total by status
    status_counts = db.query(
        UnifiedContact.status,
        func.count(UnifiedContact.id).label("count"),
    ).group_by(UnifiedContact.status).all()

    status_map = {s.status.value: s.count for s in status_counts}

    # MRR and revenue (customers only)
    customer_metrics = db.query(
        func.sum(UnifiedContact.mrr).label("total_mrr"),
        func.sum(UnifiedContact.total_revenue).label("total_revenue"),
        func.sum(UnifiedContact.outstanding_balance).label("total_outstanding"),
        func.avg(UnifiedContact.mrr).label("avg_mrr"),
    ).filter(
        UnifiedContact.contact_type == ContactType.CUSTOMER
    ).first()

    # New contacts this period
    new_this_period = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.created_at >= period_start
    ).scalar() or 0

    new_prev_period = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.created_at >= prev_period_start,
        UnifiedContact.created_at < period_start
    ).scalar() or 0

    # Conversions this period
    conversions_this_period = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.conversion_date >= period_start
    ).scalar() or 0

    conversions_prev_period = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.conversion_date >= prev_period_start,
        UnifiedContact.conversion_date < period_start
    ).scalar() or 0

    # Churn this period
    churned_this_period = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.cancellation_date >= period_start,
        UnifiedContact.contact_type == ContactType.CHURNED
    ).scalar() or 0

    return {
        "overview": {
            "total_contacts": sum(type_map.values()),
            "leads": type_map.get("lead", 0),
            "prospects": type_map.get("prospect", 0),
            "customers": type_map.get("customer", 0),
            "churned": type_map.get("churned", 0),
            "persons": type_map.get("person", 0),
        },
        "status_distribution": {
            "active": status_map.get("active", 0),
            "inactive": status_map.get("inactive", 0),
            "suspended": status_map.get("suspended", 0),
            "do_not_contact": status_map.get("do_not_contact", 0),
        },
        "financials": {
            "total_mrr": float(customer_metrics.total_mrr or 0),
            "total_revenue": float(customer_metrics.total_revenue or 0),
            "total_outstanding": float(customer_metrics.total_outstanding or 0),
            "avg_mrr": float(customer_metrics.avg_mrr or 0),
        },
        "period_metrics": {
            "period_days": period_days,
            "new_contacts": new_this_period,
            "new_contacts_prev": new_prev_period,
            "new_contacts_change": new_this_period - new_prev_period,
            "conversions": conversions_this_period,
            "conversions_prev": conversions_prev_period,
            "conversions_change": conversions_this_period - conversions_prev_period,
            "churned": churned_this_period,
        },
    }


# =============================================================================
# FUNNEL ANALYTICS
# =============================================================================

@router.get("/analytics/funnel", dependencies=[Depends(Require("contacts:read"))])
def get_sales_funnel(
    period_days: int = Query(30, ge=7, le=365),
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Sales funnel analysis showing lead → prospect → customer conversion.
    """
    now = datetime.utcnow()
    period_start = now - timedelta(days=period_days)

    base_query = db.query(UnifiedContact)
    if owner_id:
        base_query = base_query.filter(UnifiedContact.owner_id == owner_id)

    # Leads created in period
    leads_created = base_query.filter(
        UnifiedContact.created_at >= period_start,
        UnifiedContact.contact_type.in_([ContactType.LEAD, ContactType.PROSPECT, ContactType.CUSTOMER])
    ).count()

    # Leads by qualification
    qualification_query = db.query(
        UnifiedContact.lead_qualification,
        func.count(UnifiedContact.id).label("count"),
    ).filter(
        UnifiedContact.contact_type.in_([ContactType.LEAD, ContactType.PROSPECT]),
        UnifiedContact.created_at >= period_start
    )
    if owner_id:
        qualification_query = qualification_query.filter(UnifiedContact.owner_id == owner_id)
    qualification_rows = qualification_query.group_by(UnifiedContact.lead_qualification).all()

    qual_map = {
        (
            row._mapping["lead_qualification"].value
            if row._mapping["lead_qualification"]
            else "unqualified"
        ): int(row._mapping["count"])
        for row in qualification_rows
    }

    # Prospects qualified in period
    prospects_qualified = base_query.filter(
        UnifiedContact.qualified_date >= period_start
    ).count()

    # Customers converted in period
    customers_converted = base_query.filter(
        UnifiedContact.conversion_date >= period_start
    ).count()

    # Calculate conversion rates
    lead_to_prospect_rate = (prospects_qualified / leads_created * 100) if leads_created > 0 else 0
    prospect_to_customer_rate = (customers_converted / prospects_qualified * 100) if prospects_qualified > 0 else 0
    overall_conversion_rate = (customers_converted / leads_created * 100) if leads_created > 0 else 0

    return {
        "period_days": period_days,
        "funnel": {
            "leads_created": leads_created,
            "prospects_qualified": prospects_qualified,
            "customers_converted": customers_converted,
        },
        "qualification_breakdown": {
            "unqualified": qual_map.get("unqualified", 0),
            "cold": qual_map.get("cold", 0),
            "warm": qual_map.get("warm", 0),
            "hot": qual_map.get("hot", 0),
            "qualified": qual_map.get("qualified", 0),
        },
        "conversion_rates": {
            "lead_to_prospect": round(lead_to_prospect_rate, 2),
            "prospect_to_customer": round(prospect_to_customer_rate, 2),
            "overall": round(overall_conversion_rate, 2),
        },
    }


# =============================================================================
# DISTRIBUTION ANALYSIS
# =============================================================================

@router.get("/analytics/by-category", dependencies=[Depends(Require("contacts:read"))])
def get_contacts_by_category(db: Session = Depends(get_db)):
    """
    Contact distribution by category.
    """
    results = db.query(
        UnifiedContact.category,
        UnifiedContact.contact_type,
        func.count(UnifiedContact.id).label("count"),
        func.sum(UnifiedContact.mrr).label("mrr"),
    ).group_by(
        UnifiedContact.category, UnifiedContact.contact_type
    ).all()

    by_category: Dict[str, Dict[str, Any]] = {}
    for r in results:
        cat = r._mapping["category"].value
        if cat not in by_category:
            by_category[cat] = {"total": 0, "mrr": 0, "by_type": {}}
        by_category[cat]["total"] += int(r._mapping["count"])
        by_category[cat]["mrr"] += float(r._mapping["mrr"] or 0)
        by_category[cat]["by_type"][r._mapping["contact_type"].value] = int(r._mapping["count"])

    return {"by_category": by_category}


@router.get("/analytics/by-territory", dependencies=[Depends(Require("contacts:read"))])
def get_contacts_by_territory(
    contact_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Contact distribution by territory.
    """
    query = db.query(
        UnifiedContact.territory,
        func.count(UnifiedContact.id).label("count"),
        func.sum(UnifiedContact.mrr).label("mrr"),
    ).filter(
        UnifiedContact.territory.isnot(None),
        UnifiedContact.territory != ""
    )

    if contact_type:
        query = query.filter(UnifiedContact.contact_type == ContactType(contact_type))

    results = query.group_by(UnifiedContact.territory).order_by(
        func.count(UnifiedContact.id).desc()
    ).limit(limit).all()

    return {
        "territories": [
            {
                "territory": r.territory,
                "count": r.count,
                "mrr": float(r.mrr or 0),
            }
            for r in results
        ]
    }


@router.get("/analytics/by-source", dependencies=[Depends(Require("contacts:read"))])
def get_contacts_by_source(
    period_days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """
    Lead source effectiveness analysis.
    """
    period_start = datetime.utcnow() - timedelta(days=period_days)

    results = db.query(
        UnifiedContact.source,
        func.count(UnifiedContact.id).label("total_leads"),
        func.sum(case((UnifiedContact.conversion_date.isnot(None), 1), else_=0)).label("conversions"),
    ).filter(
        UnifiedContact.created_at >= period_start,
        UnifiedContact.source.isnot(None),
        UnifiedContact.source != ""
    ).group_by(UnifiedContact.source).order_by(
        func.count(UnifiedContact.id).desc()
    ).limit(20).all()

    return {
        "period_days": period_days,
        "sources": [
            {
                "source": r.source,
                "total_leads": r.total_leads,
                "conversions": r.conversions,
                "conversion_rate": round((r.conversions / r.total_leads * 100), 2) if r.total_leads > 0 else 0,
            }
            for r in results
        ]
    }


@router.get("/analytics/by-owner", dependencies=[Depends(Require("contacts:read"))])
def get_contacts_by_owner(
    contact_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Contact distribution by owner/sales person.
    """
    query = db.query(
        UnifiedContact.owner_id,
        func.count(UnifiedContact.id).label("total"),
        func.sum(case((UnifiedContact.contact_type == ContactType.LEAD, 1), else_=0)).label("leads"),
        func.sum(case((UnifiedContact.contact_type == ContactType.PROSPECT, 1), else_=0)).label("prospects"),
        func.sum(case((UnifiedContact.contact_type == ContactType.CUSTOMER, 1), else_=0)).label("customers"),
        func.sum(UnifiedContact.mrr).label("total_mrr"),
    )

    if contact_type:
        query = query.filter(UnifiedContact.contact_type == ContactType(contact_type))

    results = query.group_by(UnifiedContact.owner_id).order_by(
        func.count(UnifiedContact.id).desc()
    ).all()

    return {
        "by_owner": [
            {
                "owner_id": r.owner_id,
                "total": r.total,
                "leads": r.leads,
                "prospects": r.prospects,
                "customers": r.customers,
                "total_mrr": float(r.total_mrr or 0),
            }
            for r in results
        ]
    }


# =============================================================================
# LIFECYCLE ANALYTICS
# =============================================================================

@router.get("/analytics/lifecycle", dependencies=[Depends(Require("contacts:read"))])
def get_lifecycle_analytics(
    period_days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """
    Contact lifecycle duration analytics.
    """
    period_start = datetime.utcnow() - timedelta(days=period_days)

    # Average time from lead to prospect (qualified_date - created_at)
    avg_lead_to_prospect = db.query(
        func.avg(
            extract('epoch', UnifiedContact.qualified_date) - extract('epoch', UnifiedContact.created_at)
        ) / 86400  # Convert to days
    ).filter(
        UnifiedContact.qualified_date.isnot(None),
        UnifiedContact.qualified_date >= period_start
    ).scalar()

    # Average time from prospect to customer (conversion_date - qualified_date)
    avg_prospect_to_customer = db.query(
        func.avg(
            extract('epoch', UnifiedContact.conversion_date) - extract('epoch', UnifiedContact.qualified_date)
        ) / 86400
    ).filter(
        UnifiedContact.conversion_date.isnot(None),
        UnifiedContact.qualified_date.isnot(None),
        UnifiedContact.conversion_date >= period_start
    ).scalar()

    # Average customer lifetime (cancellation_date - conversion_date)
    avg_customer_lifetime = db.query(
        func.avg(
            extract('epoch', UnifiedContact.cancellation_date) - extract('epoch', UnifiedContact.conversion_date)
        ) / 86400
    ).filter(
        UnifiedContact.cancellation_date.isnot(None),
        UnifiedContact.conversion_date.isnot(None),
        UnifiedContact.contact_type == ContactType.CHURNED
    ).scalar()

    # Average time to first contact
    avg_response_time = db.query(
        func.avg(
            extract('epoch', UnifiedContact.last_contact_date) - extract('epoch', UnifiedContact.first_contact_date)
        ) / 86400
    ).filter(
        UnifiedContact.last_contact_date.isnot(None),
        UnifiedContact.first_contact_date.isnot(None),
        UnifiedContact.created_at >= period_start
    ).scalar()

    return {
        "period_days": period_days,
        "avg_lead_to_prospect_days": round(avg_lead_to_prospect or 0, 1),
        "avg_prospect_to_customer_days": round(avg_prospect_to_customer or 0, 1),
        "avg_customer_lifetime_days": round(avg_customer_lifetime or 0, 1),
        "avg_total_sales_cycle_days": round((avg_lead_to_prospect or 0) + (avg_prospect_to_customer or 0), 1),
        "avg_days_between_contacts": round(avg_response_time or 0, 1),
    }


# =============================================================================
# CHURN ANALYSIS
# =============================================================================

@router.get("/analytics/churn", dependencies=[Depends(Require("contacts:read"))])
def get_churn_analytics(
    period_days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """
    Churn analysis and reasons breakdown.
    """
    period_start = datetime.utcnow() - timedelta(days=period_days)

    # Total churned in period
    churned_count = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.cancellation_date >= period_start,
        UnifiedContact.contact_type == ContactType.CHURNED
    ).scalar() or 0

    # Active customers at start of period
    customers_at_start = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.contact_type == ContactType.CUSTOMER,
        UnifiedContact.conversion_date < period_start
    ).scalar() or 0

    # Churn rate
    churn_rate = (churned_count / customers_at_start * 100) if customers_at_start > 0 else 0

    # Churn reasons breakdown
    reasons = db.query(
        UnifiedContact.churn_reason,
        func.count(UnifiedContact.id).label("count"),
    ).filter(
        UnifiedContact.cancellation_date >= period_start,
        UnifiedContact.contact_type == ContactType.CHURNED,
        UnifiedContact.churn_reason.isnot(None)
    ).group_by(UnifiedContact.churn_reason).order_by(
        func.count(UnifiedContact.id).desc()
    ).all()

    # Monthly churn trend
    monthly_churn = db.query(
        extract('year', UnifiedContact.cancellation_date).label("year"),
        extract('month', UnifiedContact.cancellation_date).label("month"),
        func.count(UnifiedContact.id).label("count"),
    ).filter(
        UnifiedContact.cancellation_date >= period_start,
        UnifiedContact.contact_type == ContactType.CHURNED
    ).group_by("year", "month").order_by("year", "month").all()

    return {
        "period_days": period_days,
        "total_churned": churned_count,
        "customers_at_period_start": customers_at_start,
        "churn_rate": round(churn_rate, 2),
        "reasons": [
            {"reason": r.churn_reason, "count": r.count}
            for r in reasons
        ],
        "monthly_trend": [
            {"year": int(m.year), "month": int(m.month), "count": m.count}
            for m in monthly_churn
        ],
    }
