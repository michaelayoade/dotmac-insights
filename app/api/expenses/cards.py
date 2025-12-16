"""Corporate card management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.expenses.schemas import (
    CorporateCardCreate,
    CorporateCardRead,
    CorporateCardUpdate,
)
from app.database import get_db
from app.models.expense_management import (
    CorporateCard,
    CorporateCardStatus,
)
from app.auth import get_current_principal, Principal

router = APIRouter()


@router.get("/", response_model=List[CorporateCardRead])
async def list_cards(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    employee_id: Optional[int] = Query(default=None, description="Filter by employee"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    include_inactive: bool = Query(default=False, description="Include suspended/cancelled cards"),
    db: Session = Depends(get_db),
):
    """List corporate cards with optional filters."""
    query = db.query(CorporateCard).order_by(CorporateCard.created_at.desc())

    if employee_id:
        query = query.filter(CorporateCard.employee_id == employee_id)

    if status:
        try:
            query = query.filter(CorporateCard.status == CorporateCardStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    elif not include_inactive:
        query = query.filter(CorporateCard.status == CorporateCardStatus.ACTIVE)

    cards = query.offset(offset).limit(limit).all()
    return cards


@router.get("/{card_id}", response_model=CorporateCardRead)
async def get_card(card_id: int, db: Session = Depends(get_db)):
    """Get a single corporate card by ID."""
    card = db.query(CorporateCard).filter(CorporateCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")
    return card


@router.post("/", response_model=CorporateCardRead, status_code=201)
async def create_card(
    payload: CorporateCardCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Create a new corporate card."""
    # Check if employee exists
    from app.models.employee import Employee

    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not employee:
        raise HTTPException(status_code=400, detail="Employee not found")

    card = CorporateCard(
        card_number_last4=payload.card_number_last4,
        card_name=payload.card_name,
        card_type=payload.card_type,
        bank_name=payload.bank_name,
        card_provider=payload.card_provider,
        employee_id=payload.employee_id,
        credit_limit=payload.credit_limit,
        single_transaction_limit=payload.single_transaction_limit,
        daily_limit=payload.daily_limit,
        monthly_limit=payload.monthly_limit,
        currency=payload.currency,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        liability_account=payload.liability_account,
        bank_account_id=payload.bank_account_id,
        company=payload.company,
        status=CorporateCardStatus.ACTIVE,
        created_by_id=principal.id,
    )

    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=CorporateCardRead)
async def update_card(
    card_id: int,
    payload: CorporateCardUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Update a corporate card."""
    card = (
        db.query(CorporateCard)
        .filter(CorporateCard.id == card_id)
        .with_for_update()
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.post("/{card_id}/suspend", response_model=CorporateCardRead)
async def suspend_card(
    card_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Suspend a corporate card."""
    card = (
        db.query(CorporateCard)
        .filter(CorporateCard.id == card_id)
        .with_for_update()
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")

    if card.status == CorporateCardStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot suspend a cancelled card")

    card.status = CorporateCardStatus.SUSPENDED
    db.commit()
    db.refresh(card)
    return card


@router.post("/{card_id}/activate", response_model=CorporateCardRead)
async def activate_card(
    card_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Activate a suspended corporate card."""
    card = (
        db.query(CorporateCard)
        .filter(CorporateCard.id == card_id)
        .with_for_update()
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")

    if card.status == CorporateCardStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot activate a cancelled card")

    card.status = CorporateCardStatus.ACTIVE
    db.commit()
    db.refresh(card)
    return card


@router.post("/{card_id}/cancel", response_model=CorporateCardRead)
async def cancel_card(
    card_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Cancel a corporate card (permanent)."""
    card = (
        db.query(CorporateCard)
        .filter(CorporateCard.id == card_id)
        .with_for_update()
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")

    if card.status == CorporateCardStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Card is already cancelled")

    card.status = CorporateCardStatus.CANCELLED
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204)
async def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Delete a corporate card (only if no transactions exist)."""
    card = (
        db.query(CorporateCard)
        .options(selectinload(CorporateCard.transactions))
        .filter(CorporateCard.id == card_id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Corporate card not found")

    if card.transactions:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete card with existing transactions. Cancel it instead.",
        )

    db.delete(card)
    db.commit()
