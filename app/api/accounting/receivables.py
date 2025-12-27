"""Accounts Receivable: AR aging, outstanding receivables."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional, List, TypedDict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload

from app.auth import Require
from app.database import get_db
from app.models.customer import Customer
from app.models.contact import Contact
from app.models.invoice import Invoice, InvoiceStatus

# Helper to get contact or customer name
def _get_contact_or_customer_name(inv) -> str:
    """Get name from contact (preferred) or customer (legacy)."""
    if inv.contact:
        return inv.contact.display_name or inv.contact.name or "Unknown"
    if inv.customer:
        return inv.customer.name
    return "Unknown"

from .helpers import parse_date, resolve_currency_or_raise
from app.cache import cached

router = APIRouter()


class AgingBucket(TypedDict):
    count: int
    total: Decimal
    invoices: List[Dict[str, Any]]


# =============================================================================
# ACCOUNTS RECEIVABLE AGING
# =============================================================================

@router.get("/accounts-receivable", dependencies=[Depends(Require("accounting:read"))])
def get_accounts_receivable(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts receivable aging report.

    Shows outstanding customer invoices by age bucket.

    Args:
        as_of_date: Calculate aging as of this date (default: today)
        customer_id: Filter by legacy customer (deprecated)
        contact_id: Filter by CRM contact (preferred)
        currency: Currency filter

    Returns:
        AR aging with buckets (current, 1-30, 31-60, 61-90, 90+)
    """
    cutoff = parse_date(as_of_date, "as_of_date") or date.today()
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    query = db.query(Invoice).options(
        joinedload(Invoice.customer),
        joinedload(Invoice.contact),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
    )

    if contact_id:
        query = query.filter(Invoice.contact_id == contact_id)
    elif customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if currency:
        query = query.filter(Invoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets: Dict[str, AgingBucket] = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else inv.invoice_date.date()
        days_overdue = (cutoff - due).days if cutoff > due else 0
        outstanding = inv.total_amount - inv.amount_paid

        if outstanding <= 0:
            continue

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += outstanding
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.invoice_number,
            "contact_id": inv.contact_id,
            "contact_name": _get_contact_or_customer_name(inv),
            "customer_id": inv.customer_id,  # legacy
            "customer_name": inv.customer.name if inv.customer else None,  # legacy
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "total_amount": float(inv.total_amount),
            "amount_paid": float(inv.amount_paid),
            "outstanding": float(outstanding),
            "days_overdue": days_overdue,
        })

    buckets_response: Dict[str, Dict[str, Any]] = {
        key: {**value, "total": float(value["total"])} for key, value in buckets.items()
    }
    total_receivable = sum(b["total"] for b in buckets_response.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_receivable": total_receivable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets_response,
    }


# Alias
@router.get("/receivables-aging", dependencies=[Depends(Require("accounting:read"))])
def get_receivables_aging(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for /accounts-receivable - AR aging report."""
    return get_accounts_receivable(as_of_date, customer_id, contact_id, currency, db)


# =============================================================================
# OUTSTANDING RECEIVABLES
# =============================================================================

@router.get("/receivables-outstanding", dependencies=[Depends(Require("accounting:read"))])
def get_receivables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Outstanding receivables with top contacts/customers.

    Args:
        currency: Currency filter
        top: Number of top contacts to return

    Returns:
        Outstanding receivables summary with top contacts
    """
    as_of = date.today()
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    inv_query = db.query(
        func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
        func.count(Invoice.id).label("invoice_count"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    if currency:
        inv_query = inv_query.filter(Invoice.currency == currency)
    inv_totals = inv_query.first()
    total_outstanding = float(inv_totals.outstanding or 0) if inv_totals else 0.0
    total_invoices = int(inv_totals.invoice_count or 0) if inv_totals else 0

    # Query by contact (preferred) with fallback to customer (legacy)
    inv_by_contact_query = (
        db.query(
            Invoice.contact_id,
            Contact.name.label("contact_name"),
            func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
        )
        .outerjoin(Contact, Contact.id == Invoice.contact_id)
        .filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.contact_id.isnot(None),
        )
    )
    if currency:
        inv_by_contact_query = inv_by_contact_query.filter(Invoice.currency == currency)
    inv_by_contact = (
        inv_by_contact_query.group_by(Invoice.contact_id, Contact.name)
        .order_by(func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).desc())
        .limit(top)
        .all()
    )

    # Also get legacy customer data for invoices without contact_id
    inv_by_customer_query = (
        db.query(
            Invoice.customer_id,
            Customer.name.label("customer_name"),
            func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
        )
        .outerjoin(Customer, Customer.id == Invoice.customer_id)
        .filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.contact_id.is_(None),
        )
    )
    if currency:
        inv_by_customer_query = inv_by_customer_query.filter(Invoice.currency == currency)
    inv_by_customer = (
        inv_by_customer_query.group_by(Invoice.customer_id, Customer.name)
        .order_by(func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).desc())
        .limit(top)
        .all()
    )

    # Combine and return top contacts/customers
    top_entities = []
    for row in inv_by_contact:
        top_entities.append({
            "contact_id": row.contact_id,
            "contact_name": row.contact_name,
            "customer_id": None,
            "customer_name": None,
            "outstanding": float(row.outstanding),
        })
    for row in inv_by_customer:
        top_entities.append({
            "contact_id": None,
            "contact_name": None,
            "customer_id": row.customer_id,
            "customer_name": row.customer_name,
            "outstanding": float(row.outstanding),
        })

    # Sort combined and take top N
    top_entities.sort(key=lambda x: x["outstanding"], reverse=True)
    top_entities = top_entities[:top]

    return {
        "as_of_date": as_of.isoformat(),
        "currency": currency,
        "total_outstanding": total_outstanding,
        "total_invoices": total_invoices,
        "top_contacts": top_entities,
        "top_customers": top_entities,  # legacy alias
    }


@router.get("/receivables-aging-enhanced", dependencies=[Depends(Require("accounting:read"))])
@cached("receivables-aging-enhanced", ttl=60)
async def get_receivables_aging_enhanced(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_amount: Optional[float] = Query(None, description="Minimum outstanding amount"),
    search: Optional[str] = Query(None, description="Search by contact/customer name"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Enhanced receivables aging grouped by contact/customer (matches frontend expectations)."""
    cutoff = date.today()
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer), joinedload(Invoice.contact))
        .filter(
            and_(
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
                Invoice.is_deleted == False,  # noqa: E712
                Invoice.invoice_date <= cutoff,
            )
        )
    )

    if currency:
        query = query.filter(Invoice.currency == currency)

    invoices = query.all()

    # Aggregations
    totals = {
        "current": Decimal("0"),
        "1_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "over_90": Decimal("0"),
    }
    # Use composite key: (contact_id, customer_id) to handle both new and legacy data
    entities: Dict[tuple, Dict[str, Any]] = {}

    for inv in invoices:
        outstanding = Decimal(inv.balance or (inv.total_amount - (inv.amount_paid or 0)))
        if outstanding <= 0:
            continue

        due = inv.due_date.date() if inv.due_date else inv.invoice_date.date()
        days_overdue = (cutoff - due).days if cutoff > due else 0
        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        # Prefer contact_id, fallback to customer_id
        contact_id = inv.contact_id
        customer_id = inv.customer_id or 0
        entity_key = (contact_id, customer_id if not contact_id else None)
        entity_name = _get_contact_or_customer_name(inv)

        if entity_key not in entities:
            entities[entity_key] = {
                "contact_id": contact_id,
                "contact_name": inv.contact.display_name if inv.contact else None,
                "customer_id": customer_id if not contact_id else None,
                "customer_name": inv.customer.name if inv.customer and not contact_id else None,
                "name": entity_name,  # unified name field
                "total_receivable": Decimal("0"),
                "current": Decimal("0"),
                "overdue_1_30": Decimal("0"),
                "overdue_31_60": Decimal("0"),
                "overdue_61_90": Decimal("0"),
                "overdue_over_90": Decimal("0"),
                "invoice_count": 0,
                "oldest_invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            }

        ent = entities[entity_key]
        ent["total_receivable"] += outstanding
        ent["invoice_count"] += 1
        if ent["oldest_invoice_date"] is None and inv.invoice_date:
            ent["oldest_invoice_date"] = inv.invoice_date.isoformat()
        if bucket == "current":
            ent["current"] += outstanding
        elif bucket == "1_30":
            ent["overdue_1_30"] += outstanding
        elif bucket == "31_60":
            ent["overdue_31_60"] += outstanding
        elif bucket == "61_90":
            ent["overdue_61_90"] += outstanding
        else:
            ent["overdue_over_90"] += outstanding

        totals[bucket] += outstanding

    entity_list = list(entities.values())

    # Apply search/min_amount filters (search both contact and customer names)
    if search:
        search_lower = search.lower()
        entity_list = [
            e for e in entity_list
            if search_lower in (e["name"] or "").lower()
        ]
    if min_amount:
        entity_list = [e for e in entity_list if float(e["total_receivable"]) >= min_amount]

    entity_list.sort(key=lambda e: e["total_receivable"], reverse=True)
    total_count = len(entity_list)
    paged = entity_list[offset : offset + limit]

    # Convert Decimals to float for response
    def to_float(val: Decimal) -> float:
        return float(val or 0)

    paged = [
        {
            **e,
            "total_receivable": to_float(e["total_receivable"]),
            "current": to_float(e["current"]),
            "overdue_1_30": to_float(e["overdue_1_30"]),
            "overdue_31_60": to_float(e["overdue_31_60"]),
            "overdue_61_90": to_float(e["overdue_61_90"]),
            "overdue_over_90": to_float(e["overdue_over_90"]),
        }
        for e in paged
    ]

    return {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "total_receivable": to_float(sum(totals.values(), Decimal("0"))),
        "aging": {
            "current": to_float(totals["current"]),
            "1_30": to_float(totals["1_30"]),
            "31_60": to_float(totals["31_60"]),
            "61_90": to_float(totals["61_90"]),
            "over_90": to_float(totals["over_90"]),
        },
        "contacts": paged,
        "customers": paged,  # legacy alias
    }
