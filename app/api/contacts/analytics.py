"""
Contact Analytics Endpoints

Dashboard metrics, distribution analysis, funnel analytics
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import csv
import io

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


# =============================================================================
# TAGS ANALYTICS
# =============================================================================

@router.get("/analytics/tags", dependencies=[Depends(Require("contacts:read"))])
def get_tags_analytics(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Tag usage analytics across all contacts.
    Returns tag counts aggregated from the tags array field.
    """
    # Get all contacts with tags
    contacts_with_tags = db.query(UnifiedContact).filter(
        UnifiedContact.tags.isnot(None),
        func.array_length(UnifiedContact.tags, 1) > 0
    ).all()

    # Aggregate tags
    tag_counts: Dict[str, int] = {}
    total_tagged = 0
    total_tag_assignments = 0

    for contact in contacts_with_tags:
        if contact.tags:
            total_tagged += 1
            for tag in contact.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                total_tag_assignments += 1

    # Sort by count and limit
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    total_contacts = db.query(func.count(UnifiedContact.id)).scalar() or 0

    return {
        "total_unique_tags": len(tag_counts),
        "total_contacts": total_contacts,
        "total_tagged_contacts": total_tagged,
        "total_tag_assignments": total_tag_assignments,
        "avg_tags_per_contact": round(total_tag_assignments / total_tagged, 2) if total_tagged > 0 else 0,
        "tags": [
            {"tag": tag, "count": count}
            for tag, count in sorted_tags
        ],
    }


# =============================================================================
# DATA QUALITY ANALYTICS
# =============================================================================

@router.get("/analytics/quality", dependencies=[Depends(Require("contacts:read"))])
def get_quality_analytics(db: Session = Depends(get_db)):
    """
    Data quality analysis for contacts.
    Returns counts of missing/invalid fields and quality score.
    """
    total = db.query(func.count(UnifiedContact.id)).scalar() or 0

    if total == 0:
        return {
            "total_contacts": 0,
            "quality_score": 100,
            "complete_contacts": 0,
            "completeness_rate": 100,
            "issues": [],
        }

    # Count missing fields
    missing_email = db.query(func.count(UnifiedContact.id)).filter(
        (UnifiedContact.email.is_(None)) | (UnifiedContact.email == "")
    ).scalar() or 0

    missing_phone = db.query(func.count(UnifiedContact.id)).filter(
        (UnifiedContact.phone.is_(None)) | (UnifiedContact.phone == "")
    ).scalar() or 0

    missing_address = db.query(func.count(UnifiedContact.id)).filter(
        (UnifiedContact.city.is_(None)) | (UnifiedContact.city == ""),
        (UnifiedContact.address_line1.is_(None)) | (UnifiedContact.address_line1 == "")
    ).scalar() or 0

    missing_company = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.is_organization == True,
        (UnifiedContact.company_name.is_(None)) | (UnifiedContact.company_name == "")
    ).scalar() or 0

    missing_territory = db.query(func.count(UnifiedContact.id)).filter(
        (UnifiedContact.territory.is_(None)) | (UnifiedContact.territory == "")
    ).scalar() or 0

    missing_category = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.category.is_(None)
    ).scalar() or 0

    no_tags = db.query(func.count(UnifiedContact.id)).filter(
        (UnifiedContact.tags.is_(None)) | (func.array_length(UnifiedContact.tags, 1).is_(None))
    ).scalar() or 0

    # Invalid email (simple check - missing @)
    invalid_email = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.email.isnot(None),
        UnifiedContact.email != "",
        ~UnifiedContact.email.contains("@")
    ).scalar() or 0

    # Complete contacts (have email, phone, and address)
    complete = db.query(func.count(UnifiedContact.id)).filter(
        UnifiedContact.email.isnot(None),
        UnifiedContact.email != "",
        UnifiedContact.phone.isnot(None),
        UnifiedContact.phone != "",
        ((UnifiedContact.city.isnot(None) & (UnifiedContact.city != "")) |
         (UnifiedContact.address_line1.isnot(None) & (UnifiedContact.address_line1 != "")))
    ).scalar() or 0

    # Build issues list
    issues = []
    if missing_email > 0:
        issues.append({
            "field": "email",
            "label": "Missing Email",
            "count": missing_email,
            "percentage": round(missing_email / total * 100, 1),
            "severity": "high"
        })
    if invalid_email > 0:
        issues.append({
            "field": "invalid_email",
            "label": "Invalid Email Format",
            "count": invalid_email,
            "percentage": round(invalid_email / total * 100, 1),
            "severity": "high"
        })
    if missing_phone > 0:
        issues.append({
            "field": "phone",
            "label": "Missing Phone",
            "count": missing_phone,
            "percentage": round(missing_phone / total * 100, 1),
            "severity": "medium"
        })
    if missing_company > 0:
        issues.append({
            "field": "company",
            "label": "Missing Company Name",
            "count": missing_company,
            "percentage": round(missing_company / total * 100, 1),
            "severity": "medium"
        })
    if missing_address > 0:
        issues.append({
            "field": "address",
            "label": "Missing Address",
            "count": missing_address,
            "percentage": round(missing_address / total * 100, 1),
            "severity": "low"
        })
    if missing_territory > 0:
        issues.append({
            "field": "territory",
            "label": "No Territory Assigned",
            "count": missing_territory,
            "percentage": round(missing_territory / total * 100, 1),
            "severity": "low"
        })
    if missing_category > 0:
        issues.append({
            "field": "category",
            "label": "No Category Set",
            "count": missing_category,
            "percentage": round(missing_category / total * 100, 1),
            "severity": "low"
        })
    if no_tags > 0:
        issues.append({
            "field": "tags",
            "label": "No Tags",
            "count": no_tags,
            "percentage": round(no_tags / total * 100, 1),
            "severity": "low"
        })

    # Calculate quality score (weighted penalties)
    penalty = 0
    for issue in issues:
        weight = 3 if issue["severity"] == "high" else 2 if issue["severity"] == "medium" else 1
        penalty += (issue["count"] / total) * weight * 10

    quality_score = max(0, round(100 - penalty))
    completeness_rate = round(complete / total * 100, 1) if total > 0 else 100

    return {
        "total_contacts": total,
        "quality_score": quality_score,
        "complete_contacts": complete,
        "completeness_rate": completeness_rate,
        "issues": issues,
    }


# =============================================================================
# EXPORT
# =============================================================================

EXPORT_FIELDS = [
    "id", "name", "email", "phone", "mobile", "company_name",
    "contact_type", "category", "status", "is_organization",
    "lead_qualification", "lead_score",
    "address_line1", "address_line2", "city", "state", "postal_code", "country",
    "territory", "industry", "market_segment", "tags",
    "mrr", "lifetime_value", "outstanding_balance", "billing_type",
    "source", "source_campaign", "referrer",
    "first_contact_date", "conversion_date", "cancellation_date",
    "created_at", "updated_at", "notes",
]


@router.get("/export", dependencies=[Depends(Require("contacts:read"))])
def export_contacts(
    format: str = Query("csv", pattern="^(csv|json)$"),
    contact_type: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    fields: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Export contacts to CSV or JSON format.

    Args:
        format: Export format (csv or json)
        contact_type: Filter by contact type
        category: Filter by category
        status: Filter by status
        fields: Comma-separated list of fields to include (default: all)
    """
    query = db.query(UnifiedContact)

    if contact_type:
        query = query.filter(UnifiedContact.contact_type == ContactType(contact_type))
    if category:
        query = query.filter(UnifiedContact.category == ContactCategory(category))
    if status:
        query = query.filter(UnifiedContact.status == ContactStatus(status))

    contacts = query.all()

    # Determine fields to export
    if fields:
        export_fields = [f.strip() for f in fields.split(",") if f.strip() in EXPORT_FIELDS]
    else:
        export_fields = EXPORT_FIELDS

    def format_value(contact, field):
        """Format a field value for export."""
        value = getattr(contact, field, None)
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return "; ".join(str(v) for v in value)
        if hasattr(value, "value"):  # Enum
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    if format == "json":
        import json
        data = [
            {field: format_value(c, field) for field in export_fields}
            for c in contacts
        ]
        content = json.dumps(data, indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=contacts_export_{datetime.utcnow().strftime('%Y%m%d')}.json"}
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(export_fields)
        for contact in contacts:
            writer.writerow([format_value(contact, field) for field in export_fields])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=contacts_export_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
