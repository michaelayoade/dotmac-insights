"""Expense policy endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.expenses.schemas import ExpensePolicyCreate, ExpensePolicyRead
from app.database import get_db
from app.models.expense_management import ExpensePolicy

router = APIRouter()


@router.get("/", response_model=List[ExpensePolicyRead])
async def list_policies(
    include_inactive: bool = Query(default=False, description="Include inactive policies"),
    category_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(ExpensePolicy)
    if category_id:
        query = query.filter(ExpensePolicy.category_id == category_id)
    if not include_inactive:
        query = query.filter(ExpensePolicy.is_active.is_(True))
    return query.order_by(ExpensePolicy.priority.desc()).all()


@router.post("/", response_model=ExpensePolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(payload: ExpensePolicyCreate, db: Session = Depends(get_db)):
    policy = ExpensePolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.put("/{policy_id}", response_model=ExpensePolicyRead)
async def update_policy(policy_id: int, payload: ExpensePolicyCreate, db: Session = Depends(get_db)):
    policy = db.query(ExpensePolicy).filter(ExpensePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(ExpensePolicy).filter(ExpensePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return None
