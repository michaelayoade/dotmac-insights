"""Credit/Debit Notes: CRUD and workflow for AR credit notes and AP debit notes."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.books_settings import DebitNote, DebitNoteStatus

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class NoteLineCreate(BaseModel):
    """Schema for creating a note line."""
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
    return_reason: Optional[str] = None


class CreditNoteCreate(BaseModel):
    """Schema for creating a credit note."""
    customer_id: int
    invoice_id: Optional[int] = None
    credit_number: Optional[str] = None
    description: Optional[str] = None
    issue_date: str
    posting_date: Optional[str] = None
    currency: str = "NGN"
    conversion_rate: float = 1
    company: Optional[str] = None
    lines: List[NoteLineCreate] = []


class DebitNoteCreate(BaseModel):
    """Schema for creating a debit note."""
    supplier_id: int
    supplier_name: Optional[str] = None
    original_bill_id: Optional[int] = None
    description: Optional[str] = None
    issue_date: str
    posting_date: Optional[str] = None
    currency: str = "NGN"
    conversion_rate: float = 1
    company: Optional[str] = None
    lines: List[NoteLineCreate] = []


class NoteUpdate(BaseModel):
    """Schema for updating a note."""
    description: Optional[str] = None
    issue_date: Optional[str] = None
    posting_date: Optional[str] = None


# =============================================================================
# CREDIT NOTES (AR)
# =============================================================================

@router.get("/credit-notes", dependencies=[Depends(Require("accounting:read"))])
def list_credit_notes(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List credit notes with filters."""
    query = db.query(CreditNote)

    if customer_id:
        query = query.filter(CreditNote.customer_id == customer_id)

    if status:
        try:
            status_enum = CreditNoteStatus(status.lower())
            query = query.filter(CreditNote.status == status_enum)
        except ValueError:
            pass

    if start_date:
        query = query.filter(CreditNote.issue_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(CreditNote.issue_date <= parse_date(end_date, "end_date"))

    query = query.order_by(CreditNote.issue_date.desc(), CreditNote.id.desc())
    total, notes = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "credit_notes": [
            {
                "id": n.id,
                "credit_number": n.credit_number,
                "customer_id": n.customer_id,
                "invoice_id": n.invoice_id,
                "issue_date": n.issue_date.isoformat() if n.issue_date else None,
                "amount": float(n.amount),
                "currency": n.currency,
                "status": n.status.value if n.status else None,
            }
            for n in notes
        ],
    }


@router.get("/credit-notes/{note_id}", dependencies=[Depends(Require("accounting:read"))])
def get_credit_note(
    note_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get credit note detail with lines."""
    note = db.query(CreditNote).filter(CreditNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    return {
        "id": note.id,
        "credit_number": note.credit_number,
        "customer_id": note.customer_id,
        "invoice_id": note.invoice_id,
        "description": note.description,
        "issue_date": note.issue_date.isoformat() if note.issue_date else None,
        "posting_date": note.posting_date.isoformat() if note.posting_date else None,
        "amount": float(note.amount),
        "tax_amount": float(note.tax_amount) if note.tax_amount else 0,
        "total_amount": float(note.total_amount) if note.total_amount else float(note.amount),
        "currency": note.currency,
        "base_currency": note.base_currency,
        "conversion_rate": float(note.conversion_rate) if note.conversion_rate else 1,
        "base_amount": float(note.base_amount) if note.base_amount else 0,
        "status": note.status.value if note.status else None,
        "workflow_status": note.workflow_status,
        "docstatus": note.docstatus,
        "company": note.company,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "lines": [
            {
                "id": line.id,
                "item_code": line.item_code,
                "item_name": line.item_name,
                "description": line.description,
                "quantity": float(line.quantity),
                "rate": float(line.rate),
                "amount": float(line.amount),
                "tax_rate": float(line.tax_rate) if line.tax_rate else 0,
                "tax_amount": float(line.tax_amount) if line.tax_amount else 0,
                "return_reason": line.return_reason,
            }
            for line in getattr(note, "lines", [])
        ],
    }


@router.post("/credit-notes", dependencies=[Depends(Require("books:write"))])
def create_credit_note(
    data: CreditNoteCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new credit note."""
    from app.models.document_lines import CreditNoteLine

    # Generate credit note number if not provided
    credit_number = data.credit_number
    if not credit_number:
        from app.services.number_generator import generate_voucher_number
        credit_number = generate_voucher_number(db, "credit_note")

    # Parse dates
    try:
        issue_date = datetime.fromisoformat(data.issue_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue date format")

    posting_date = datetime.fromisoformat(data.posting_date) if data.posting_date else issue_date

    note = CreditNote(
        credit_number=credit_number,
        customer_id=data.customer_id,
        invoice_id=data.invoice_id,
        description=data.description,
        issue_date=issue_date,
        posting_date=posting_date,
        currency=data.currency,
        conversion_rate=Decimal(str(data.conversion_rate)),
        company=data.company,
        status=CreditNoteStatus.DRAFT,
        created_by_id=user.id,
    )

    # Calculate totals from lines
    total_amount = Decimal("0")
    total_tax = Decimal("0")

    db.add(note)
    db.flush()

    for idx, line_data in enumerate(data.lines):
        line = CreditNoteLine(
            credit_note_id=note.id,
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
            return_reason=line_data.return_reason,
            idx=idx,
        )
        db.add(line)
        total_amount += line.amount
        total_tax += line.tax_amount

    note.amount = total_amount
    note.tax_amount = total_tax
    note.total_amount = total_amount + total_tax
    note.base_amount = note.amount * note.conversion_rate
    note.base_tax_amount = note.tax_amount * note.conversion_rate

    db.commit()
    db.refresh(note)

    return {
        "message": "Credit note created",
        "id": note.id,
        "credit_number": note.credit_number,
    }


# =============================================================================
# DEBIT NOTES (AP)
# =============================================================================

@router.get("/debit-notes", dependencies=[Depends(Require("accounting:read"))])
def list_debit_notes(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List debit notes with filters."""
    query = db.query(DebitNote)

    if supplier_id:
        query = query.filter(DebitNote.supplier_id == supplier_id)

    if status:
        try:
            status_enum = DebitNoteStatus(status.lower())
            query = query.filter(DebitNote.status == status_enum)
        except ValueError:
            pass

    if start_date:
        query = query.filter(DebitNote.issue_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(DebitNote.issue_date <= parse_date(end_date, "end_date"))

    query = query.order_by(DebitNote.issue_date.desc(), DebitNote.id.desc())
    total, notes = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "debit_notes": [
            {
                "id": n.id,
                "debit_note_number": n.debit_note_number,
                "supplier_id": n.supplier_id,
                "supplier_name": n.supplier_name,
                "issue_date": n.issue_date.isoformat() if n.issue_date else None,
                "amount": float(n.amount),
                "currency": n.currency,
                "status": n.status.value if n.status else None,
                "amount_remaining": float(n.amount_remaining) if n.amount_remaining else 0,
            }
            for n in notes
        ],
    }


@router.get("/debit-notes/{note_id}", dependencies=[Depends(Require("accounting:read"))])
def get_debit_note(
    note_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get debit note detail with lines."""
    note = db.query(DebitNote).filter(DebitNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")

    return {
        "id": note.id,
        "debit_note_number": note.debit_note_number,
        "supplier_id": note.supplier_id,
        "supplier_name": note.supplier_name,
        "original_bill_id": note.original_bill_id,
        "description": note.description,
        "issue_date": note.issue_date.isoformat() if note.issue_date else None,
        "posting_date": note.posting_date.isoformat() if note.posting_date else None,
        "amount": float(note.amount),
        "tax_amount": float(note.tax_amount) if note.tax_amount else 0,
        "total_amount": float(note.total_amount) if note.total_amount else float(note.amount),
        "currency": note.currency,
        "base_currency": note.base_currency,
        "conversion_rate": float(note.conversion_rate) if note.conversion_rate else 1,
        "base_amount": float(note.base_amount) if note.base_amount else 0,
        "amount_applied": float(note.amount_applied) if note.amount_applied else 0,
        "amount_remaining": float(note.amount_remaining) if note.amount_remaining else 0,
        "status": note.status.value if note.status else None,
        "workflow_status": note.workflow_status,
        "docstatus": note.docstatus,
        "company": note.company,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "lines": [
            {
                "id": line.id,
                "item_code": line.item_code,
                "item_name": line.item_name,
                "description": line.description,
                "quantity": float(line.quantity),
                "rate": float(line.rate),
                "amount": float(line.amount),
                "tax_rate": float(line.tax_rate) if line.tax_rate else 0,
                "tax_amount": float(line.tax_amount) if line.tax_amount else 0,
                "return_reason": line.return_reason,
            }
            for line in getattr(note, "lines", [])
        ],
    }


@router.post("/debit-notes", dependencies=[Depends(Require("books:write"))])
def create_debit_note(
    data: DebitNoteCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new debit note."""
    from app.models.document_lines import DebitNoteLine
    from app.services.number_generator import generate_voucher_number

    debit_note_number = generate_voucher_number(db, "debit_note")

    # Parse dates
    try:
        issue_date = datetime.fromisoformat(data.issue_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue date format")

    posting_date = datetime.fromisoformat(data.posting_date) if data.posting_date else issue_date

    note = DebitNote(
        debit_note_number=debit_note_number,
        supplier_id=data.supplier_id,
        supplier_name=data.supplier_name,
        original_bill_id=data.original_bill_id,
        description=data.description,
        issue_date=issue_date,
        posting_date=posting_date,
        currency=data.currency,
        conversion_rate=Decimal(str(data.conversion_rate)),
        company=data.company,
        status=DebitNoteStatus.DRAFT,
        created_by_id=user.id,
    )

    # Calculate totals from lines
    total_amount = Decimal("0")
    total_tax = Decimal("0")

    db.add(note)
    db.flush()

    for idx, line_data in enumerate(data.lines):
        line = DebitNoteLine(
            debit_note_id=note.id,
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
            return_reason=line_data.return_reason,
            idx=idx,
        )
        db.add(line)
        total_amount += line.amount
        total_tax += line.tax_amount

    note.amount = total_amount
    note.tax_amount = total_tax
    note.total_amount = total_amount + total_tax
    note.amount_remaining = note.total_amount
    note.base_amount = note.amount * note.conversion_rate
    note.base_tax_amount = note.tax_amount * note.conversion_rate

    db.commit()
    db.refresh(note)

    return {
        "message": "Debit note created",
        "id": note.id,
        "debit_note_number": note.debit_note_number,
    }


# =============================================================================
# WORKFLOW
# =============================================================================

@router.post("/credit-notes/{note_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_credit_note(
    note_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Submit a credit note for approval."""
    note = db.query(CreditNote).filter(CreditNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if note.status != CreditNoteStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only submit draft notes")

    note.status = CreditNoteStatus.ISSUED
    note.workflow_status = "issued"
    note.docstatus = 1
    db.commit()

    return {
        "message": "Credit note issued",
        "id": note.id,
        "status": note.status.value,
    }


@router.post("/debit-notes/{note_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_debit_note(
    note_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Submit a debit note for approval."""
    note = db.query(DebitNote).filter(DebitNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")

    if note.status != DebitNoteStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only submit draft notes")

    note.status = DebitNoteStatus.ISSUED
    note.workflow_status = "issued"
    note.docstatus = 1
    db.commit()

    return {
        "message": "Debit note issued",
        "id": note.id,
        "status": note.status.value,
    }
