"""
Invoices Read-Only Endpoints (Sales View)

NOTE: For creating/updating/deleting invoices, use the accounting module:
  - POST   /api/v1/accounting/invoices
  - PATCH  /api/v1/accounting/invoices/{id}
  - DELETE /api/v1/accounting/invoices/{id}
  - POST   /api/v1/accounting/invoices/{id}/submit
  - POST   /api/v1/accounting/invoices/{id}/approve
  - POST   /api/v1/accounting/invoices/{id}/post

The accounting module is the single source of truth for invoice writes,
ensuring proper workflow (draft → pending → approved → posted) and GL integration.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, Optional

from app.database import get_db
from app.auth import Require
from app.models.invoice import Invoice, InvoiceStatus
from app.models.customer import Customer
from app.api.sales_pkg.common import (
    _parse_iso_utc,
    _resolve_currency_or_raise,
    _serialize_invoice,
)

router = APIRouter()


@router.get("/invoices", dependencies=[Depends(Require("explorer:read"))])
async def list_invoices(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    overdue_only: bool = False,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="invoice_date,due_date,total_amount,amount_paid,customer_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List invoices with filtering, search, sort, and pagination (single-currency only)."""
    query = db.query(Invoice).filter(Invoice.is_deleted == False)

    if status:
        try:
            status_enum = InvoiceStatus(status)
            query = query.filter(Invoice.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Invoice.invoice_date >= start_dt)

    if end_dt:
        query = query.filter(Invoice.invoice_date <= end_dt)

    if min_amount:
        query = query.filter(Invoice.total_amount >= min_amount)

    if max_amount:
        query = query.filter(Invoice.total_amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    if currency:
        query = query.filter(Invoice.currency == currency)

    if overdue_only:
        query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Invoice.invoice_number.ilike(like), Invoice.description.ilike(like)))

    sort_map = {
        "invoice_date": Invoice.invoice_date,
        "due_date": Invoice.due_date,
        "total_amount": Invoice.total_amount,
        "amount_paid": Invoice.amount_paid,
        "customer_id": Invoice.customer_id,
        "status": Invoice.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "invoice_date")
    if sort_column is None:
        sort_column = Invoice.invoice_date
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    invoice_rows = (
        query.outerjoin(Customer, Invoice.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, Invoice.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "customer_name": customer_name,
                "total_amount": float(inv.total_amount),
                "amount_paid": float(inv.amount_paid or 0),
                "balance": float(inv.total_amount - (inv.amount_paid or 0)),
                "currency": inv.currency,
                "status": inv.status.value if inv.status else None,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
                "source": inv.source.value if inv.source else None,
            }
            for inv, customer_name in invoice_rows
        ],
    }


@router.get("/invoices/{invoice_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed invoice information."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _serialize_invoice(invoice, db)
