"""Expense category endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.expenses.schemas import ExpenseCategoryCreate, ExpenseCategoryRead
from app.auth import Require
from app.database import get_db
from app.models.expense_management import ExpenseCategory

router = APIRouter()


def _serialize_category(category: ExpenseCategory) -> Dict[str, Any]:
    """Serialize ExpenseCategory model to dict."""
    return {
        "id": category.id,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "parent_id": category.parent_id,
        "is_group": category.is_group,
        "expense_account": category.expense_account,
        "payable_account": category.payable_account,
        "category_type": category.category_type,
        "default_tax_code_id": category.default_tax_code_id,
        "is_tax_deductible": category.is_tax_deductible,
        "is_system": category.is_system,
        "is_active": category.is_active,
        "requires_receipt": category.requires_receipt,
        "company": category.company,
    }


@router.get("/", dependencies=[Depends(Require("expenses:read"))])
async def list_categories(
    include_inactive: bool = Query(default=False, description="Include inactive categories"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(ExpenseCategory)
    if not include_inactive:
        query = query.filter(ExpenseCategory.is_active.is_(True))
    categories = query.order_by(ExpenseCategory.code).all()
    return {
        "items": [_serialize_category(c) for c in categories],
        "total": len(categories),
    }


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(Require("expenses:write"))])
async def create_category(payload: ExpenseCategoryCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    existing = (
        db.query(ExpenseCategory)
        .filter(ExpenseCategory.code == payload.code)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Category code already exists")

    category = ExpenseCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return _serialize_category(category)


@router.put("/{category_id}", dependencies=[Depends(Require("expenses:write"))])
async def update_category(category_id: int, payload: ExpenseCategoryCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in payload.model_dump().items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return _serialize_category(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Require("expenses:write"))])
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(status_code=400, detail="System categories cannot be deleted")

    db.delete(category)
    db.commit()
    return None
