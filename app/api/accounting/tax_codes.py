"""Tax Codes: CRUD endpoints for tax code management."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.tax import TaxCode, TaxType, RoundingMethod
from app.services.tax_calculator import TaxCalculator
from .helpers import paginate

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class TaxCodeCreate(BaseModel):
    """Schema for creating a tax code."""
    code: str
    name: str
    description: Optional[str] = None
    rate: float = 0
    tax_type: str = "both"  # sales, purchase, both
    is_tax_inclusive: bool = False
    rounding_method: str = "round"  # round, floor, ceil
    rounding_precision: int = 2
    jurisdiction: Optional[str] = None
    country: Optional[str] = None
    account_head: Optional[str] = None
    cost_center: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    company: Optional[str] = None


class TaxCodeUpdate(BaseModel):
    """Schema for updating a tax code."""
    name: Optional[str] = None
    description: Optional[str] = None
    rate: Optional[float] = None
    tax_type: Optional[str] = None
    is_tax_inclusive: Optional[bool] = None
    rounding_method: Optional[str] = None
    rounding_precision: Optional[int] = None
    jurisdiction: Optional[str] = None
    country: Optional[str] = None
    account_head: Optional[str] = None
    cost_center: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    is_active: Optional[bool] = None


class TaxCalculateRequest(BaseModel):
    """Schema for tax calculation request."""
    amount: float
    tax_code_id: Optional[int] = None
    tax_rate: Optional[float] = None
    is_inclusive: Optional[bool] = None


# =============================================================================
# TAX CODES LIST & DETAIL
# =============================================================================

@router.get("/tax-codes", dependencies=[Depends(Require("accounting:read"))])
def list_tax_codes(
    tax_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    country: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax codes with optional filters."""
    query = db.query(TaxCode)

    if tax_type:
        try:
            tt = TaxType(tax_type.lower())
            query = query.filter(TaxCode.tax_type == tt)
        except ValueError:
            pass

    if is_active is not None:
        query = query.filter(TaxCode.is_active == is_active)

    if country:
        query = query.filter(TaxCode.country == country)

    if jurisdiction:
        query = query.filter(TaxCode.jurisdiction == jurisdiction)

    query = query.order_by(TaxCode.code)
    total, codes = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "tax_codes": [
            {
                "id": tc.id,
                "code": tc.code,
                "name": tc.name,
                "rate": float(tc.rate),
                "tax_type": tc.tax_type.value,
                "is_tax_inclusive": tc.is_tax_inclusive,
                "is_active": tc.is_active,
                "is_valid": tc.is_valid,
                "jurisdiction": tc.jurisdiction,
                "country": tc.country,
            }
            for tc in codes
        ],
    }


@router.get("/tax-codes/{tax_code_id}", dependencies=[Depends(Require("accounting:read"))])
def get_tax_code(
    tax_code_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax code detail."""
    tc = db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Tax code not found")

    return {
        "id": tc.id,
        "code": tc.code,
        "name": tc.name,
        "description": tc.description,
        "rate": float(tc.rate),
        "tax_type": tc.tax_type.value,
        "is_tax_inclusive": tc.is_tax_inclusive,
        "rounding_method": tc.rounding_method.value,
        "rounding_precision": tc.rounding_precision,
        "jurisdiction": tc.jurisdiction,
        "country": tc.country,
        "account_head": tc.account_head,
        "cost_center": tc.cost_center,
        "valid_from": tc.valid_from.isoformat() if tc.valid_from else None,
        "valid_to": tc.valid_to.isoformat() if tc.valid_to else None,
        "is_active": tc.is_active,
        "is_valid": tc.is_valid,
        "company": tc.company,
        "created_at": tc.created_at.isoformat() if tc.created_at else None,
        "updated_at": tc.updated_at.isoformat() if tc.updated_at else None,
    }


# =============================================================================
# TAX CODES CRUD
# =============================================================================

@router.post("/tax-codes", dependencies=[Depends(Require("books:write"))])
def create_tax_code(
    data: TaxCodeCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new tax code."""
    # Check for duplicate code
    existing = db.query(TaxCode).filter(TaxCode.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tax code '{data.code}' already exists")

    # Parse enums
    try:
        tax_type_enum = TaxType(data.tax_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tax type: {data.tax_type}")

    try:
        rounding_enum = RoundingMethod(data.rounding_method.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid rounding method: {data.rounding_method}")

    # Parse dates
    valid_from = None
    valid_to = None
    if data.valid_from:
        valid_from = date.fromisoformat(data.valid_from)
    if data.valid_to:
        valid_to = date.fromisoformat(data.valid_to)

    tc = TaxCode(
        code=data.code,
        name=data.name,
        description=data.description,
        rate=Decimal(str(data.rate)),
        tax_type=tax_type_enum,
        is_tax_inclusive=data.is_tax_inclusive,
        rounding_method=rounding_enum,
        rounding_precision=data.rounding_precision,
        jurisdiction=data.jurisdiction,
        country=data.country,
        account_head=data.account_head,
        cost_center=data.cost_center,
        valid_from=valid_from,
        valid_to=valid_to,
        company=data.company,
        created_by_id=user.id,
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)

    return {
        "message": "Tax code created",
        "id": tc.id,
        "code": tc.code,
    }


@router.patch("/tax-codes/{tax_code_id}", dependencies=[Depends(Require("books:write"))])
def update_tax_code(
    tax_code_id: int,
    data: TaxCodeUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a tax code."""
    tc = db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Tax code not found")

    if data.name is not None:
        tc.name = data.name
    if data.description is not None:
        tc.description = data.description
    if data.rate is not None:
        tc.rate = Decimal(str(data.rate))
    if data.tax_type is not None:
        try:
            tc.tax_type = TaxType(data.tax_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tax type: {data.tax_type}")
    if data.is_tax_inclusive is not None:
        tc.is_tax_inclusive = data.is_tax_inclusive
    if data.rounding_method is not None:
        try:
            tc.rounding_method = RoundingMethod(data.rounding_method.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid rounding method: {data.rounding_method}")
    if data.rounding_precision is not None:
        tc.rounding_precision = data.rounding_precision
    if data.jurisdiction is not None:
        tc.jurisdiction = data.jurisdiction
    if data.country is not None:
        tc.country = data.country
    if data.account_head is not None:
        tc.account_head = data.account_head
    if data.cost_center is not None:
        tc.cost_center = data.cost_center
    if data.valid_from is not None:
        tc.valid_from = date.fromisoformat(data.valid_from) if data.valid_from else None
    if data.valid_to is not None:
        tc.valid_to = date.fromisoformat(data.valid_to) if data.valid_to else None
    if data.is_active is not None:
        tc.is_active = data.is_active

    db.commit()

    return {
        "message": "Tax code updated",
        "id": tc.id,
    }


@router.delete("/tax-codes/{tax_code_id}", dependencies=[Depends(Require("books:write"))])
def deactivate_tax_code(
    tax_code_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Deactivate (soft delete) a tax code."""
    tc = db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Tax code not found")

    tc.is_active = False
    db.commit()

    return {
        "message": "Tax code deactivated",
        "id": tc.id,
    }


# =============================================================================
# TAX CALCULATION
# =============================================================================

@router.post("/tax-codes/calculate", dependencies=[Depends(Require("accounting:read"))])
def calculate_tax(
    data: TaxCalculateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate tax for an amount."""
    calculator = TaxCalculator(db)

    tax_rate = Decimal(str(data.tax_rate)) if data.tax_rate is not None else None
    result = calculator.calculate_line_tax(
        amount=Decimal(str(data.amount)),
        tax_code_id=data.tax_code_id,
        tax_rate=tax_rate,
        is_inclusive=data.is_inclusive,
    )

    return {
        "net_amount": float(result.net_amount),
        "tax_amount": float(result.tax_amount),
        "gross_amount": float(result.gross_amount),
        "tax_rate": float(result.tax_rate),
        "is_inclusive": result.is_inclusive,
    }
