"""Expense category endpoints.

Thin wrapper around ExpenseCategoryService - all business logic is in the service.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.expenses.schemas import ExpenseCategoryCreate
from app.auth import Require
from app.database import get_db
from app.models.expense_management import ExpenseCategory
from app.services.expenses import ExpenseCategoryService
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginationParams

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
    """List expense categories using service."""
    service = ExpenseCategoryService(db)

    # Use None for is_active when include_inactive to get all
    is_active = None if include_inactive else True

    result = service.list_categories(
        is_active=is_active,
        pagination=PaginationParams(offset=0, limit=1000),
    )
    return {
        "items": [_serialize_category(c) for c in result.items],
        "total": result.total,
    }


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(Require("expenses:write"))])
async def create_category(payload: ExpenseCategoryCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create expense category via service."""
    service = ExpenseCategoryService(db)

    try:
        category = service.create_category(
            name=payload.name,
            code=payload.code,
            expense_account=payload.expense_account,
            description=payload.description,
            parent_id=payload.parent_id,
            is_group=payload.is_group or False,
            payable_account=payload.payable_account,
            category_type=payload.category_type,
            default_tax_code_id=payload.default_tax_code_id,
            is_tax_deductible=payload.is_tax_deductible if payload.is_tax_deductible is not None else True,
            requires_receipt=payload.requires_receipt if payload.requires_receipt is not None else True,
            company=payload.company,
        )
        db.commit()
        return _serialize_category(category)
    except ConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/{category_id}", dependencies=[Depends(Require("expenses:write"))])
async def update_category(category_id: int, payload: ExpenseCategoryCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Update expense category via service."""
    service = ExpenseCategoryService(db)

    try:
        category = service.update_category(
            category_id=category_id,
            name=payload.name,
            code=payload.code,
            expense_account=payload.expense_account,
            description=payload.description,
            parent_id=payload.parent_id,
            is_group=payload.is_group,
            payable_account=payload.payable_account,
            category_type=payload.category_type,
            default_tax_code_id=payload.default_tax_code_id,
            is_tax_deductible=payload.is_tax_deductible,
            requires_receipt=payload.requires_receipt,
        )
        db.commit()
        return _serialize_category(category)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Category not found")
    except ConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Require("expenses:write"))])
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete expense category via service (soft delete)."""
    service = ExpenseCategoryService(db)

    try:
        service.delete_category(category_id)
        db.commit()
        return None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Category not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
