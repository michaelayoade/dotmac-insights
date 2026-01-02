"""Accounts receivable invoices: CRUD and workflow.

Single source of truth for invoice writes; sales should call this API for creates/updates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.customer import Customer

from .helpers import parse_date, paginate, invalidate_report_cache

router = APIRouter()


# PYDANTIC SCHEMAS

class InvoiceLineCreate(BaseModel):
    """Schema for creating an invoice line."""
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: float = 1
    rate: float = 0
    amount: float = 0
    tax_code_id: Optional[int] = None
    tax_rate: float = 0
    tax_amount: float = 0
    account: Optional[str] = None
    cost_center: Optional[str] = None


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice."""
    customer_id: int
    contact_id: Optional[int] = None
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    invoice_date: str
    due_date: Optional[str] = None
    posting_date: Optional[str] = None
    currency: str = "NGN"
    conversion_rate: float = Field(default=1, gt=0, description="Conversion rate must be positive")
    payment_terms_id: Optional[int] = None
    company: Optional[str] = None
    category: Optional[str] = None
    lines: List[InvoiceLineCreate] = []


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""
    customer_id: Optional[int] = None
    contact_id: Optional[int] = None
    description: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    posting_date: Optional[str] = None
    currency: Optional[str] = None
    conversion_rate: Optional[float] = Field(default=None, gt=0, description="Conversion rate must be positive")
    payment_terms_id: Optional[int] = None
    category: Optional[str] = None


# INVOICE LIST & DETAIL

@router.get("/invoices", dependencies=[Depends(Require("accounting:read"))])
def list_invoices(
    customer_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    overdue_only: bool = False,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List invoices with filters."""
    query = db.query(Invoice).filter(Invoice.is_deleted == False)

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if contact_id:
        query = query.filter(Invoice.contact_id == contact_id)

    if status:
        try:
            status_enum = InvoiceStatus(status.lower())
            query = query.filter(Invoice.status == status_enum)
        except ValueError:
            valid_statuses = [s.value for s in InvoiceStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_statuses}"
            )

    if start_date:
        query = query.filter(Invoice.invoice_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(Invoice.invoice_date <= parse_date(end_date, "end_date"))

    if overdue_only:
        query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    total, invoices = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "contact_id": inv.contact_id,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "total_amount": float(inv.total_amount) if inv.total_amount else 0,
                "amount_paid": float(inv.amount_paid) if inv.amount_paid else 0,
                "balance": float(inv.balance) if inv.balance else 0,
                "currency": inv.currency,
                "status": inv.status.value if inv.status else None,
                "docstatus": inv.docstatus,
            }
            for inv in invoices
        ],
    }


@router.get("/invoices/{invoice_id}", dependencies=[Depends(Require("accounting:read"))])
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoice detail with lines."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer = None
    if invoice.customer_id:
        cust = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "contact_id": invoice.contact_id,
        "customer": customer,
        "description": invoice.description,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "posting_date": invoice.posting_date.isoformat() if invoice.posting_date else None,
        "amount": float(invoice.amount) if invoice.amount else 0,
        "tax_amount": float(invoice.tax_amount) if invoice.tax_amount else 0,
        "total_amount": float(invoice.total_amount) if invoice.total_amount else 0,
        "amount_paid": float(invoice.amount_paid) if invoice.amount_paid else 0,
        "balance": float(invoice.balance) if invoice.balance else 0,
        "currency": invoice.currency,
        "base_currency": invoice.base_currency,
        "conversion_rate": float(invoice.conversion_rate) if invoice.conversion_rate else 1,
        "base_amount": float(invoice.base_amount) if invoice.base_amount else 0,
        "status": invoice.status.value if invoice.status else None,
        "workflow_status": invoice.workflow_status,
        "docstatus": invoice.docstatus,
        "category": invoice.category,
        "company": invoice.company,
        "source": invoice.source.value if invoice.source else None,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "lines": [
            {
                "id": line.id,
                "item_code": line.item_code,
                "item_name": line.item_name,
                "description": line.description,
                "quantity": float(line.quantity) if line.quantity else 0,
                "rate": float(line.rate) if line.rate else 0,
                "amount": float(line.amount) if line.amount else 0,
                "tax_rate": float(line.tax_rate) if line.tax_rate else 0,
                "tax_amount": float(line.tax_amount) if line.tax_amount else 0,
            }
            for line in getattr(invoice, "lines", [])
        ],
    }


# INVOICE CRUD

@router.post("/invoices", dependencies=[Depends(Require("books:write"))])
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new invoice in draft status."""
    from app.models.document_lines import InvoiceLine
    from app.services.number_generator import generate_voucher_number

    # Validate customer exists
    customer = db.query(Customer).filter(Customer.id == data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail=f"Customer {data.customer_id} not found")

    # Generate invoice number if not provided
    invoice_number = data.invoice_number
    if not invoice_number:
        invoice_number = generate_voucher_number(db, "invoice")

    # Parse dates
    try:
        invoice_date = datetime.fromisoformat(data.invoice_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice date format")

    due_date = None
    if data.due_date:
        try:
            due_date = datetime.fromisoformat(data.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due date format")

    posting_date = datetime.fromisoformat(data.posting_date) if data.posting_date else invoice_date

    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=data.customer_id,
        contact_id=data.contact_id,
        description=data.description,
        invoice_date=invoice_date,
        due_date=due_date,
        posting_date=posting_date,
        currency=data.currency,
        conversion_rate=Decimal(str(data.conversion_rate)),
        payment_terms_id=data.payment_terms_id,
        company=data.company,
        category=data.category,
        source=InvoiceSource.INTERNAL,
        status=InvoiceStatus.DRAFT,
        docstatus=0,
        workflow_status="draft",
        created_by_id=principal.id,
        origin_system="local",
    )

    # Calculate totals from lines
    total_amount = Decimal("0")
    total_tax = Decimal("0")

    db.add(invoice)
    db.flush()

    for idx, line_data in enumerate(data.lines):
        line = InvoiceLine(
            invoice_id=invoice.id,
            item_code=line_data.item_code,
            item_name=line_data.item_name,
            description=line_data.description,
            quantity=Decimal(str(line_data.quantity)),
            rate=Decimal(str(line_data.rate)),
            amount=Decimal(str(line_data.amount)),
            tax_code_id=line_data.tax_code_id,
            tax_rate=Decimal(str(line_data.tax_rate)),
            tax_amount=Decimal(str(line_data.tax_amount)),
            account=line_data.account,
            cost_center=line_data.cost_center,
            idx=idx,
        )
        db.add(line)
        total_amount += line.amount
        total_tax += line.tax_amount

    invoice.amount = total_amount
    invoice.tax_amount = total_tax
    invoice.total_amount = total_amount + total_tax
    invoice.balance = invoice.total_amount
    invoice.amount_paid = Decimal("0")
    invoice.base_amount = invoice.amount * invoice.conversion_rate
    invoice.base_tax_amount = invoice.tax_amount * invoice.conversion_rate

    db.commit()
    db.refresh(invoice)

    return {
        "message": "Invoice created",
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status.value,
    }


@router.patch("/invoices/{invoice_id}", dependencies=[Depends(Require("books:write"))])
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a draft invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only update draft invoices")

    if data.customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == data.customer_id).first()
        if not customer:
            raise HTTPException(status_code=400, detail=f"Customer {data.customer_id} not found")
        invoice.customer_id = data.customer_id

    if data.contact_id is not None:
        invoice.contact_id = data.contact_id

    if data.description is not None:
        invoice.description = data.description

    if data.invoice_date is not None:
        try:
            invoice.invoice_date = datetime.fromisoformat(data.invoice_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid invoice date format")

    if data.due_date is not None:
        try:
            invoice.due_date = datetime.fromisoformat(data.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due date format")

    if data.posting_date is not None:
        try:
            invoice.posting_date = datetime.fromisoformat(data.posting_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid posting date format")

    if data.currency is not None:
        invoice.currency = data.currency

    if data.conversion_rate is not None:
        invoice.conversion_rate = Decimal(str(data.conversion_rate))
        invoice.base_amount = invoice.amount * invoice.conversion_rate
        invoice.base_tax_amount = invoice.tax_amount * invoice.conversion_rate

    if data.payment_terms_id is not None:
        invoice.payment_terms_id = data.payment_terms_id

    if data.category is not None:
        invoice.category = data.category

    db.commit()

    return {
        "message": "Invoice updated",
        "id": invoice.id,
    }


@router.delete("/invoices/{invoice_id}", dependencies=[Depends(Require("books:write"))])
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a draft invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only delete draft invoices")

    invoice.is_deleted = True
    invoice.deleted_at = datetime.now(timezone.utc)
    invoice.deleted_by_id = principal.id
    db.commit()

    return {"message": "Invoice deleted", "id": invoice_id}


# WORKFLOW

@router.post("/invoices/{invoice_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit invoice for approval (draft → pending)."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only submit draft invoices")

    invoice.status = InvoiceStatus.PENDING
    invoice.workflow_status = "pending"
    db.commit()

    return {
        "message": "Invoice submitted for approval",
        "id": invoice.id,
        "status": invoice.status.value,
    }


@router.post("/invoices/{invoice_id}/approve", dependencies=[Depends(Require("books:approve"))])
def approve_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve a pending invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only approve pending invoices")

    invoice.status = InvoiceStatus.APPROVED
    invoice.workflow_status = "approved"
    db.commit()

    return {
        "message": "Invoice approved",
        "id": invoice.id,
        "status": invoice.status.value,
    }


@router.post("/invoices/{invoice_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Post invoice to GL - creates AR debit, revenue credit."""
    from app.services.document_posting import DocumentPostingService, PostingError
    from app.services.billing_outbound_sync import BillingOutboundSyncService

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.docstatus != 0:
        raise HTTPException(status_code=400, detail="Invoice already posted or cancelled")

    posting_service = DocumentPostingService(db)
    try:
        je = posting_service.post_invoice(invoice_id, principal.id)
        invoice.docstatus = 1
        invoice.status = InvoiceStatus.UNPAID
        invoice.workflow_status = "posted"
        invoice.journal_entry_id = je.id
        db.commit()
        db.refresh(invoice)
    except PostingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await invalidate_report_cache()

    # Trigger outbound sync to ERPNext (if enabled)
    sync_service = BillingOutboundSyncService(db)
    sync_service.sync_invoice_to_erpnext(invoice)
    db.commit()

    return {
        "message": "Invoice posted",
        "id": invoice.id,
        "journal_entry_id": je.id,
        "status": invoice.status.value,
    }


@router.post("/invoices/{invoice_id}/cancel", dependencies=[Depends(Require("books:approve"))])
async def cancel_invoice(
    invoice_id: int,
    reason: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a posted invoice (creates reversal journal entry)."""
    from app.services.document_posting import DocumentPostingService, PostingError

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.docstatus != 1:
        raise HTTPException(status_code=400, detail="Can only cancel posted invoices")

    if invoice.amount_paid and invoice.amount_paid > 0:
        raise HTTPException(status_code=400, detail="Cannot cancel invoice with payments. Reverse payments first.")

    posting_service = DocumentPostingService(db)
    try:
        reversal_je = posting_service.reverse_invoice(invoice_id, principal.id, reason)
        invoice.docstatus = 2
        invoice.status = InvoiceStatus.CANCELLED
        invoice.workflow_status = "cancelled"
        db.commit()
    except PostingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await invalidate_report_cache()

    return {
        "message": "Invoice cancelled",
        "id": invoice.id,
        "reversal_journal_entry_id": reversal_je.id if reversal_je else None,
        "status": invoice.status.value,
    }
