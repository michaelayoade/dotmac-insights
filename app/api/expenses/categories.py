"""Expense category endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.expenses.schemas import ExpenseCategoryCreate, ExpenseCategoryRead
from app.database import get_db
from app.models.expense_management import ExpenseCategory

router = APIRouter()


@router.get("/", response_model=List[ExpenseCategoryRead])
async def list_categories(
    include_inactive: bool = Query(default=False, description="Include inactive categories"),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseCategory)
    if not include_inactive:
        query = query.filter(ExpenseCategory.is_active.is_(True))
    return query.order_by(ExpenseCategory.code).all()


@router.post("/", response_model=ExpenseCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: ExpenseCategoryCreate, db: Session = Depends(get_db)):
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
    return category


@router.put("/{category_id}", response_model=ExpenseCategoryRead)
async def update_category(category_id: int, payload: ExpenseCategoryCreate, db: Session = Depends(get_db)):
    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in payload.model_dump().items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(status_code=400, detail="System categories cannot be deleted")

    db.delete(category)
    db.commit()
    return None
