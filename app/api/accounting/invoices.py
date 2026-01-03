"""Accounts receivable invoices: CRUD and workflow.

Single source of truth for invoice writes; sales should call this API for creates/updates.
Uses InvoiceService for business logic.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.services.accounting.invoice_types import (
    InvoiceCreateData,
    InvoiceFilters,
    InvoiceLineData,
    InvoiceUpdateData,
)
from app.services.accounting.invoices import InvoiceService
from app.services.errors import NotFoundError, ServiceError, ValidationError
from app.services.types import PaginationParams

from .helpers import invalidate_report_cache, parse_date

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------


def get_invoice_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> InvoiceService:
    """Dependency to get an InvoiceService instance."""
    return InvoiceService(db, principal)


# ---------------------------------------------------------------------------
# Pydantic Schemas (for API validation)
# ---------------------------------------------------------------------------


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

    customer_account_id: int
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    invoice_date: str
    due_date: Optional[str] = None
    posting_date: Optional[str] = None
    currency: str = "NGN"
    conversion_rate: float = Field(
        default=1, gt=0, description="Conversion rate must be positive"
    )
    payment_terms_id: Optional[int] = None
    company: Optional[str] = None
    category: Optional[str] = None
    lines: List[InvoiceLineCreate] = []


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""

    customer_account_id: Optional[int] = None
    description: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    posting_date: Optional[str] = None
    currency: Optional[str] = None
    conversion_rate: Optional[float] = Field(
        default=None, gt=0, description="Conversion rate must be positive"
    )
    payment_terms_id: Optional[int] = None
    category: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: Convert Pydantic schema to service dataclass
# ---------------------------------------------------------------------------


def _to_create_data(schema: InvoiceCreate) -> InvoiceCreateData:
    """Convert Pydantic InvoiceCreate to service InvoiceCreateData."""
    # Parse dates
    try:
        invoice_date = datetime.fromisoformat(schema.invoice_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid invoice date format") from e

    due_date = None
    if schema.due_date:
        try:
            due_date = datetime.fromisoformat(schema.due_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid due date format") from e

    posting_date = None
    if schema.posting_date:
        try:
            posting_date = datetime.fromisoformat(schema.posting_date)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid posting date format"
            ) from e

    lines = [
        InvoiceLineData(
            item_code=line.item_code,
            item_name=line.item_name,
            description=line.description,
            quantity=Decimal(str(line.quantity)),
            rate=Decimal(str(line.rate)),
            amount=Decimal(str(line.amount)),
            tax_code_id=line.tax_code_id,
            tax_rate=Decimal(str(line.tax_rate)),
            tax_amount=Decimal(str(line.tax_amount)),
            account=line.account,
            cost_center=line.cost_center,
        )
        for line in schema.lines
    ]

    return InvoiceCreateData(
        customer_account_id=schema.customer_account_id,
        invoice_number=schema.invoice_number,
        description=schema.description,
        invoice_date=invoice_date,
        due_date=due_date,
        posting_date=posting_date,
        currency=schema.currency,
        conversion_rate=Decimal(str(schema.conversion_rate)),
        payment_terms_id=schema.payment_terms_id,
        company=schema.company,
        category=schema.category,
        lines=lines,
    )


def _to_update_data(schema: InvoiceUpdate) -> InvoiceUpdateData:
    """Convert Pydantic InvoiceUpdate to service InvoiceUpdateData."""
    invoice_date = None
    if schema.invoice_date is not None:
        try:
            invoice_date = datetime.fromisoformat(schema.invoice_date)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid invoice date format"
            ) from e

    due_date = None
    if schema.due_date is not None:
        try:
            due_date = datetime.fromisoformat(schema.due_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid due date format") from e

    posting_date = None
    if schema.posting_date is not None:
        try:
            posting_date = datetime.fromisoformat(schema.posting_date)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid posting date format"
            ) from e

    conversion_rate = None
    if schema.conversion_rate is not None:
        conversion_rate = Decimal(str(schema.conversion_rate))

    return InvoiceUpdateData(
        customer_account_id=schema.customer_account_id,
        description=schema.description,
        invoice_date=invoice_date,
        due_date=due_date,
        posting_date=posting_date,
        currency=schema.currency,
        conversion_rate=conversion_rate,
        payment_terms_id=schema.payment_terms_id,
        category=schema.category,
    )


# ---------------------------------------------------------------------------
# Helper: Serialize invoice to response dict
# ---------------------------------------------------------------------------


def _serialize_invoice_list_item(inv: Invoice) -> Dict[str, Any]:
    """Serialize invoice for list response."""
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "customer_account_id": inv.customer_account_id,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "total_amount": float(inv.total_amount) if inv.total_amount else 0,
        "amount_paid": float(inv.amount_paid) if inv.amount_paid else 0,
        "balance": float(inv.balance) if inv.balance else 0,
        "currency": inv.currency,
        "status": inv.status.value if inv.status else None,
        "docstatus": inv.docstatus,
    }


def _serialize_invoice_detail(invoice: Invoice, db: Session) -> Dict[str, Any]:
    """Serialize invoice for detail response."""
    customer = None
    if invoice.customer_account and invoice.customer_account.party:
        party = invoice.customer_account.party
        customer = {"id": invoice.customer_account_id, "party_id": party.id, "name": party.name, "email": party.primary_email}

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_account_id": invoice.customer_account_id,
        "customer": customer,
        "description": invoice.description,
        "invoice_date": (
            invoice.invoice_date.isoformat() if invoice.invoice_date else None
        ),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "posting_date": (
            invoice.posting_date.isoformat() if invoice.posting_date else None
        ),
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


# ---------------------------------------------------------------------------
# Invoice List & Detail
# ---------------------------------------------------------------------------


@router.get("/invoices", dependencies=[Depends(Require("accounting:read"))])
def list_invoices(
    customer_account_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    overdue_only: bool = False,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """List invoices with filters."""
    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = InvoiceStatus(status.lower())
        except ValueError:
            valid_statuses = [s.value for s in InvoiceStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_statuses}",
            )

    # Build filters
    filters = InvoiceFilters(
        customer_account_id=customer_account_id,
        status=status_enum,
        start_date=parse_date(start_date, "start_date") if start_date else None,
        end_date=parse_date(end_date, "end_date") if end_date else None,
        overdue_only=overdue_only,
    )

    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_invoices(filters, pagination)

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "invoices": [_serialize_invoice_list_item(inv) for inv in result.items],
    }


@router.get("/invoices/{invoice_id}", dependencies=[Depends(Require("accounting:read"))])
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Get invoice detail with lines."""
    try:
        invoice = service.get_invoice(invoice_id)
        return _serialize_invoice_detail(invoice, db)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ---------------------------------------------------------------------------
# Invoice CRUD
# ---------------------------------------------------------------------------


@router.post("/invoices", dependencies=[Depends(Require("books:write"))])
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Create a new invoice in draft status."""
    try:
        create_data = _to_create_data(data)
        invoice = service.create_invoice(create_data)
        db.commit()
        db.refresh(invoice)
        return {
            "message": "Invoice created",
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "status": invoice.status.value,
        }
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/invoices/{invoice_id}", dependencies=[Depends(Require("books:write"))])
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Update a draft invoice."""
    try:
        update_data = _to_update_data(data)
        invoice = service.update_invoice(invoice_id, update_data)
        db.commit()
        return {
            "message": "Invoice updated",
            "id": invoice.id,
        }
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/invoices/{invoice_id}", dependencies=[Depends(Require("books:write"))])
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Soft delete a draft invoice."""
    try:
        service.delete_invoice(invoice_id)
        db.commit()
        return {"message": "Invoice deleted", "id": invoice_id}
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@router.post("/invoices/{invoice_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Submit invoice for approval (draft → pending)."""
    try:
        invoice = service.submit_invoice(invoice_id)
        db.commit()
        return {
            "message": "Invoice submitted for approval",
            "id": invoice.id,
            "status": invoice.status.value,
        }
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("/invoices/{invoice_id}/approve", dependencies=[Depends(Require("books:approve"))])
def approve_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Approve a pending invoice.

    Note: This is a workflow step before posting. The invoice transitions
    from pending to approved workflow state but keeps PENDING status.
    """
    try:
        invoice = service.get_invoice(invoice_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)

    if invoice.status != InvoiceStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only approve pending invoices")

    # Mark as approved (workflow status only, status stays PENDING until posted)
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
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Post invoice to GL - creates AR debit, revenue credit."""
    from app.services.billing_outbound_sync import BillingOutboundSyncService

    try:
        invoice, je = service.post_invoice(invoice_id)
        db.commit()
        db.refresh(invoice)
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)

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
    service: InvoiceService = Depends(get_invoice_service),
) -> Dict[str, Any]:
    """Cancel a posted invoice (creates reversal journal entry)."""
    try:
        invoice, reversal_je = service.cancel_invoice(invoice_id, reason)
        db.commit()
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)

    await invalidate_report_cache()

    return {
        "message": "Invoice cancelled",
        "id": invoice.id,
        "reversal_journal_entry_id": reversal_je.id if reversal_je else None,
        "status": invoice.status.value,
    }
