"""
Payments Read-Only Endpoints

NOTE: For creating/updating/deleting payments, use the accounting module:
  - POST   /api/v1/accounting/ar-payments
  - PATCH  /api/v1/accounting/ar-payments/{id}
  - DELETE /api/v1/accounting/ar-payments/{id}

The accounting module is the single source of truth for payment writes,
ensuring proper workflow (pending → approved → posted) and GL integration.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, Optional

from app.database import get_db
from app.auth import Require
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.party import CustomerAccount, Party
from app.api.sales_pkg.common import (
    PaymentMethod,
    _parse_iso_utc,
    _resolve_currency_or_raise,
)

router = APIRouter()


@router.get("/payments", dependencies=[Depends(Require("explorer:read"))])
async def list_payments(
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    customer_account_id: Optional[int] = None,
    party_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="payment_date,amount,customer_account_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payments with filtering, search, sort, and pagination (single-currency only)."""
    query = db.query(Payment).filter(Payment.is_deleted == False)

    if status:
        try:
            status_enum = PaymentStatus(status)
            query = query.filter(Payment.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if payment_method:
        try:
            method_enum = PaymentMethod(payment_method)
            query = query.filter(Payment.payment_method == method_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment_method: {payment_method}")

    if customer_account_id:
        query = query.filter(Payment.customer_account_id == customer_account_id)
    elif party_id:
        query = query.join(
            CustomerAccount,
            CustomerAccount.id == Payment.customer_account_id,
        ).filter(CustomerAccount.party_id == party_id)

    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Payment.payment_date >= start_dt)

    if end_dt:
        query = query.filter(Payment.payment_date <= end_dt)

    if min_amount:
        query = query.filter(Payment.amount >= min_amount)

    if max_amount:
        query = query.filter(Payment.amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    if currency:
        query = query.filter(Payment.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Payment.receipt_number.ilike(like),
                Payment.transaction_reference.ilike(like),
                Payment.gateway_reference.ilike(like),
                Payment.notes.ilike(like),
            )
        )

    sort_map = {
        "payment_date": Payment.payment_date,
        "amount": Payment.amount,
        "customer_account_id": Payment.customer_account_id,
        "invoice_id": Payment.invoice_id,
        "status": Payment.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "payment_date")
    if sort_column is None:
        sort_column = Payment.payment_date
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    payment_rows = (
        query.outerjoin(CustomerAccount, Payment.customer_account_id == CustomerAccount.id)
        .outerjoin(Party, CustomerAccount.party_id == Party.id)
        .add_columns(Party.name.label("party_name"), CustomerAccount.party_id.label("party_id"))
        .order_by(order_clause, Payment.id.desc())
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
                "id": p.id,
                "receipt_number": p.receipt_number,
                "customer_account_id": p.customer_account_id,
                "party_id": party_id,
                "party_name": party_name,
                "invoice_id": p.invoice_id,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "transaction_reference": p.transaction_reference,
                "gateway_reference": p.gateway_reference,
                "notes": p.notes,
                "source": p.source.value if p.source else None,
                "write_back_status": getattr(p, "write_back_status", None),
            }
            for p, party_name, party_id in payment_rows
        ],
    }


@router.get("/payments/{payment_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed payment information."""
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    customer_account = None
    party_id = None
    party_name = None
    if payment.customer_account and payment.customer_account.party:
        party = payment.customer_account.party
        party_id = party.id
        party_name = party.name
        if not party_name:
            party_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not party_name:
            party_name = party.legal_name or party.trading_name
        customer_account = {
            "id": payment.customer_account.id,
            "party_id": party.id,
            "name": party_name,
        }

    invoice = None
    if payment.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if inv:
            invoice = {"id": inv.id, "invoice_number": inv.invoice_number, "total_amount": float(inv.total_amount)}

    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "payment_method": payment.payment_method.value if payment.payment_method else None,
        "status": payment.status.value if payment.status else None,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "transaction_reference": payment.transaction_reference,
        "gateway_reference": payment.gateway_reference,
        "notes": payment.notes,
        "source": payment.source.value if payment.source else None,
        "external_ids": {
            "splynx_id": payment.splynx_id,
            "erpnext_id": payment.erpnext_id,
        },
        "customer_account_id": payment.customer_account_id,
        "party_id": party_id,
        "party_name": party_name,
        "customer_account": customer_account,
        "invoice": invoice,
        "references": [
            {
                "id": ref.id,
                "allocation_type": ref.allocation_type.value,
                "document_id": ref.document_id,
                "allocated_amount": float(ref.allocated_amount or 0),
                "discount_amount": float(ref.discount_amount or 0),
                "write_off_amount": float(ref.write_off_amount or 0),
                "exchange_gain_loss": float(ref.exchange_gain_loss or 0),
                "conversion_rate": float(ref.conversion_rate or 1),
            }
            for ref in payment.allocations
        ],
    }


@router.get("/credit-notes", dependencies=[Depends(Require("explorer:read"))])
async def list_credit_notes(
    customer_account_id: Optional[int] = None,
    party_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="issue_date,amount,customer_account_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List credit notes with filtering, search, sort, and pagination (single-currency only)."""
    currency = _resolve_currency_or_raise(db, CreditNote.currency, currency)
    query = db.query(CreditNote).filter(CreditNote.is_deleted == False)

    if customer_account_id:
        query = query.join(Invoice, CreditNote.invoice_id == Invoice.id).filter(
            Invoice.customer_account_id == customer_account_id
        )
    elif party_id:
        query = query.join(Invoice, CreditNote.invoice_id == Invoice.id).join(
            CustomerAccount,
            CustomerAccount.id == Invoice.customer_account_id,
        ).filter(CustomerAccount.party_id == party_id)

    if invoice_id:
        query = query.filter(CreditNote.invoice_id == invoice_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(CreditNote.issue_date >= start_dt)

    if end_dt:
        query = query.filter(CreditNote.issue_date <= end_dt)

    if currency:
        query = query.filter(CreditNote.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(CreditNote.credit_number.ilike(like), CreditNote.description.ilike(like)))

    sort_map = {
        "issue_date": CreditNote.issue_date,
        "amount": CreditNote.amount,
        "customer_account_id": Invoice.customer_account_id,
        "invoice_id": CreditNote.invoice_id,
        "status": CreditNote.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "issue_date")
    if sort_column is None:
        sort_column = CreditNote.issue_date
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    credit_note_rows = (
        query.outerjoin(Invoice, CreditNote.invoice_id == Invoice.id)
        .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
        .outerjoin(Party, CustomerAccount.party_id == Party.id)
        .add_columns(
            CustomerAccount.id.label("customer_account_id"),
            CustomerAccount.party_id.label("party_id"),
            Party.name.label("party_name"),
        )
        .order_by(order_clause, CreditNote.id.desc())
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
                "id": cn.id,
                "credit_note_number": cn.credit_number,
                "customer_account_id": customer_account_id,
                "party_id": party_id,
                "party_name": party_name,
                "invoice_id": cn.invoice_id,
                "amount": float(cn.amount) if cn.amount else 0,
                "currency": cn.currency,
                "date": cn.issue_date.isoformat() if cn.issue_date else None,
                "reason": cn.description,
                "status": cn.status.value if cn.status else None,
                "source": "splynx",
                "external_ids": {
                    "splynx_id": cn.splynx_id,
                },
            }
            for cn, customer_account_id, party_id, party_name in credit_note_rows
        ],
    }
