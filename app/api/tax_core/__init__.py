"""
Generic Tax Configuration API

Provides country-agnostic tax management endpoints:
- /tax-core/regions - Tax region management
- /tax-core/categories - Tax category (VAT, WHT, etc.) management
- /tax-core/rates - Tax rate configuration
- /tax-core/transactions - Tax transaction ledger
- /tax-core/company-settings - Company-specific tax settings

All endpoints require appropriate admin permissions.
"""

import re
from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.tax_config import (
    TaxRegion,
    GenericTaxCategory as TaxCategory,  # Alias for backward compatibility
    TaxRate,
    TaxTransaction,
    CompanyTaxSettings,
    TaxCategoryType,
    TaxTransactionType,
    TaxFilingFrequency,
    TaxTransactionStatus,
)

router = APIRouter(prefix="/tax-core", tags=["Tax Core"])


# ============= SCHEMAS =============


class TaxRegionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., max_length=100)
    currency: str = Field(default="USD", max_length=3)
    tax_authority_name: Optional[str] = None
    tax_authority_code: Optional[str] = None
    tax_id_label: str = "Tax ID"
    tax_id_format: Optional[str] = None
    default_sales_tax_rate: Decimal = Decimal("0")
    default_withholding_rate: Decimal = Decimal("0")
    default_filing_frequency: str = "monthly"
    filing_deadline_day: int = 21
    fiscal_year_start_month: int = 1
    requires_compliance_addon: bool = False
    compliance_addon_code: Optional[str] = None
    is_active: bool = True


class TaxRegionUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    tax_authority_name: Optional[str] = None
    tax_authority_code: Optional[str] = None
    tax_id_label: Optional[str] = None
    tax_id_format: Optional[str] = None
    default_sales_tax_rate: Optional[Decimal] = None
    default_withholding_rate: Optional[Decimal] = None
    default_filing_frequency: Optional[str] = None
    filing_deadline_day: Optional[int] = None
    fiscal_year_start_month: Optional[int] = None
    requires_compliance_addon: Optional[bool] = None
    compliance_addon_code: Optional[str] = None
    is_active: Optional[bool] = None


class TaxCategoryCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    category_type: str  # sales_tax, withholding, income_tax, etc.
    default_rate: Decimal = Decimal("0")
    is_recoverable: bool = True
    is_inclusive: bool = False
    applies_to_purchases: bool = True
    applies_to_sales: bool = True
    filing_frequency: Optional[str] = None
    filing_deadline_day: Optional[int] = None
    output_account: Optional[str] = None
    input_account: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class TaxCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_type: Optional[str] = None
    default_rate: Optional[Decimal] = None
    is_recoverable: Optional[bool] = None
    is_inclusive: Optional[bool] = None
    applies_to_purchases: Optional[bool] = None
    applies_to_sales: Optional[bool] = None
    filing_frequency: Optional[str] = None
    filing_deadline_day: Optional[int] = None
    output_account: Optional[str] = None
    input_account: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class TaxRateCreate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    rate: Decimal
    conditions: Optional[dict] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True


class TaxTransactionCreate(BaseModel):
    category_id: int
    transaction_type: str  # output, input, withholding, remittance
    transaction_date: date
    company: str
    party_type: str = Field(..., pattern="^(customer|supplier|employee|company|other)$")
    party_id: Optional[int] = None
    party_name: str
    party_tax_id: Optional[str] = None
    taxable_amount: Decimal = Field(..., ge=0)
    tax_rate: Decimal = Field(..., ge=0)
    tax_amount: Optional[Decimal] = None
    currency: str = "USD"
    exchange_rate: Decimal = Decimal("1")
    filing_period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    is_exempt: bool = False
    is_zero_rated: bool = False
    exemption_reason: Optional[str] = None
    source_doctype: str
    source_docname: str
    metadata: Optional[dict] = None


class CompanyTaxSettingsCreate(BaseModel):
    company: str
    tax_id: Optional[str] = None
    vat_registration_number: Optional[str] = None
    registration_number: Optional[str] = None
    filing_frequency: Optional[str] = None
    is_registered: bool = True
    is_withholding_agent: bool = False
    fiscal_year_start_month: Optional[int] = None
    is_active: bool = True


class CompanyTaxSettingsUpdate(BaseModel):
    tax_id: Optional[str] = None
    vat_registration_number: Optional[str] = None
    registration_number: Optional[str] = None
    filing_frequency: Optional[str] = None
    is_registered: Optional[bool] = None
    is_withholding_agent: Optional[bool] = None
    fiscal_year_start_month: Optional[int] = None
    is_active: Optional[bool] = None


# ============= TAX REGIONS =============


@router.get("/regions", dependencies=[Depends(Require("admin:read"))])
def list_tax_regions(
    active_only: bool = True,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax regions."""
    query = db.query(TaxRegion)

    if active_only:
        query = query.filter(TaxRegion.is_active == True)
    if search:
        query = query.filter(
            or_(
                TaxRegion.code.ilike(f"%{search}%"),
                TaxRegion.name.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    regions = query.order_by(TaxRegion.code).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "currency": r.currency,
                "default_sales_tax_rate": str(r.default_sales_tax_rate),
                "default_filing_frequency": r.default_filing_frequency.value if r.default_filing_frequency else None,
                "requires_compliance_addon": r.requires_compliance_addon,
                "is_active": r.is_active,
            }
            for r in regions
        ],
    }


@router.get("/regions/{region_id}", dependencies=[Depends(Require("admin:read"))])
def get_tax_region(
    region_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax region detail."""
    r = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Tax region not found")

    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "currency": r.currency,
        "tax_authority_name": r.tax_authority_name,
        "tax_authority_code": r.tax_authority_code,
        "tax_id_label": r.tax_id_label,
        "tax_id_format": r.tax_id_format,
        "default_sales_tax_rate": str(r.default_sales_tax_rate),
        "default_withholding_rate": str(r.default_withholding_rate),
        "default_filing_frequency": r.default_filing_frequency.value if r.default_filing_frequency else None,
        "filing_deadline_day": r.filing_deadline_day,
        "fiscal_year_start_month": r.fiscal_year_start_month,
        "requires_compliance_addon": r.requires_compliance_addon,
        "compliance_addon_code": r.compliance_addon_code,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.post("/regions", dependencies=[Depends(Require("admin:write"))])
def create_tax_region(
    payload: TaxRegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new tax region."""
    existing = db.query(TaxRegion).filter(TaxRegion.code == payload.code.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tax region {payload.code} already exists")

    try:
        filing_freq = TaxFilingFrequency(payload.default_filing_frequency)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid filing frequency: {payload.default_filing_frequency}")

    region = TaxRegion(
        code=payload.code.upper(),
        name=payload.name,
        currency=payload.currency,
        tax_authority_name=payload.tax_authority_name,
        tax_authority_code=payload.tax_authority_code,
        tax_id_label=payload.tax_id_label,
        tax_id_format=payload.tax_id_format,
        default_sales_tax_rate=payload.default_sales_tax_rate,
        default_withholding_rate=payload.default_withholding_rate,
        default_filing_frequency=filing_freq,
        filing_deadline_day=payload.filing_deadline_day,
        fiscal_year_start_month=payload.fiscal_year_start_month,
        requires_compliance_addon=payload.requires_compliance_addon,
        compliance_addon_code=payload.compliance_addon_code,
        is_active=payload.is_active,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    return {"id": region.id, "code": region.code, "name": region.name}


@router.patch("/regions/{region_id}", dependencies=[Depends(Require("admin:write"))])
def update_tax_region(
    region_id: int,
    payload: TaxRegionUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a tax region."""
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "default_filing_frequency" in update_data and update_data["default_filing_frequency"]:
        try:
            update_data["default_filing_frequency"] = TaxFilingFrequency(update_data["default_filing_frequency"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid filing frequency")

    for key, value in update_data.items():
        setattr(region, key, value)

    db.commit()
    return {"id": region.id, "code": region.code, "updated": True}


@router.delete("/regions/{region_id}", dependencies=[Depends(Require("admin:write"))])
def delete_tax_region(
    region_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a tax region."""
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    # Check for linked categories
    categories_count = db.query(TaxCategory).filter(TaxCategory.region_id == region_id).count()
    if categories_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete region with {categories_count} linked tax categories. Deactivate instead."
        )

    # Check for linked transactions
    transactions_count = db.query(TaxTransaction).filter(TaxTransaction.region_id == region_id).count()
    if transactions_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete region with {transactions_count} linked transactions. Deactivate instead."
        )

    db.delete(region)
    db.commit()

    return {"id": region_id, "deleted": True}


@router.get("/regions/code/{code}", dependencies=[Depends(Require("admin:read"))])
def get_tax_region_by_code(
    code: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax region by code."""
    r = db.query(TaxRegion).filter(TaxRegion.code == code.upper()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Tax region not found")

    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "currency": r.currency,
        "tax_authority_name": r.tax_authority_name,
        "tax_authority_code": r.tax_authority_code,
        "tax_id_label": r.tax_id_label,
        "tax_id_format": r.tax_id_format,
        "default_sales_tax_rate": str(r.default_sales_tax_rate),
        "default_withholding_rate": str(r.default_withholding_rate),
        "default_filing_frequency": r.default_filing_frequency.value if r.default_filing_frequency else None,
        "filing_deadline_day": r.filing_deadline_day,
        "fiscal_year_start_month": r.fiscal_year_start_month,
        "requires_compliance_addon": r.requires_compliance_addon,
        "compliance_addon_code": r.compliance_addon_code,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ============= TAX CATEGORIES =============


@router.get("/regions/{region_id}/categories", dependencies=[Depends(Require("admin:read"))])
def list_tax_categories(
    region_id: int,
    active_only: bool = True,
    category_type: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax categories for a region."""
    # Verify region exists
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    query = db.query(TaxCategory).filter(TaxCategory.region_id == region_id)

    if active_only:
        query = query.filter(TaxCategory.is_active == True)

    if category_type:
        try:
            ct = TaxCategoryType(category_type)
            query = query.filter(TaxCategory.category_type == ct)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category_type: {category_type}")

    total = query.count()
    categories = query.order_by(TaxCategory.display_order, TaxCategory.code).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "category_type": c.category_type.value if c.category_type else None,
                "default_rate": str(c.default_rate),
                "is_recoverable": c.is_recoverable,
                "is_active": c.is_active,
            }
            for c in categories
        ],
    }


@router.get("/categories/{category_id}", dependencies=[Depends(Require("admin:read"))])
def get_tax_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax category detail."""
    c = db.query(TaxCategory).filter(TaxCategory.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Tax category not found")

    # Get rates
    rates = db.query(TaxRate).filter(TaxRate.category_id == c.id).order_by(TaxRate.effective_from.desc()).all()

    return {
        "id": c.id,
        "region_id": c.region_id,
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "category_type": c.category_type.value if c.category_type else None,
        "default_rate": str(c.default_rate),
        "is_recoverable": c.is_recoverable,
        "is_inclusive": c.is_inclusive,
        "applies_to_purchases": c.applies_to_purchases,
        "applies_to_sales": c.applies_to_sales,
        "filing_frequency": c.filing_frequency.value if c.filing_frequency else None,
        "filing_deadline_day": c.filing_deadline_day,
        "output_account": c.output_account,
        "input_account": c.input_account,
        "display_order": c.display_order,
        "is_active": c.is_active,
        "rates": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "rate": str(r.rate),
                "effective_from": r.effective_from.isoformat() if r.effective_from else None,
                "effective_to": r.effective_to.isoformat() if r.effective_to else None,
                "is_active": r.is_active,
            }
            for r in rates
        ],
    }


@router.post("/regions/{region_id}/categories", dependencies=[Depends(Require("admin:write"))])
def create_tax_category(
    region_id: int,
    payload: TaxCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new tax category."""
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    # Check for duplicate code within region
    existing = db.query(TaxCategory).filter(
        TaxCategory.region_id == region_id,
        TaxCategory.code == payload.code.upper(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tax category with code {payload.code} already exists in this region"
        )

    try:
        cat_type = TaxCategoryType(payload.category_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category_type: {payload.category_type}")

    filing_freq = None
    if payload.filing_frequency:
        try:
            filing_freq = TaxFilingFrequency(payload.filing_frequency)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid filing_frequency: {payload.filing_frequency}")

    category = TaxCategory(
        region_id=region_id,
        code=payload.code.upper(),
        name=payload.name,
        description=payload.description,
        category_type=cat_type,
        default_rate=payload.default_rate,
        is_recoverable=payload.is_recoverable,
        is_inclusive=payload.is_inclusive,
        applies_to_purchases=payload.applies_to_purchases,
        applies_to_sales=payload.applies_to_sales,
        filing_frequency=filing_freq,
        filing_deadline_day=payload.filing_deadline_day,
        output_account=payload.output_account,
        input_account=payload.input_account,
        display_order=payload.display_order,
        is_active=payload.is_active,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    return {"id": category.id, "code": category.code, "name": category.name}


@router.patch("/categories/{category_id}", dependencies=[Depends(Require("admin:write"))])
def update_tax_category(
    category_id: int,
    payload: TaxCategoryUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a tax category."""
    category = db.query(TaxCategory).filter(TaxCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Tax category not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "category_type" in update_data and update_data["category_type"]:
        try:
            update_data["category_type"] = TaxCategoryType(update_data["category_type"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category_type")

    if "filing_frequency" in update_data and update_data["filing_frequency"]:
        try:
            update_data["filing_frequency"] = TaxFilingFrequency(update_data["filing_frequency"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid filing_frequency")

    for key, value in update_data.items():
        setattr(category, key, value)

    db.commit()
    return {"id": category.id, "code": category.code, "updated": True}


# ============= TAX RATES =============


@router.post("/categories/{category_id}/rates", dependencies=[Depends(Require("admin:write"))])
def add_tax_rate(
    category_id: int,
    payload: TaxRateCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a tax rate to a category."""
    category = db.query(TaxCategory).filter(TaxCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Tax category not found")

    rate = TaxRate(
        category_id=category_id,
        code=payload.code,
        name=payload.name,
        rate=payload.rate,
        conditions=payload.conditions,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        is_active=payload.is_active,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)

    return {
        "id": rate.id,
        "code": rate.code,
        "rate": str(rate.rate),
        "effective_from": rate.effective_from.isoformat(),
    }


@router.delete("/rates/{rate_id}", dependencies=[Depends(Require("admin:write"))])
def delete_tax_rate(
    rate_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a tax rate."""
    rate = db.query(TaxRate).filter(TaxRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Tax rate not found")

    db.delete(rate)
    db.commit()
    return {"id": rate_id, "deleted": True}


# ============= TAX TRANSACTIONS =============


@router.get("/transactions", dependencies=[Depends(Require("books:read"))])
def list_tax_transactions(
    region_id: Optional[int] = None,
    category_id: Optional[int] = None,
    company: Optional[str] = None,
    filing_period: Optional[str] = None,
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax transactions with filtering."""
    query = db.query(TaxTransaction)

    if region_id:
        query = query.filter(TaxTransaction.region_id == region_id)
    if category_id:
        query = query.filter(TaxTransaction.category_id == category_id)
    if company:
        query = query.filter(TaxTransaction.company == company)
    if filing_period:
        # Validate filing period format (YYYY-MM)
        if not re.match(r"^\d{4}-\d{2}$", filing_period):
            raise HTTPException(status_code=400, detail="Invalid filing_period format. Use YYYY-MM")
        try:
            year, month = map(int, filing_period.split("-"))
            if month < 1 or month > 12:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid filing_period. Month must be 01-12")
        query = query.filter(TaxTransaction.filing_period == filing_period)
    if transaction_type:
        try:
            tt = TaxTransactionType(transaction_type)
            query = query.filter(TaxTransaction.transaction_type == tt)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid transaction_type: {transaction_type}")
    if status:
        try:
            st = TaxTransactionStatus(status)
            query = query.filter(TaxTransaction.status == st)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    transactions = query.order_by(TaxTransaction.transaction_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "reference_number": t.reference_number,
                "transaction_type": t.transaction_type.value if t.transaction_type else None,
                "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
                "company": t.company,
                "party_name": t.party_name,
                "taxable_amount": str(t.taxable_amount),
                "tax_amount": str(t.tax_amount),
                "filing_period": t.filing_period,
                "status": t.status.value if t.status else None,
            }
            for t in transactions
        ],
    }


@router.post("/regions/{region_id}/transactions", dependencies=[Depends(Require("books:write"))])
def create_tax_transaction(
    region_id: int,
    payload: TaxTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Record a new tax transaction."""
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    category = db.query(TaxCategory).filter(TaxCategory.id == payload.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Tax category not found")
    if category.region_id != region_id:
        raise HTTPException(status_code=400, detail="Tax category does not belong to this region")

    try:
        trans_type = TaxTransactionType(payload.transaction_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid transaction_type: {payload.transaction_type}")

    # Validate filing period format and month
    try:
        year, month = map(int, payload.filing_period.split("-"))
        if month < 1 or month > 12:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filing_period. Use YYYY-MM")

    # Generate reference number
    ref_number = f"TAX-{payload.filing_period}-{uuid4().hex[:8].upper()}"

    # Calculate tax amount server-side
    if payload.is_exempt or payload.is_zero_rated:
        tax_amount = Decimal("0")
    else:
        tax_amount = (payload.taxable_amount * payload.tax_rate).quantize(Decimal("0.01"))

    base_tax_amount = (tax_amount * payload.exchange_rate).quantize(Decimal("0.01"))

    transaction = TaxTransaction(
        region_id=region_id,
        category_id=payload.category_id,
        reference_number=ref_number,
        transaction_type=trans_type,
        transaction_date=payload.transaction_date,
        company=payload.company,
        party_type=payload.party_type,
        party_id=payload.party_id,
        party_name=payload.party_name,
        party_tax_id=payload.party_tax_id,
        taxable_amount=payload.taxable_amount,
        tax_rate=payload.tax_rate,
        tax_amount=tax_amount,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        base_tax_amount=base_tax_amount,
        filing_period=payload.filing_period,
        is_exempt=payload.is_exempt,
        is_zero_rated=payload.is_zero_rated,
        exemption_reason=payload.exemption_reason,
        source_doctype=payload.source_doctype,
        source_docname=payload.source_docname,
        meta=payload.metadata,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {
        "id": transaction.id,
        "reference_number": transaction.reference_number,
        "tax_amount": str(transaction.tax_amount),
    }


@router.get("/transactions/summary", dependencies=[Depends(Require("books:read"))])
def get_tax_summary(
    region_id: int,
    filing_period: str,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax summary for a filing period."""
    query = db.query(TaxTransaction).filter(
        TaxTransaction.region_id == region_id,
        TaxTransaction.filing_period == filing_period,
        TaxTransaction.status != TaxTransactionStatus.VOID,
    )

    if company:
        query = query.filter(TaxTransaction.company == company)

    transactions = query.all()

    # Aggregate by transaction type
    output_total = sum(t.base_tax_amount for t in transactions if t.transaction_type == TaxTransactionType.OUTPUT)
    input_total = sum(t.base_tax_amount for t in transactions if t.transaction_type == TaxTransactionType.INPUT)
    withholding_total = sum(t.base_tax_amount for t in transactions if t.transaction_type == TaxTransactionType.WITHHOLDING)

    return {
        "region_id": region_id,
        "filing_period": filing_period,
        "company": company,
        "output_tax": str(output_total),
        "input_tax": str(input_total),
        "net_payable": str(output_total - input_total),
        "withholding_tax": str(withholding_total),
        "transaction_count": len(transactions),
    }


# ============= COMPANY TAX SETTINGS =============


@router.get("/company-settings", dependencies=[Depends(Require("books:read"))])
def list_company_tax_settings(
    company: Optional[str] = None,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List company tax settings."""
    query = db.query(CompanyTaxSettings)

    if company:
        query = query.filter(CompanyTaxSettings.company == company)
    if region_id:
        query = query.filter(CompanyTaxSettings.region_id == region_id)

    settings = query.all()

    return {
        "data": [
            {
                "id": s.id,
                "region_id": s.region_id,
                "company": s.company,
                "tax_id": s.tax_id,
                "vat_registration_number": s.vat_registration_number,
                "is_registered": s.is_registered,
                "is_withholding_agent": s.is_withholding_agent,
                "is_active": s.is_active,
            }
            for s in settings
        ],
    }


@router.post("/regions/{region_id}/company-settings", dependencies=[Depends(Require("books:write"))])
def create_company_tax_settings(
    region_id: int,
    payload: CompanyTaxSettingsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create company tax settings for a region."""
    region = db.query(TaxRegion).filter(TaxRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Tax region not found")

    existing = db.query(CompanyTaxSettings).filter(
        CompanyTaxSettings.company == payload.company,
        CompanyTaxSettings.region_id == region_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Settings already exist for this company and region")

    filing_freq = None
    if payload.filing_frequency:
        try:
            filing_freq = TaxFilingFrequency(payload.filing_frequency)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid filing_frequency: {payload.filing_frequency}")

    settings = CompanyTaxSettings(
        region_id=region_id,
        company=payload.company,
        tax_id=payload.tax_id,
        vat_registration_number=payload.vat_registration_number,
        registration_number=payload.registration_number,
        filing_frequency=filing_freq,
        is_registered=payload.is_registered,
        is_withholding_agent=payload.is_withholding_agent,
        fiscal_year_start_month=payload.fiscal_year_start_month,
        is_active=payload.is_active,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)

    return {"id": settings.id, "company": settings.company, "region_id": region_id}


@router.patch("/company-settings/{settings_id}", dependencies=[Depends(Require("books:write"))])
def update_company_tax_settings(
    settings_id: int,
    payload: CompanyTaxSettingsUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update company tax settings."""
    settings = db.query(CompanyTaxSettings).filter(CompanyTaxSettings.id == settings_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Company tax settings not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "filing_frequency" in update_data and update_data["filing_frequency"]:
        try:
            update_data["filing_frequency"] = TaxFilingFrequency(update_data["filing_frequency"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid filing_frequency")

    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    return {"id": settings.id, "company": settings.company, "updated": True}


# ============= UTILITY ENDPOINTS =============


@router.get("/enums", dependencies=[Depends(Require("admin:read"))])
def get_tax_enums() -> Dict[str, Any]:
    """Get available enum values for tax configuration."""
    return {
        "category_types": [e.value for e in TaxCategoryType],
        "transaction_types": [e.value for e in TaxTransactionType],
        "filing_frequencies": [e.value for e in TaxFilingFrequency],
        "transaction_statuses": [e.value for e in TaxTransactionStatus],
    }
