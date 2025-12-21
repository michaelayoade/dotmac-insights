"""
Payroll Configuration API

Admin endpoints for managing generic payroll configuration:
- PayrollRegion: Country/region-specific settings
- DeductionRule: Configurable deduction/contribution rules
- TaxBand: Progressive tax brackets

All endpoints require admin:write permission.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)

router = APIRouter(prefix="/payroll-config", tags=["Payroll Configuration"])


# ============= SCHEMAS =============


class PayrollRegionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=10, description="ISO 3166-1 alpha-2 code")
    name: str = Field(..., max_length=100)
    currency: str = Field(default="USD", max_length=3)
    default_pay_frequency: Optional[str] = "monthly"
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    payment_day: int = Field(default=28, ge=1, le=31)
    has_statutory_deductions: bool = False
    requires_compliance_addon: bool = False
    compliance_addon_code: Optional[str] = None
    tax_authority_name: Optional[str] = None
    tax_id_label: str = "Tax ID"
    tax_id_format: Optional[str] = None
    paye_filing_frequency: Optional[str] = None
    paye_filing_deadline_day: Optional[int] = None
    is_active: bool = True


class PayrollRegionUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    default_pay_frequency: Optional[str] = None
    fiscal_year_start_month: Optional[int] = None
    payment_day: Optional[int] = None
    has_statutory_deductions: Optional[bool] = None
    requires_compliance_addon: Optional[bool] = None
    compliance_addon_code: Optional[str] = None
    tax_authority_name: Optional[str] = None
    tax_id_label: Optional[str] = None
    tax_id_format: Optional[str] = None
    paye_filing_frequency: Optional[str] = None
    paye_filing_deadline_day: Optional[int] = None
    is_active: Optional[bool] = None


class TaxBandCreate(BaseModel):
    lower_limit: Decimal
    upper_limit: Optional[Decimal] = None
    rate: Decimal = Field(..., ge=0, le=1, description="Rate as decimal (0.07 for 7%)")
    band_order: int = 0


class DeductionRuleCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    deduction_type: str  # tax, pension, insurance, levy, other
    applicability: str = "employee"  # employee, employer, both
    is_statutory: bool = False
    calc_method: str  # flat, percentage, progressive
    rate: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    employee_share: Optional[Decimal] = None
    employer_share: Optional[Decimal] = None
    base_components: Optional[List[str]] = None
    min_base: Optional[Decimal] = None
    max_base: Optional[Decimal] = None
    cap_amount: Optional[Decimal] = None
    floor_amount: Optional[Decimal] = None
    employment_types: Optional[List[str]] = None
    min_service_months: int = 0
    effective_from: date
    effective_to: Optional[date] = None
    statutory_code: Optional[str] = None
    filing_frequency: Optional[str] = None
    remittance_deadline_days: Optional[int] = None
    display_order: int = 0
    is_active: bool = True
    tax_bands: Optional[List[TaxBandCreate]] = None


class DeductionRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    deduction_type: Optional[str] = None
    applicability: Optional[str] = None
    is_statutory: Optional[bool] = None
    calc_method: Optional[str] = None
    rate: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    employee_share: Optional[Decimal] = None
    employer_share: Optional[Decimal] = None
    base_components: Optional[List[str]] = None
    min_base: Optional[Decimal] = None
    max_base: Optional[Decimal] = None
    cap_amount: Optional[Decimal] = None
    floor_amount: Optional[Decimal] = None
    employment_types: Optional[List[str]] = None
    min_service_months: Optional[int] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    statutory_code: Optional[str] = None
    filing_frequency: Optional[str] = None
    remittance_deadline_days: Optional[int] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


# ============= PAYROLL REGIONS =============


@router.get("/regions", dependencies=[Depends(Require("admin:read"))])
def list_regions(
    active_only: bool = True,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payroll regions."""
    query = db.query(PayrollRegion)

    if active_only:
        query = query.filter(PayrollRegion.is_active == True)
    if search:
        query = query.filter(
            or_(
                PayrollRegion.code.ilike(f"%{search}%"),
                PayrollRegion.name.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    regions = query.order_by(PayrollRegion.code).offset(offset).limit(limit).all()

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
                "default_pay_frequency": r.default_pay_frequency.value if r.default_pay_frequency else None,
                "has_statutory_deductions": r.has_statutory_deductions,
                "requires_compliance_addon": r.requires_compliance_addon,
                "compliance_addon_code": r.compliance_addon_code,
                "is_active": r.is_active,
            }
            for r in regions
        ],
    }


@router.get("/regions/{region_id}", dependencies=[Depends(Require("admin:read"))])
def get_region(
    region_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll region detail."""
    r = db.query(PayrollRegion).filter(PayrollRegion.id == region_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Region not found")

    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "currency": r.currency,
        "default_pay_frequency": r.default_pay_frequency.value if r.default_pay_frequency else None,
        "fiscal_year_start_month": r.fiscal_year_start_month,
        "payment_day": r.payment_day,
        "has_statutory_deductions": r.has_statutory_deductions,
        "requires_compliance_addon": r.requires_compliance_addon,
        "compliance_addon_code": r.compliance_addon_code,
        "tax_authority_name": r.tax_authority_name,
        "tax_id_label": r.tax_id_label,
        "tax_id_format": r.tax_id_format,
        "paye_filing_frequency": r.paye_filing_frequency,
        "paye_filing_deadline_day": r.paye_filing_deadline_day,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("/regions", dependencies=[Depends(Require("admin:write"))])
def create_region(
    payload: PayrollRegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new payroll region."""
    # Check if code already exists
    existing = db.query(PayrollRegion).filter(PayrollRegion.code == payload.code.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Region with code {payload.code} already exists")

    # Parse frequency enum
    try:
        frequency = PayrollFrequency(payload.default_pay_frequency) if payload.default_pay_frequency else PayrollFrequency.MONTHLY
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid pay frequency: {payload.default_pay_frequency}")

    region = PayrollRegion(
        code=payload.code.upper(),
        name=payload.name,
        currency=payload.currency,
        default_pay_frequency=frequency,
        fiscal_year_start_month=payload.fiscal_year_start_month,
        payment_day=payload.payment_day,
        has_statutory_deductions=payload.has_statutory_deductions,
        requires_compliance_addon=payload.requires_compliance_addon,
        compliance_addon_code=payload.compliance_addon_code,
        tax_authority_name=payload.tax_authority_name,
        tax_id_label=payload.tax_id_label,
        tax_id_format=payload.tax_id_format,
        paye_filing_frequency=payload.paye_filing_frequency,
        paye_filing_deadline_day=payload.paye_filing_deadline_day,
        is_active=payload.is_active,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    return {"id": region.id, "code": region.code, "name": region.name}


@router.patch("/regions/{region_id}", dependencies=[Depends(Require("admin:write"))])
def update_region(
    region_id: int,
    payload: PayrollRegionUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payroll region."""
    region = db.query(PayrollRegion).filter(PayrollRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle frequency enum
    if "default_pay_frequency" in update_data and update_data["default_pay_frequency"]:
        try:
            update_data["default_pay_frequency"] = PayrollFrequency(update_data["default_pay_frequency"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid pay frequency")

    for key, value in update_data.items():
        setattr(region, key, value)

    db.commit()
    db.refresh(region)

    return {"id": region.id, "code": region.code, "name": region.name, "updated": True}


@router.delete("/regions/{region_id}", dependencies=[Depends(Require("admin:write"))])
def delete_region(
    region_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a payroll region."""
    region = db.query(PayrollRegion).filter(PayrollRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Check for linked rules
    rules_count = db.query(DeductionRule).filter(DeductionRule.region_id == region_id).count()
    if rules_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete region with {rules_count} linked deduction rules. Deactivate instead."
        )

    db.delete(region)
    db.commit()

    return {"id": region_id, "deleted": True}


@router.get("/regions/code/{code}", dependencies=[Depends(Require("admin:read"))])
def get_region_by_code(
    code: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll region by code."""
    r = db.query(PayrollRegion).filter(PayrollRegion.code == code.upper()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Region not found")

    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "currency": r.currency,
        "default_pay_frequency": r.default_pay_frequency.value if r.default_pay_frequency else None,
        "fiscal_year_start_month": r.fiscal_year_start_month,
        "payment_day": r.payment_day,
        "has_statutory_deductions": r.has_statutory_deductions,
        "requires_compliance_addon": r.requires_compliance_addon,
        "compliance_addon_code": r.compliance_addon_code,
        "tax_authority_name": r.tax_authority_name,
        "tax_id_label": r.tax_id_label,
        "tax_id_format": r.tax_id_format,
        "paye_filing_frequency": r.paye_filing_frequency,
        "paye_filing_deadline_day": r.paye_filing_deadline_day,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ============= DEDUCTION RULES =============


@router.get("/regions/{region_id}/rules", dependencies=[Depends(Require("admin:read"))])
def list_rules(
    region_id: int,
    active_only: bool = True,
    deduction_type: Optional[str] = None,
    statutory_only: bool = False,
    calc_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List deduction rules for a region."""
    # Verify region exists
    region = db.query(PayrollRegion).filter(PayrollRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    if calc_date is None:
        calc_date = date.today()

    query = db.query(DeductionRule).filter(DeductionRule.region_id == region_id)

    if active_only:
        query = query.filter(
            DeductionRule.is_active == True,
            DeductionRule.effective_from <= calc_date,
            or_(
                DeductionRule.effective_to.is_(None),
                DeductionRule.effective_to >= calc_date,
            ),
        )

    if deduction_type:
        try:
            dt = DeductionType(deduction_type)
            query = query.filter(DeductionRule.deduction_type == dt)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid deduction_type: {deduction_type}")

    if statutory_only:
        query = query.filter(DeductionRule.is_statutory == True)

    total = query.count()
    rules = query.order_by(DeductionRule.display_order, DeductionRule.code).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "deduction_type": r.deduction_type.value if r.deduction_type else None,
                "applicability": r.applicability.value if r.applicability else None,
                "calc_method": r.calc_method.value if r.calc_method else None,
                "is_statutory": r.is_statutory,
                "rate": str(r.rate) if r.rate else None,
                "flat_amount": str(r.flat_amount) if r.flat_amount else None,
                "effective_from": r.effective_from.isoformat() if r.effective_from else None,
                "effective_to": r.effective_to.isoformat() if r.effective_to else None,
                "is_active": r.is_active,
            }
            for r in rules
        ],
    }


@router.get("/rules/{rule_id}", dependencies=[Depends(Require("admin:read"))])
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get deduction rule detail."""
    r = db.query(DeductionRule).filter(DeductionRule.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Get tax bands if progressive
    tax_bands = []
    if r.calc_method == CalcMethod.PROGRESSIVE:
        bands = db.query(TaxBand).filter(TaxBand.deduction_rule_id == r.id).order_by(TaxBand.band_order).all()
        tax_bands = [
            {
                "id": b.id,
                "lower_limit": str(b.lower_limit),
                "upper_limit": str(b.upper_limit) if b.upper_limit else None,
                "rate": str(b.rate),
                "band_order": b.band_order,
            }
            for b in bands
        ]

    return {
        "id": r.id,
        "region_id": r.region_id,
        "code": r.code,
        "name": r.name,
        "description": r.description,
        "deduction_type": r.deduction_type.value if r.deduction_type else None,
        "applicability": r.applicability.value if r.applicability else None,
        "is_statutory": r.is_statutory,
        "calc_method": r.calc_method.value if r.calc_method else None,
        "rate": str(r.rate) if r.rate else None,
        "flat_amount": str(r.flat_amount) if r.flat_amount else None,
        "employee_share": str(r.employee_share) if r.employee_share is not None else None,
        "employer_share": str(r.employer_share) if r.employer_share is not None else None,
        "base_components": r.base_components,
        "min_base": str(r.min_base) if r.min_base else None,
        "max_base": str(r.max_base) if r.max_base else None,
        "cap_amount": str(r.cap_amount) if r.cap_amount else None,
        "floor_amount": str(r.floor_amount) if r.floor_amount else None,
        "employment_types": r.employment_types,
        "min_service_months": r.min_service_months,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "statutory_code": r.statutory_code,
        "filing_frequency": r.filing_frequency,
        "remittance_deadline_days": r.remittance_deadline_days,
        "display_order": r.display_order,
        "is_active": r.is_active,
        "tax_bands": tax_bands,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("/regions/{region_id}/rules", dependencies=[Depends(Require("admin:write"))])
def create_rule(
    region_id: int,
    payload: DeductionRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new deduction rule."""
    # Verify region exists
    region = db.query(PayrollRegion).filter(PayrollRegion.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Check for duplicate code within region
    existing = db.query(DeductionRule).filter(
        DeductionRule.region_id == region_id,
        DeductionRule.code == payload.code.upper(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Deduction rule with code {payload.code} already exists in this region"
        )

    # Parse enums
    try:
        deduction_type = DeductionType(payload.deduction_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid deduction_type: {payload.deduction_type}")

    try:
        applicability = RuleApplicability(payload.applicability)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid applicability: {payload.applicability}")

    try:
        calc_method = CalcMethod(payload.calc_method)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid calc_method: {payload.calc_method}")

    # Validate calc_method requirements
    if calc_method == CalcMethod.FLAT and payload.flat_amount is None:
        raise HTTPException(status_code=400, detail="flat_amount required for FLAT calc_method")
    if calc_method == CalcMethod.PERCENTAGE and payload.rate is None:
        raise HTTPException(status_code=400, detail="rate required for PERCENTAGE calc_method")

    employee_share = payload.employee_share
    employer_share = payload.employer_share
    if applicability == RuleApplicability.BOTH:
        if employee_share is None and employer_share is None:
            employee_share = Decimal("0.5")
            employer_share = Decimal("0.5")
        elif employee_share is None or employer_share is None:
            raise HTTPException(status_code=400, detail="Both employee_share and employer_share are required")
        else:
            if (employee_share + employer_share) != Decimal("1"):
                raise HTTPException(status_code=400, detail="employee_share + employer_share must equal 1")
    else:
        employee_share = None
        employer_share = None

    rule = DeductionRule(
        region_id=region_id,
        code=payload.code.upper(),
        name=payload.name,
        description=payload.description,
        deduction_type=deduction_type,
        applicability=applicability,
        is_statutory=payload.is_statutory,
        calc_method=calc_method,
        rate=payload.rate,
        flat_amount=payload.flat_amount,
        employee_share=employee_share,
        employer_share=employer_share,
        base_components=payload.base_components,
        min_base=payload.min_base,
        max_base=payload.max_base,
        cap_amount=payload.cap_amount,
        floor_amount=payload.floor_amount,
        employment_types=payload.employment_types,
        min_service_months=payload.min_service_months,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        statutory_code=payload.statutory_code,
        filing_frequency=payload.filing_frequency,
        remittance_deadline_days=payload.remittance_deadline_days,
        display_order=payload.display_order,
        is_active=payload.is_active,
        created_by_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    db.add(rule)
    db.flush()

    # Add tax bands if provided and calc_method is progressive
    if calc_method == CalcMethod.PROGRESSIVE and payload.tax_bands:
        for i, band_data in enumerate(payload.tax_bands):
            band = TaxBand(
                deduction_rule_id=rule.id,
                lower_limit=band_data.lower_limit,
                upper_limit=band_data.upper_limit,
                rate=band_data.rate,
                band_order=band_data.band_order if band_data.band_order else i,
            )
            db.add(band)

    db.commit()
    db.refresh(rule)

    return {"id": rule.id, "code": rule.code, "name": rule.name}


@router.patch("/rules/{rule_id}", dependencies=[Depends(Require("admin:write"))])
def update_rule(
    rule_id: int,
    payload: DeductionRuleUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a deduction rule."""
    rule = db.query(DeductionRule).filter(DeductionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle enums
    if "deduction_type" in update_data and update_data["deduction_type"]:
        try:
            update_data["deduction_type"] = DeductionType(update_data["deduction_type"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid deduction_type")

    if "applicability" in update_data and update_data["applicability"]:
        try:
            update_data["applicability"] = RuleApplicability(update_data["applicability"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid applicability")

    if "calc_method" in update_data and update_data["calc_method"]:
        try:
            update_data["calc_method"] = CalcMethod(update_data["calc_method"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid calc_method")

    new_applicability = update_data.get("applicability", rule.applicability)
    employee_share = update_data.get("employee_share", rule.employee_share)
    employer_share = update_data.get("employer_share", rule.employer_share)

    if new_applicability == RuleApplicability.BOTH:
        if employee_share is None and employer_share is None:
            employee_share = Decimal("0.5")
            employer_share = Decimal("0.5")
        elif employee_share is None or employer_share is None:
            raise HTTPException(status_code=400, detail="Both employee_share and employer_share are required")
        else:
            if (employee_share + employer_share) != Decimal("1"):
                raise HTTPException(status_code=400, detail="employee_share + employer_share must equal 1")
    else:
        employee_share = None
        employer_share = None

    update_data["employee_share"] = employee_share
    update_data["employer_share"] = employer_share

    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)

    return {"id": rule.id, "code": rule.code, "name": rule.name, "updated": True}


@router.delete("/rules/{rule_id}", dependencies=[Depends(Require("admin:write"))])
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a deduction rule and its tax bands."""
    rule = db.query(DeductionRule).filter(DeductionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Delete tax bands first (cascade should handle this, but be explicit)
    db.query(TaxBand).filter(TaxBand.deduction_rule_id == rule_id).delete()

    db.delete(rule)
    db.commit()

    return {"id": rule_id, "deleted": True}


# ============= TAX BANDS =============


@router.post("/rules/{rule_id}/bands", dependencies=[Depends(Require("admin:write"))])
def add_tax_band(
    rule_id: int,
    payload: TaxBandCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a tax band to a progressive rule."""
    rule = db.query(DeductionRule).filter(DeductionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if rule.calc_method != CalcMethod.PROGRESSIVE:
        raise HTTPException(status_code=400, detail="Tax bands only apply to PROGRESSIVE rules")

    band = TaxBand(
        deduction_rule_id=rule_id,
        lower_limit=payload.lower_limit,
        upper_limit=payload.upper_limit,
        rate=payload.rate,
        band_order=payload.band_order,
    )
    db.add(band)
    db.commit()
    db.refresh(band)

    return {
        "id": band.id,
        "lower_limit": str(band.lower_limit),
        "upper_limit": str(band.upper_limit) if band.upper_limit else None,
        "rate": str(band.rate),
        "band_order": band.band_order,
    }


@router.delete("/bands/{band_id}", dependencies=[Depends(Require("admin:write"))])
def delete_tax_band(
    band_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a tax band."""
    band = db.query(TaxBand).filter(TaxBand.id == band_id).first()
    if not band:
        raise HTTPException(status_code=404, detail="Tax band not found")

    db.delete(band)
    db.commit()

    return {"id": band_id, "deleted": True}


# ============= UTILITY ENDPOINTS =============


@router.get("/enums", dependencies=[Depends(Require("admin:read"))])
def get_enums() -> Dict[str, Any]:
    """Get available enum values for payroll configuration."""
    return {
        "calc_methods": [e.value for e in CalcMethod],
        "deduction_types": [e.value for e in DeductionType],
        "payroll_frequencies": [e.value for e in PayrollFrequency],
        "rule_applicabilities": [e.value for e in RuleApplicability],
    }
