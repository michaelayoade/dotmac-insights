"""
Salary Assignments Endpoints

Uses PayrollService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import (
    StructureAssignmentFilters,
    StructureAssignmentCreateData,
    StructureAssignmentUpdateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import SalaryStructureAssignmentNotFoundError, ValidationError as HRValidationError

router = APIRouter()

# =============================================================================
# SALARY STRUCTURE ASSIGNMENT
# =============================================================================


class SalaryStructureAssignmentCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    salary_structure: str
    salary_structure_id: Optional[int] = None
    from_date: date
    base: Optional[Decimal] = Decimal("0")
    variable: Optional[Decimal] = Decimal("0")
    income_tax_slab: Optional[str] = None
    company: Optional[str] = None
    docstatus: Optional[int] = 0


class SalaryStructureAssignmentUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    salary_structure: Optional[str] = None
    salary_structure_id: Optional[int] = None
    from_date: Optional[date] = None
    base: Optional[Decimal] = None
    variable: Optional[Decimal] = None
    income_tax_slab: Optional[str] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None


def _serialize_assignment(a, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a SalaryStructureAssignment model to dict."""
    result = {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "salary_structure": a.salary_structure,
        "salary_structure_id": a.salary_structure_id,
        "from_date": a.from_date.isoformat() if a.from_date else None,
        "base": float(a.base) if a.base else 0,
        "company": a.company,
    }
    if include_timestamps:
        result["variable"] = float(a.variable) if a.variable else 0
        result["income_tax_slab"] = a.income_tax_slab
        result["docstatus"] = a.docstatus
        result["created_at"] = a.created_at.isoformat() if a.created_at else None
        result["updated_at"] = a.updated_at.isoformat() if a.updated_at else None
    return result


@router.get("/salary-structure-assignments", dependencies=[Depends(Require("hr:read"))])
def list_salary_structure_assignments(
    employee_id: Optional[int] = None,
    salary_structure_id: Optional[int] = None,
    from_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List salary structure assignments with filtering."""
    service = PayrollService(db)

    filters = StructureAssignmentFilters(
        employee_id=employee_id,
        salary_structure_id=salary_structure_id,
        from_date=from_date,
        company=company,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_structure_assignments(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_assignment(a) for a in result.items],
    }


@router.get("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_structure_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary structure assignment detail."""
    service = PayrollService(db)
    try:
        a = service.get_structure_assignment(assignment_id)
    except SalaryStructureAssignmentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")

    return _serialize_assignment(a, include_timestamps=True)


@router.post("/salary-structure-assignments", dependencies=[Depends(Require("hr:write"))])
def create_salary_structure_assignment(
    payload: SalaryStructureAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new salary structure assignment."""
    service = PayrollService(db, current_user)

    create_data = StructureAssignmentCreateData(
        employee=payload.employee,
        employee_id=payload.employee_id or 0,
        employee_name=payload.employee_name,
        salary_structure=payload.salary_structure,
        salary_structure_id=payload.salary_structure_id or 0,
        from_date=payload.from_date,
        base=payload.base or Decimal("0"),
        variable=payload.variable or Decimal("0"),
        income_tax_slab=payload.income_tax_slab,
        company=payload.company,
    )

    try:
        assignment = service.create_structure_assignment(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_structure_assignment(assignment.id, db)


@router.patch("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_structure_assignment(
    assignment_id: int,
    payload: SalaryStructureAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a salary structure assignment."""
    service = PayrollService(db, current_user)

    update_data = StructureAssignmentUpdateData(
        from_date=payload.from_date,
        base=payload.base,
        variable=payload.variable,
        income_tax_slab=payload.income_tax_slab,
    )

    try:
        service.update_structure_assignment(assignment_id, update_data)
        db.commit()
    except SalaryStructureAssignmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_structure_assignment(assignment_id, db)


@router.delete("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_structure_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a salary structure assignment."""
    service = PayrollService(db, current_user)

    try:
        service.delete_structure_assignment(assignment_id)
        db.commit()
    except SalaryStructureAssignmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")

    return {"message": "Salary structure assignment deleted", "id": assignment_id}
