"""
Salary Structures Endpoints

Uses PayrollService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import (
    SalaryStructureFilters,
    SalaryStructureCreateData,
    SalaryStructureUpdateData,
    StructureEarningData,
    StructureDeductionData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import SalaryStructureNotFoundError, ValidationError as HRValidationError

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


def _serialize_structure(s, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a SalaryStructure model to dict."""
    result = {
        "id": s.id,
        "erpnext_id": s.erpnext_id,
        "salary_structure_name": s.salary_structure_name,
        "company": s.company,
        "is_active": s.is_active,
        "payroll_frequency": s.payroll_frequency,
        "currency": s.currency,
        "earnings_count": len(s.earnings) if hasattr(s, 'earnings') else 0,
        "deductions_count": len(s.deductions) if hasattr(s, 'deductions') else 0,
    }
    if include_details:
        result["payment_account"] = s.payment_account
        result["mode_of_payment"] = s.mode_of_payment
        result["earnings"] = [
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
        result["deductions"] = [
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
        result["created_at"] = s.created_at.isoformat() if s.created_at else None
        result["updated_at"] = s.updated_at.isoformat() if s.updated_at else None
    return result


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
    service = PayrollService(db)

    filters = SalaryStructureFilters(
        is_active=is_active,
        company=company,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_salary_structures(filters, pagination)

    # Apply search post-query if needed
    items = result.items
    if search:
        search_lower = search.lower()
        items = [s for s in items if s.salary_structure_name and search_lower in s.salary_structure_name.lower()]

    return {
        "total": len(items) if search else result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_structure(s) for s in items],
    }


@router.get("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_structure(
    structure_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary structure detail with earnings and deductions."""
    service = PayrollService(db)
    try:
        s = service.get_salary_structure(structure_id)
    except SalaryStructureNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    return _serialize_structure(s, include_details=True)


@router.post("/salary-structures", dependencies=[Depends(Require("hr:write"))])
def create_salary_structure(
    payload: SalaryStructureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new salary structure with earnings and deductions."""
    service = PayrollService(db, current_user)

    # Convert payload earnings/deductions to service data types
    earnings_data = []
    if payload.earnings:
        for idx, e in enumerate(payload.earnings):
            earnings_data.append(StructureEarningData(
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=e.amount or Decimal("0"),
                amount_based_on_formula=e.amount_based_on_formula or False,
                formula=e.formula,
                condition=e.condition,
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            ))

    deductions_data = []
    if payload.deductions:
        for idx, d in enumerate(payload.deductions):
            deductions_data.append(StructureDeductionData(
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=d.amount or Decimal("0"),
                amount_based_on_formula=d.amount_based_on_formula or False,
                formula=d.formula,
                condition=d.condition,
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            ))

    create_data = SalaryStructureCreateData(
        salary_structure_name=payload.salary_structure_name,
        company=payload.company,
        is_active=payload.is_active or "Yes",
        payroll_frequency=payload.payroll_frequency,
        currency=payload.currency or "USD",
        payment_account=payload.payment_account,
        mode_of_payment=payload.mode_of_payment,
        earnings=earnings_data,
        deductions=deductions_data,
    )

    try:
        structure = service.create_salary_structure(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_structure(structure.id, db)


@router.patch("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_structure(
    structure_id: int,
    payload: SalaryStructureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a salary structure and optionally replace earnings/deductions."""
    service = PayrollService(db, current_user)

    # Convert payload earnings/deductions to service data types
    earnings_data = None
    if payload.earnings is not None:
        earnings_data = []
        for idx, e in enumerate(payload.earnings):
            earnings_data.append(StructureEarningData(
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=e.amount or Decimal("0"),
                amount_based_on_formula=e.amount_based_on_formula or False,
                formula=e.formula,
                condition=e.condition,
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            ))

    deductions_data = None
    if payload.deductions is not None:
        deductions_data = []
        for idx, d in enumerate(payload.deductions):
            deductions_data.append(StructureDeductionData(
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=d.amount or Decimal("0"),
                amount_based_on_formula=d.amount_based_on_formula or False,
                formula=d.formula,
                condition=d.condition,
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            ))

    update_data = SalaryStructureUpdateData(
        salary_structure_name=payload.salary_structure_name,
        company=payload.company,
        is_active=payload.is_active,
        payroll_frequency=payload.payroll_frequency,
        currency=payload.currency,
        payment_account=payload.payment_account,
        mode_of_payment=payload.mode_of_payment,
        earnings=earnings_data,
        deductions=deductions_data,
    )

    try:
        service.update_salary_structure(structure_id, update_data)
        db.commit()
    except SalaryStructureNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary structure not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_structure(structure_id, db)


@router.delete("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a salary structure."""
    service = PayrollService(db, current_user)

    try:
        service.delete_salary_structure(structure_id)
        db.commit()
    except SalaryStructureNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary structure not found")

    return {"message": "Salary structure deleted", "id": structure_id}
