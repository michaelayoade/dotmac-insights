"""Cash advance endpoints."""
from __future__ import annotations

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.expenses.schemas import (
    CashAdvanceCreate,
    CashAdvanceRead,
    CashAdvanceDisburse,
    CashAdvanceSettle,
)
from app.auth import get_current_principal, Principal
from app.database import get_db
from app.models.expense_management import CashAdvance, CashAdvanceStatus
from app.services.cash_advance_service import CashAdvanceService

router = APIRouter()


@router.get("/", response_model=List[CashAdvanceRead])
async def list_advances(
    status: Optional[CashAdvanceStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(CashAdvance).order_by(CashAdvance.created_at.desc())
    if status:
        query = query.filter(CashAdvance.status == status)
    advances = query.offset(offset).limit(limit).all()
    return advances


@router.get("/{advance_id}", response_model=CashAdvanceRead)
async def get_advance(advance_id: int, db: Session = Depends(get_db)):
    advance = (
        db.query(CashAdvance)
        .options(selectinload(CashAdvance.expense_claims))
        .filter(CashAdvance.id == advance_id)
        .first()
    )
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")
    return advance


@router.post("/", response_model=CashAdvanceRead, status_code=201)
async def create_advance(
    payload: CashAdvanceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    service = CashAdvanceService(db)
    advance = service.create_advance(payload)
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/submit", response_model=CashAdvanceRead)
async def submit_advance(
    advance_id: int,
    company_code: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    advance = service.submit(advance, user_id=principal.id, company_code=company_code)
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/approve", response_model=CashAdvanceRead)
async def approve_advance(
    advance_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    advance = service.approve(advance, user_id=principal.id)
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/reject", response_model=CashAdvanceRead)
async def reject_advance(
    advance_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    advance = service.reject(advance, user_id=principal.id, reason=reason)
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/disburse", response_model=CashAdvanceRead)
async def disburse_advance(
    advance_id: int,
    payload: CashAdvanceDisburse,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    advance = service.disburse(
        advance,
        amount=payload.amount,
        mode_of_payment=payload.mode_of_payment,
        payment_reference=payload.payment_reference,
        bank_account_id=payload.bank_account_id,
        user_id=principal.id,
    )
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/settle", response_model=CashAdvanceRead)
async def settle_advance(
    advance_id: int,
    payload: CashAdvanceSettle,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    advance = service.settle(
        advance,
        amount=payload.amount,
        refund_amount=payload.refund_amount or Decimal("0"),
    )
    db.commit()
    db.refresh(advance)
    return advance
