"""Expense claim endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.expenses.schemas import ExpenseClaimCreate, ExpenseClaimRead
from app.database import get_db
from app.models.expense_management import ExpenseClaim
from app.services.expense_service import ExpenseService
from app.services.expense_posting_service import ExpensePostingService
from app.auth import get_current_principal, Principal

router = APIRouter()


@router.get("/", response_model=List[ExpenseClaimRead])
async def list_claims(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseClaim).options(selectinload(ExpenseClaim.lines)).order_by(ExpenseClaim.created_at.desc())
    if status:
        try:
            from app.models.expense_management import ExpenseClaimStatus

            query = query.filter(ExpenseClaim.status == ExpenseClaimStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    claims = query.offset(offset).limit(limit).all()
    return claims


@router.get("/{claim_id}", response_model=ExpenseClaimRead)
async def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/", response_model=ExpenseClaimRead, status_code=201)
async def create_claim(
    payload: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    service = ExpenseService(db)
    claim = service.create_claim(payload)
    db.commit()
    db.refresh(claim)
    return (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim.id)
        .first()
    )


@router.post("/{claim_id}/submit", response_model=ExpenseClaimRead)
async def submit_claim(
    claim_id: int,
    company_code: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    claim = service.submit_claim(claim, user_id=principal.id, company_code=company_code)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/approve", response_model=ExpenseClaimRead)
async def approve_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    claim = service.approve_claim(claim, user_id=principal.id)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/reject", response_model=ExpenseClaimRead)
async def reject_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    service = ExpenseService(db)
    claim = service.reject_claim(claim, user_id=principal.id, reason=reason)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/return", response_model=ExpenseClaimRead)
async def return_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Return reason is required")

    service = ExpenseService(db)
    claim = service.return_claim(claim, reason=reason)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/recall", response_model=ExpenseClaimRead)
async def recall_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    claim = service.recall_claim(claim, user_id=principal.id)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/post", response_model=ExpenseClaimRead)
async def post_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    posting_service = ExpensePostingService(db)
    posting_service.post_claim(claim, user_id=principal.id)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/reverse", response_model=ExpenseClaimRead)
async def reverse_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Reversal reason is required")

    posting_service = ExpensePostingService(db)
    posting_service.reverse_claim(claim, reason=reason, user_id=principal.id)
    db.commit()
    db.refresh(claim)
    return claim
