"""Expense policy endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.expenses.schemas import ExpensePolicyCreate, ExpensePolicyRead
from app.auth import Require
from app.database import get_db
from app.models.expense_management import ExpensePolicy

router = APIRouter()


def _serialize_policy(policy: ExpensePolicy) -> Dict[str, Any]:
    """Serialize ExpensePolicy model to dict."""
    return {
        "id": policy.id,
        "policy_name": policy.policy_name,
        "description": policy.description,
        "category_id": policy.category_id,
        "applies_to_all": policy.applies_to_all,
        "department_id": policy.department_id,
        "designation_id": policy.designation_id,
        "employment_type": policy.employment_type,
        "grade_level": policy.grade_level,
        "max_single_expense": float(policy.max_single_expense) if policy.max_single_expense is not None else None,
        "max_daily_limit": float(policy.max_daily_limit) if policy.max_daily_limit is not None else None,
        "max_monthly_limit": float(policy.max_monthly_limit) if policy.max_monthly_limit is not None else None,
        "max_claim_amount": float(policy.max_claim_amount) if policy.max_claim_amount is not None else None,
        "currency": policy.currency,
        "receipt_required": policy.receipt_required,
        "receipt_threshold": float(policy.receipt_threshold) if policy.receipt_threshold is not None else None,
        "auto_approve_below": float(policy.auto_approve_below) if policy.auto_approve_below is not None else None,
        "requires_pre_approval": policy.requires_pre_approval,
        "allow_out_of_pocket": policy.allow_out_of_pocket,
        "allow_cash_advance": policy.allow_cash_advance,
        "allow_corporate_card": policy.allow_corporate_card,
        "allow_per_diem": policy.allow_per_diem,
        "effective_from": policy.effective_from.isoformat() if policy.effective_from else None,
        "effective_to": policy.effective_to.isoformat() if policy.effective_to else None,
        "is_active": policy.is_active,
        "priority": policy.priority,
        "company": policy.company,
    }


@router.get("/", dependencies=[Depends(Require("expenses:read"))])
async def list_policies(
    include_inactive: bool = Query(default=False, description="Include inactive policies"),
    category_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(ExpensePolicy)
    if category_id:
        query = query.filter(ExpensePolicy.category_id == category_id)
    if not include_inactive:
        query = query.filter(ExpensePolicy.is_active.is_(True))
    policies = query.order_by(ExpensePolicy.priority.desc()).all()
    return {
        "items": [_serialize_policy(p) for p in policies],
        "total": len(policies),
    }


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(Require("expenses:write"))])
async def create_policy(payload: ExpensePolicyCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    policy = ExpensePolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _serialize_policy(policy)


@router.put("/{policy_id}", dependencies=[Depends(Require("expenses:write"))])
async def update_policy(policy_id: int, payload: ExpensePolicyCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    policy = db.query(ExpensePolicy).filter(ExpensePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return _serialize_policy(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Require("expenses:write"))])
async def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(ExpensePolicy).filter(ExpensePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return None
