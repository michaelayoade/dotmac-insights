"""Credit/Debit Notes: CRUD and workflow for AR credit notes and AP debit notes."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.models.credit_note import CreditNoteStatus
from app.models.books_settings import DebitNoteStatus
from app.services.accounting import CreditNoteService, DebitNoteService
from app.services.accounting.credit_notes_types import (
    CreditNoteFilters,
    CreditNoteCreateData,
    CreditNoteLineData,
)
from app.services.accounting.debit_notes_types import (
    DebitNoteFilters,
    DebitNoteCreateData,
    DebitNoteLineData,
)
from app.services.errors import NotFoundError, ValidationError as ServiceValidationError
from app.services.types import PaginationParams

router = APIRouter()


# SERVICE DEPENDENCIES


def get_credit_note_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CreditNoteService:
    """Dependency to get a CreditNoteService instance."""
    return CreditNoteService(db, principal)


def get_debit_note_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DebitNoteService:
    """Dependency to get a DebitNoteService instance."""
    return DebitNoteService(db, principal)


# PYDANTIC SCHEMAS


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
    customer_account_id: int
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


# HELPER FUNCTIONS


def _convert_credit_note_line(line: NoteLineCreate) -> CreditNoteLineData:
    """Convert Pydantic line schema to service dataclass."""
    return CreditNoteLineData(
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
        return_reason=line.return_reason,
    )


def _convert_debit_note_line(line: NoteLineCreate) -> DebitNoteLineData:
    """Convert Pydantic line schema to service dataclass."""
    return DebitNoteLineData(
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
        return_reason=line.return_reason,
    )


def _parse_status_credit(status_str: Optional[str]) -> Optional[CreditNoteStatus]:
    """Parse status string to enum."""
    if not status_str:
        return None
    try:
        return CreditNoteStatus(status_str.lower())
    except ValueError:
        return None


def _parse_status_debit(status_str: Optional[str]) -> Optional[DebitNoteStatus]:
    """Parse status string to enum."""
    if not status_str:
        return None
    try:
        return DebitNoteStatus(status_str.lower())
    except ValueError:
        return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


# CREDIT NOTES (AR)


@router.get("/credit-notes", dependencies=[Depends(Require("accounting:read"))])
def list_credit_notes(
    customer_account_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: CreditNoteService = Depends(get_credit_note_service),
) -> Dict[str, Any]:
    """List credit notes with filters."""
    filters = CreditNoteFilters(
        customer_account_id=customer_account_id,
        status=_parse_status_credit(status),
        start_date=_parse_date(start_date).date() if start_date else None,
        end_date=_parse_date(end_date).date() if end_date else None,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_credit_notes(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "credit_notes": [
            {
                "id": n.id,
                "credit_number": n.credit_number,
                "customer_account_id": n.customer_account_id,
                "invoice_id": n.invoice_id,
                "issue_date": n.issue_date.isoformat() if n.issue_date else None,
                "amount": float(n.amount),
                "currency": n.currency,
                "status": n.status.value if n.status else None,
            }
            for n in result.items
        ],
    }


@router.get("/credit-notes/{note_id}", dependencies=[Depends(Require("accounting:read"))])
def get_credit_note(
    note_id: int,
    service: CreditNoteService = Depends(get_credit_note_service),
) -> Dict[str, Any]:
    """Get credit note detail with lines."""
    try:
        note = service.get_credit_note(note_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": note.id,
        "credit_number": note.credit_number,
        "customer_account_id": note.customer_account_id,
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
    service: CreditNoteService = Depends(get_credit_note_service),
) -> Dict[str, Any]:
    """Create a new credit note."""
    try:
        issue_date = datetime.fromisoformat(data.issue_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue date format")

    posting_date = None
    if data.posting_date:
        try:
            posting_date = datetime.fromisoformat(data.posting_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid posting date format")

    try:
        create_data = CreditNoteCreateData(
            customer_account_id=data.customer_account_id,
            invoice_id=data.invoice_id,
            credit_number=data.credit_number,
            description=data.description,
            issue_date=issue_date,
            posting_date=posting_date,
            currency=data.currency,
            conversion_rate=Decimal(str(data.conversion_rate)),
            company=data.company,
            lines=[_convert_credit_note_line(line) for line in data.lines],
        )
        note = service.create_credit_note(create_data)
        db.commit()
        db.refresh(note)

        return {
            "message": "Credit note created",
            "id": note.id,
            "credit_number": note.credit_number,
        }
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


# DEBIT NOTES (AP)


@router.get("/debit-notes", dependencies=[Depends(Require("accounting:read"))])
def list_debit_notes(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """List debit notes with filters."""
    filters = DebitNoteFilters(
        supplier_id=supplier_id,
        status=_parse_status_debit(status),
        start_date=_parse_date(start_date).date() if start_date else None,
        end_date=_parse_date(end_date).date() if end_date else None,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_debit_notes(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "debit_notes": [
            {
                "id": n.id,
                "debit_note_number": n.debit_note_number,
                "supplier_id": n.supplier_id,
                "supplier_name": n.supplier_name,
                "issue_date": n.posting_date.isoformat() if n.posting_date else None,
                "amount": float(n.total_amount),
                "currency": n.currency,
                "status": n.status.value if n.status else None,
                "amount_remaining": float(n.outstanding_amount) if n.outstanding_amount else 0,
            }
            for n in result.items
        ],
    }


@router.get("/debit-notes/{note_id}", dependencies=[Depends(Require("accounting:read"))])
def get_debit_note(
    note_id: int,
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """Get debit note detail with lines."""
    try:
        note = service.get_debit_note(note_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": note.id,
        "debit_note_number": note.debit_note_number,
        "supplier_id": note.supplier_id,
        "supplier_name": note.supplier_name,
        "original_bill_id": note.purchase_invoice_id,
        "description": note.remarks,
        "issue_date": note.posting_date.isoformat() if note.posting_date else None,
        "posting_date": note.posting_date.isoformat() if note.posting_date else None,
        "amount": float(note.total_amount),
        "tax_amount": float(sum((line.tax_amount or Decimal("0")) for line in getattr(note, "lines", []))),
        "total_amount": float(note.total_amount),
        "currency": note.currency,
        "base_currency": note.base_currency,
        "conversion_rate": float(note.conversion_rate) if note.conversion_rate else 1,
        "base_amount": float(note.base_amount) if note.base_amount else 0,
        "amount_applied": float(note.total_amount - note.outstanding_amount) if note.outstanding_amount is not None else 0,
        "amount_remaining": float(note.outstanding_amount) if note.outstanding_amount else 0,
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
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """Create a new debit note."""
    try:
        issue_date = datetime.fromisoformat(data.issue_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue date format")

    posting_date = None
    if data.posting_date:
        try:
            posting_date = datetime.fromisoformat(data.posting_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid posting date format")

    try:
        create_data = DebitNoteCreateData(
            supplier_id=data.supplier_id,
            supplier_name=data.supplier_name,
            original_bill_id=data.original_bill_id,
            description=data.description,
            issue_date=issue_date,
            posting_date=posting_date,
            currency=data.currency,
            conversion_rate=Decimal(str(data.conversion_rate)),
            company=data.company,
            lines=[_convert_debit_note_line(line) for line in data.lines],
        )
        note = service.create_debit_note(create_data)
        db.commit()
        db.refresh(note)

        return {
            "message": "Debit note created",
            "id": note.id,
            "debit_note_number": note.debit_note_number,
        }
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


# WORKFLOW


@router.post("/credit-notes/{note_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_credit_note(
    note_id: int,
    db: Session = Depends(get_db),
    service: CreditNoteService = Depends(get_credit_note_service),
) -> Dict[str, Any]:
    """Submit a credit note for approval."""
    try:
        note = service.submit_credit_note(note_id)
        db.commit()

        return {
            "message": "Credit note issued",
            "id": note.id,
            "status": note.status.value,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


@router.post("/debit-notes/{note_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_debit_note(
    note_id: int,
    db: Session = Depends(get_db),
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """Submit a debit note for approval."""
    try:
        note = service.submit_debit_note(note_id)
        db.commit()

        return {
            "message": "Debit note issued",
            "id": note.id,
            "status": note.status.value,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)
