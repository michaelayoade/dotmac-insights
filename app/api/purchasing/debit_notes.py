"""Debit Notes API endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.services.purchasing import DebitNoteService
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

from ._deps import (
    get_debit_note_service,
    RequireRead,
    parse_date,
    handle_service_error,
)

router = APIRouter(prefix="/debit-notes", tags=["purchasing"])


@router.get("", dependencies=[RequireRead])
async def get_debit_notes(
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """Get debit notes (returns/credits from suppliers)."""
    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_debit_notes(
        supplier=supplier,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        pagination=pagination,
    )

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "debit_notes": [
            {
                "id": n.id,
                "erpnext_id": n.erpnext_id,
                "supplier": n.supplier_name or n.supplier,
                "posting_date": n.posting_date.isoformat() if n.posting_date else None,
                "grand_total": float(n.grand_total),
                "status": n.status.value if n.status else None,
                "return_against": getattr(n, "return_against", None),
            }
            for n in result.data
        ],
    }


@router.get("/{note_id}", dependencies=[RequireRead])
async def get_debit_note_detail(
    note_id: int,
    service: DebitNoteService = Depends(get_debit_note_service),
) -> Dict[str, Any]:
    """Get debit note details."""
    try:
        detail = service.get_debit_note(note_id)
    except NotFoundError as e:
        handle_service_error(e)

    note = detail["note"]
    return {
        "id": note.id,
        "erpnext_id": note.erpnext_id,
        "supplier": note.supplier_name or note.supplier,
        "posting_date": note.posting_date.isoformat() if note.posting_date else None,
        "grand_total": float(note.grand_total),
        "status": note.status.value if note.status else None,
        "return_against": getattr(note, "return_against", None),
        "original_invoice": detail["original_invoice"],
        "remarks": getattr(note, "remarks", None),
    }
