"""
Salary Structures Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.models.hr_payroll import (
    SalaryStructure,
    SalaryStructureEarning,
    SalaryStructureDeduction,
)
from .helpers import decimal_or_default

router = APIRouter()

# =============================================================================
# SALARY STRUCTURE
# =============================================================================

class SalaryStructureComponentPayload(BaseModel):
    salary_component: str
    abbr: Optional[str] = None
    amount: Optional[Decimal] = Decimal("0")
    amount_based_on_formula: Optional[bool] = False
    formula: Optional[str] = None
    condition: Optional[str] = None
    statistical_component: Optional[bool] = False
    do_not_include_in_total: Optional[bool] = False
    idx: Optional[int] = 0


class SalaryStructureCreate(BaseModel):
    salary_structure_name: str
    company: Optional[str] = None
    is_active: Optional[str] = "Yes"
    payroll_frequency: Optional[str] = None
    currency: Optional[str] = "USD"
    payment_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    earnings: Optional[List[SalaryStructureComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalaryStructureComponentPayload]] = Field(default=None)


class SalaryStructureUpdate(BaseModel):
    salary_structure_name: Optional[str] = None
    company: Optional[str] = None
    is_active: Optional[str] = None
    payroll_frequency: Optional[str] = None
    currency: Optional[str] = None
    payment_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    earnings: Optional[List[SalaryStructureComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalaryStructureComponentPayload]] = Field(default=None)


@router.get("/salary-structures", dependencies=[Depends(Require("hr:read"))])
def list_salary_structures(
    is_active: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List salary structures with filtering."""
    query = db.query(SalaryStructure)

    if is_active:
        query = query.filter(SalaryStructure.is_active == is_active)
    if company:
        query = query.filter(SalaryStructure.company.ilike(f"%{company}%"))
    if search:
        query = query.filter(SalaryStructure.salary_structure_name.ilike(f"%{search}%"))

    total = query.count()
    structures = query.order_by(SalaryStructure.salary_structure_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "salary_structure_name": s.salary_structure_name,
                "company": s.company,
                "is_active": s.is_active,
                "payroll_frequency": s.payroll_frequency,
                "currency": s.currency,
                "earnings_count": len(s.earnings),
                "deductions_count": len(s.deductions),
            }
            for s in structures
        ],
    }


@router.get("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_structure(
    structure_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary structure detail with earnings and deductions."""
    s = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    earnings = [
        {
            "id": e.id,
            "salary_component": e.salary_component,
            "abbr": e.abbr,
            "amount": float(e.amount) if e.amount else 0,
            "amount_based_on_formula": e.amount_based_on_formula,
            "formula": e.formula,
            "condition": e.condition,
            "statistical_component": e.statistical_component,
            "do_not_include_in_total": e.do_not_include_in_total,
            "idx": e.idx,
        }
        for e in sorted(s.earnings, key=lambda x: x.idx)
    ]

    deductions = [
        {
            "id": d.id,
            "salary_component": d.salary_component,
            "abbr": d.abbr,
            "amount": float(d.amount) if d.amount else 0,
            "amount_based_on_formula": d.amount_based_on_formula,
            "formula": d.formula,
            "condition": d.condition,
            "statistical_component": d.statistical_component,
            "do_not_include_in_total": d.do_not_include_in_total,
            "idx": d.idx,
        }
        for d in sorted(s.deductions, key=lambda x: x.idx)
    ]

    return {
        "id": s.id,
        "erpnext_id": s.erpnext_id,
        "salary_structure_name": s.salary_structure_name,
        "company": s.company,
        "is_active": s.is_active,
        "payroll_frequency": s.payroll_frequency,
        "currency": s.currency,
        "payment_account": s.payment_account,
        "mode_of_payment": s.mode_of_payment,
        "earnings": earnings,
        "deductions": deductions,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post("/salary-structures", dependencies=[Depends(Require("hr:write"))])
def create_salary_structure(
    payload: SalaryStructureCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new salary structure with earnings and deductions."""
    structure = SalaryStructure(
        salary_structure_name=payload.salary_structure_name,
        company=payload.company,
        is_active=payload.is_active or "Yes",
        payroll_frequency=payload.payroll_frequency,
        currency=payload.currency or "USD",
        payment_account=payload.payment_account,
        mode_of_payment=payload.mode_of_payment,
    )
    db.add(structure)
    db.flush()

    if payload.earnings:
        for idx, e in enumerate(payload.earnings):
            earning = SalaryStructureEarning(
                salary_structure_id=structure.id,
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=decimal_or_default(e.amount),
                amount_based_on_formula=e.amount_based_on_formula or False,
                formula=e.formula,
                condition=e.condition,
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            )
            db.add(earning)

    if payload.deductions:
        for idx, d in enumerate(payload.deductions):
            deduction = SalaryStructureDeduction(
                salary_structure_id=structure.id,
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=decimal_or_default(d.amount),
                amount_based_on_formula=d.amount_based_on_formula or False,
                formula=d.formula,
                condition=d.condition,
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(deduction)

    db.commit()
    return get_salary_structure(structure.id, db)


@router.patch("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_structure(
    structure_id: int,
    payload: SalaryStructureUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a salary structure and optionally replace earnings/deductions."""
    structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not structure:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    update_data = payload.model_dump(exclude_unset=True)
    earnings_data = update_data.pop("earnings", None)
    deductions_data = update_data.pop("deductions", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(structure, field, value)

    if earnings_data is not None:
        db.query(SalaryStructureEarning).filter(
            SalaryStructureEarning.salary_structure_id == structure.id
        ).delete(synchronize_session=False)
        for idx, e in enumerate(earnings_data):
            earning = SalaryStructureEarning(
                salary_structure_id=structure.id,
                salary_component=e.get("salary_component"),
                abbr=e.get("abbr"),
                amount=decimal_or_default(e.get("amount")),
                amount_based_on_formula=e.get("amount_based_on_formula", False),
                formula=e.get("formula"),
                condition=e.get("condition"),
                statistical_component=e.get("statistical_component", False),
                do_not_include_in_total=e.get("do_not_include_in_total", False),
                idx=e.get("idx") if e.get("idx") is not None else idx,
            )
            db.add(earning)

    if deductions_data is not None:
        db.query(SalaryStructureDeduction).filter(
            SalaryStructureDeduction.salary_structure_id == structure.id
        ).delete(synchronize_session=False)
        for idx, d in enumerate(deductions_data):
            deduction = SalaryStructureDeduction(
                salary_structure_id=structure.id,
                salary_component=d.get("salary_component"),
                abbr=d.get("abbr"),
                amount=decimal_or_default(d.get("amount")),
                amount_based_on_formula=d.get("amount_based_on_formula", False),
                formula=d.get("formula"),
                condition=d.get("condition"),
                statistical_component=d.get("statistical_component", False),
                do_not_include_in_total=d.get("do_not_include_in_total", False),
                idx=d.get("idx") if d.get("idx") is not None else idx,
            )
            db.add(deduction)

    db.commit()
    return get_salary_structure(structure.id, db)


@router.delete("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_structure(
    structure_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a salary structure."""
    structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not structure:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    db.delete(structure)
    db.commit()
    return {"message": "Salary structure deleted", "id": structure_id}


