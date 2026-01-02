"""Journal Entries: API endpoints for journal entry management.

This module provides the REST API for journal entry management.
Business logic is delegated to JournalEntryService.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.accounting import JournalEntryType
from app.services.accounting import JournalEntryService
from app.services.accounting.journal_entry_types import (
    JECreateData,
    JEFilters,
    JELineData,
    JEUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

from .helpers import parse_date, invalidate_report_cache

router = APIRouter()


# ============= SERVICE DEPENDENCY =============

def get_journal_entry_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> JournalEntryService:
    """Create a JournalEntryService instance for dependency injection."""
    return JournalEntryService(db, principal)


# ============= PYDANTIC SCHEMAS =============

class JournalEntryAccountCreate(BaseModel):
    """Schema for creating a journal entry account line."""

    account: Optional[str] = None
    account_id: Optional[int] = None
    debit: float = 0
    credit: float = 0
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None
    description: Optional[str] = None
    user_remark: Optional[str] = None


class JournalEntryCreate(BaseModel):
    """Schema for creating a journal entry."""

    voucher_type: str = "journal_entry"
    posting_date: str
    user_remark: Optional[str] = None
    description: Optional[str] = None
    company: Optional[str] = None
    accounts: List[JournalEntryAccountCreate] = Field(default_factory=list)
    lines: Optional[List[JournalEntryAccountCreate]] = None


# ============= HELPER FUNCTIONS =============

def _entry_to_dict(e) -> Dict[str, Any]:
    """Convert JournalEntry to list response dict."""
    return {
        "id": e.id,
        "erpnext_id": e.erpnext_id,
        "voucher_type": e.voucher_type.value if e.voucher_type else None,
        "posting_date": e.posting_date.isoformat() if e.posting_date else None,
        "company": e.company,
        "total_debit": float(e.total_debit),
        "total_credit": float(e.total_credit),
        "user_remark": e.user_remark,
        "is_opening": e.is_opening,
    }


def _entry_detail_to_dict(entry, gl_entries) -> Dict[str, Any]:
    """Convert JournalEntry with GL entries to detailed response dict."""
    accounts = [
        {
            "id": acc.id,
            "account": acc.account,
            "account_type": getattr(acc, "account_type", None),
            "party_type": acc.party_type,
            "party": acc.party,
            "debit": float(acc.debit or 0),
            "credit": float(acc.credit or 0),
            "debit_in_account_currency": float(acc.debit_in_account_currency or 0),
            "credit_in_account_currency": float(acc.credit_in_account_currency or 0),
            "exchange_rate": float(acc.exchange_rate or 1),
            "reference_type": getattr(acc, "reference_type", None),
            "reference_name": getattr(acc, "reference_name", None),
            "reference_due_date": (
                acc.reference_due_date.isoformat()
                if hasattr(acc, "reference_due_date") and acc.reference_due_date
                else None
            ),
            "cost_center": acc.cost_center,
            "project": getattr(acc, "project", None),
            "bank_account": getattr(acc, "bank_account", None),
            "cheque_no": getattr(acc, "cheque_no", None),
            "cheque_date": (
                acc.cheque_date.isoformat()
                if hasattr(acc, "cheque_date") and acc.cheque_date
                else None
            ),
            "user_remark": getattr(acc, "user_remark", None),
            "idx": getattr(acc, "idx", 0),
        }
        for acc in getattr(entry, "items", [])
    ]

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "voucher_type": entry.voucher_type.value if entry.voucher_type else None,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "company": entry.company,
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "is_balanced": abs(entry.total_debit - entry.total_credit) < Decimal("0.01"),
        "user_remark": entry.user_remark,
        "is_opening": entry.is_opening,
        "line_items": [
            {
                "id": gl.id,
                "account": gl.account,
                "party_type": gl.party_type,
                "party": gl.party,
                "debit": float(gl.debit),
                "credit": float(gl.credit),
                "cost_center": gl.cost_center,
            }
            for gl in gl_entries
        ],
        "line_count": len(gl_entries),
        "accounts": accounts,
    }


# ============= LIST & DETAIL ENDPOINTS =============

@router.get("/journal-entries", dependencies=[Depends(Require("accounting:read"))])
def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Get journal entries list."""
    # Build filters
    vtype_enum = None
    if voucher_type:
        try:
            vtype_enum = JournalEntryType(voucher_type.lower())
        except ValueError:
            pass  # Ignore invalid voucher type

    filters = JEFilters(
        start_date=parse_date(start_date, "start_date") if start_date else None,
        end_date=parse_date(end_date, "end_date") if end_date else None,
        voucher_type=vtype_enum,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_entries(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "entries": [_entry_to_dict(e) for e in result.items],
    }


@router.get(
    "/journal-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))]
)
def get_journal_entry_detail(
    entry_id: int,
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Get journal entry detail with all line items (GL entries)."""
    try:
        entry = service.get_entry(entry_id)
        gl_entries = service.get_entry_lines(entry_id)
        return _entry_detail_to_dict(entry, gl_entries)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= CRUD ENDPOINTS =============

@router.post("/journal-entries", dependencies=[Depends(Require("books:write"))])
async def create_journal_entry(
    je_data: JournalEntryCreate,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Create a new journal entry."""
    try:
        voucher_type_enum = JournalEntryType(je_data.voucher_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid voucher type: {je_data.voucher_type}"
        )

    posting_dt = parse_date(je_data.posting_date, "posting_date")
    if posting_dt is None:
        raise HTTPException(status_code=400, detail="Invalid posting_date")

    account_lines = je_data.accounts or (je_data.lines or [])

    try:
        create_data = JECreateData(
            posting_date=posting_dt,
            voucher_type=voucher_type_enum,
            user_remark=je_data.user_remark,
            description=je_data.description,
            company=je_data.company,
            lines=[
                JELineData(
                    account=line.account,
                    account_id=line.account_id,
                    debit=Decimal(str(line.debit)),
                    credit=Decimal(str(line.credit)),
                    party_type=line.party_type,
                    party=line.party,
                    cost_center=line.cost_center,
                    description=line.description,
                    user_remark=line.user_remark,
                )
                for line in account_lines
            ],
        )

        je = service.create_entry(create_data)
        db.commit()

        return {
            "message": "Journal entry created",
            "id": je.id,
            "total_debit": str(je.total_debit),
            "total_credit": str(je.total_credit),
            "docstatus": je.docstatus,
        }
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))]
)
def update_journal_entry(
    je_id: int,
    posting_date: Optional[str] = None,
    user_remark: Optional[str] = None,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Update a draft journal entry."""
    try:
        update_data = JEUpdateData(
            posting_date=(
                parse_date(posting_date, "posting_date") if posting_date else None
            ),
            user_remark=user_remark,
        )

        service.update_entry(je_id, update_data)
        db.commit()

        return {
            "message": "Journal entry updated",
            "id": je_id,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))]
)
def delete_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Delete a draft journal entry."""
    try:
        service.delete_entry(je_id)
        db.commit()
        return {"message": "Journal entry deleted"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= WORKFLOW ENDPOINTS =============

@router.post(
    "/journal-entries/{je_id}/submit", dependencies=[Depends(Require("books:write"))]
)
async def submit_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Submit a journal entry for approval."""
    try:
        service.submit_entry(je_id)
        db.commit()
        return {
            "message": "Journal entry submitted for approval",
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/journal-entries/{je_id}/approve",
    dependencies=[Depends(Require("books:approve"))],
)
async def approve_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Approve a journal entry at the current step."""
    try:
        service.approve_entry(je_id, remarks)
        db.commit()
        return {
            "message": "Journal entry approved",
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/journal-entries/{je_id}/reject",
    dependencies=[Depends(Require("books:approve"))],
)
async def reject_journal_entry(
    je_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Reject a journal entry."""
    try:
        service.reject_entry(je_id, reason)
        db.commit()
        return {
            "message": "Journal entry rejected",
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/journal-entries/{je_id}/post", dependencies=[Depends(Require("books:approve"))]
)
async def post_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    service: JournalEntryService = Depends(get_journal_entry_service),
) -> Dict[str, Any]:
    """Post an approved journal entry to the GL."""
    try:
        service.post_entry(je_id, remarks)
        db.commit()

        # Invalidate report caches after posting
        await invalidate_report_cache()

        return {
            "message": "Journal entry posted",
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
