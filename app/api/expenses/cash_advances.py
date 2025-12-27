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
from app.auth import get_current_principal, Principal, Require
from app.api.expenses.access import apply_employee_scope, assert_employee_access
from app.database import get_db
from app.models.expense_management import CashAdvance, CashAdvanceStatus
from app.services.errors import ValidationError
from app.services.cash_advance_service import CashAdvanceService

router = APIRouter()


@router.get("/", response_model=List[CashAdvanceRead], dependencies=[Depends(Require("expenses:read"))])
async def list_advances(
    status: Optional[CashAdvanceStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = db.query(CashAdvance).order_by(CashAdvance.created_at.desc())
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    if status:
        query = query.filter(CashAdvance.status == status)
    advances = query.offset(offset).limit(limit).all()
    return advances


@router.get("/{advance_id}", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:read"))])
async def get_advance(
    advance_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = (
        db.query(CashAdvance)
        .options(selectinload(CashAdvance.expense_claims))
        .filter(CashAdvance.id == advance_id)
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")
    return advance


@router.post("/", response_model=CashAdvanceRead, status_code=201, dependencies=[Depends(Require("expenses:write"))])
async def create_advance(
    payload: CashAdvanceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    assert_employee_access(principal, db, payload.employee_id)
    service = CashAdvanceService(db)
    advance = service.create_advance(payload)
    if principal.type == "user":
        advance.created_by_id = principal.id
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/submit", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:write"))])
async def submit_advance(
    advance_id: int,
    company_code: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update()
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    try:
        advance = service.submit(advance, user_id=principal.id, company_code=company_code)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/approve", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:write"))])
async def approve_advance(
    advance_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update()
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    try:
        advance = service.approve(advance, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/reject", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:write"))])
async def reject_advance(
    advance_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    query = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update()
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    try:
        advance = service.reject(advance, user_id=principal.id, reason=reason)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/disburse", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:write"))])
async def disburse_advance(
    advance_id: int,
    payload: CashAdvanceDisburse,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update()
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    try:
        advance = service.disburse(
            advance,
            amount=payload.amount,
            mode_of_payment=payload.mode_of_payment,
            payment_reference=payload.payment_reference,
            bank_account_id=payload.bank_account_id,
            user_id=principal.id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(advance)
    return advance


@router.post("/{advance_id}/settle", response_model=CashAdvanceRead, dependencies=[Depends(Require("expenses:write"))])
async def settle_advance(
    advance_id: int,
    payload: CashAdvanceSettle,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    query = db.query(CashAdvance).filter(CashAdvance.id == advance_id).with_for_update()
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CashAdvance.employee_id,
        created_by_field=CashAdvance.created_by_id,
    )
    advance = query.first()
    if not advance:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    service = CashAdvanceService(db)
    try:
        advance = service.settle(
            advance,
            amount=payload.amount,
            refund_amount=payload.refund_amount or Decimal("0"),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(advance)
    return advance
