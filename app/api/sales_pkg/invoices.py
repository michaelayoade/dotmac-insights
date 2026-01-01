"""
Invoices Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import Dict, Any, Optional, List, cast
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup, 
    Territory, SalesPerson
)
from app.api.sales_pkg.common import (
    Principal,
    InvoiceCreateRequest,
    InvoiceUpdateRequest,
    InvoiceSource,
    _ensure_utc,
    _parse_invoice_status,
    _parse_iso_utc,
    _resolve_currency_or_raise,
    _serialize_invoice,
    get_company_context,
    get_current_principal,
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
    query = db.query(Invoice)

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
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _serialize_invoice(invoice, db)


@router.delete("/invoices/{invoice_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete an invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.is_deleted = True
    invoice.deleted_at = datetime.now(timezone.utc)
    invoice.deleted_by_id = principal.id
    db.commit()
    return {"status": "disabled", "invoice_id": invoice_id}


@router.post("/invoices", dependencies=[Depends(Require("sales:write"))])
async def create_invoice(
    payload: InvoiceCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new invoice stored locally (not pushed upstream)."""
    if payload.customer_id:
        customer_exists = db.query(Customer.id).filter(Customer.id == payload.customer_id).first()
        if not customer_exists:
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")

    status = _parse_invoice_status(payload.status) or InvoiceStatus.PENDING
    total_amount = payload.amount + payload.tax_amount
    balance = total_amount - (payload.amount_paid or Decimal("0"))

    invoice = Invoice(
        source=InvoiceSource.ERPNEXT,
        customer_id=payload.customer_id,
        invoice_number=payload.invoice_number,
        description=payload.description,
        amount=payload.amount,
        tax_amount=payload.tax_amount,
        total_amount=total_amount,
        amount_paid=payload.amount_paid,
        balance=balance,
        currency=payload.currency,
        status=status,
        invoice_date=_ensure_utc(payload.invoice_date),
        due_date=_ensure_utc(payload.due_date),
        paid_date=_ensure_utc(payload.paid_date),
        category=payload.category,
        company=get_company_context(allow_null=True),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return _serialize_invoice(invoice, db)


@router.patch("/invoices/{invoice_id}", dependencies=[Depends(Require("sales:write"))])
async def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing invoice stored locally."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if payload.customer_id is not None:
        customer_exists = db.query(Customer.id).filter(Customer.id == payload.customer_id).first()
        if not customer_exists:
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        invoice.customer_id = payload.customer_id

    if payload.invoice_number is not None:
        invoice.invoice_number = payload.invoice_number
    if payload.description is not None:
        invoice.description = payload.description
    if payload.amount is not None:
        invoice.amount = payload.amount
    if payload.tax_amount is not None:
        invoice.tax_amount = payload.tax_amount
    if payload.amount_paid is not None:
        invoice.amount_paid = payload.amount_paid
    if payload.currency is not None:
        invoice.currency = payload.currency
    if payload.status is not None:
        invoice.status = _parse_invoice_status(payload.status) or invoice.status
    if payload.invoice_date is not None:
        invoice.invoice_date = cast(datetime, _ensure_utc(payload.invoice_date))
    if payload.due_date is not None:
        invoice.due_date = _ensure_utc(payload.due_date)
    if payload.paid_date is not None:
        invoice.paid_date = _ensure_utc(payload.paid_date)
    if payload.category is not None:
        invoice.category = payload.category

    # Recalculate totals if any amount fields changed
    if any(field is not None for field in [payload.amount, payload.tax_amount, payload.total_amount]):
        invoice.total_amount = payload.total_amount if payload.total_amount is not None else invoice.amount + (invoice.tax_amount or Decimal("0"))

    invoice.balance = invoice.total_amount - (invoice.amount_paid or Decimal("0"))

    db.commit()
    db.refresh(invoice)

    return _serialize_invoice(invoice, db)


@router.post("/invoices/{invoice_id}/post", dependencies=[Depends(Require("billing:write"))])
async def post_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("billing:write")),
) -> Dict[str, Any]:
    """Post invoice to GL - creates AR debit, revenue credit."""
    from app.services.document_posting import DocumentPostingService, PostingError
    from app.services.billing_outbound_sync import BillingOutboundSyncService
    from app.api.accounting.helpers import invalidate_report_cache

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check workflow/docstatus (only post draft invoices)
    if invoice.docstatus != 0:
        raise HTTPException(status_code=400, detail="Invoice already posted or cancelled")

    posting_service = DocumentPostingService(db)
    try:
        # post_invoice requires (invoice_id, user_id, posting_date=None)
        je = posting_service.post_invoice(invoice_id, user.id)
        invoice.docstatus = 1
        invoice.journal_entry_id = je.id
        db.commit()
        db.refresh(invoice)  # ensure returned data reflects DB state
    except PostingError as e:
        db.rollback()
        # PostingError contains safe validation messages (not internal details)
        raise HTTPException(status_code=400, detail=f"Posting failed: {e.args[0] if e.args else 'validation error'}")
    except Exception:
        db.rollback()
        raise  # let FastAPI handle unexpected errors

    await invalidate_report_cache()

    # Trigger outbound sync to ERPNext (if enabled via feature flag)
    sync_service = BillingOutboundSyncService(db)
    sync_service.sync_invoice_to_erpnext(invoice)
    db.commit()  # persist sync log

    return {
        "message": "Invoice posted",
        "invoice_id": invoice.id,
        "journal_entry_id": je.id,
        "docstatus": invoice.docstatus,
    }

