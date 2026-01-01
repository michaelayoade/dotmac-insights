"""
Salary Assignments Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.hr_payroll import SalaryStructureAssignment
from app.models.employee import Employee
from .helpers import decimal_or_default

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
    query = db.query(SalaryStructureAssignment)

    if employee_id:
        query = query.filter(SalaryStructureAssignment.employee_id == employee_id)
    if salary_structure_id:
        query = query.filter(SalaryStructureAssignment.salary_structure_id == salary_structure_id)
    if from_date:
        query = query.filter(SalaryStructureAssignment.from_date >= from_date)
    if company:
        query = query.filter(SalaryStructureAssignment.company.ilike(f"%{company}%"))

    total = query.count()
    assignments = query.order_by(SalaryStructureAssignment.from_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
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
            for a in assignments
        ],
    }


@router.get("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_structure_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary structure assignment detail."""
    a = db.query(SalaryStructureAssignment).filter(SalaryStructureAssignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")

    return {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "salary_structure": a.salary_structure,
        "salary_structure_id": a.salary_structure_id,
        "from_date": a.from_date.isoformat() if a.from_date else None,
        "base": float(a.base) if a.base else 0,
        "variable": float(a.variable) if a.variable else 0,
        "income_tax_slab": a.income_tax_slab,
        "company": a.company,
        "docstatus": a.docstatus,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/salary-structure-assignments", dependencies=[Depends(Require("hr:write"))])
def create_salary_structure_assignment(
    payload: SalaryStructureAssignmentCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new salary structure assignment."""
    assignment = SalaryStructureAssignment(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        salary_structure=payload.salary_structure,
        salary_structure_id=payload.salary_structure_id,
        from_date=payload.from_date,
        base=decimal_or_default(payload.base),
        variable=decimal_or_default(payload.variable),
        income_tax_slab=payload.income_tax_slab,
        company=payload.company,
        docstatus=payload.docstatus or 0,
    )
    db.add(assignment)
    db.commit()
    return get_salary_structure_assignment(assignment.id, db)


@router.patch("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_structure_assignment(
    assignment_id: int,
    payload: SalaryStructureAssignmentUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a salary structure assignment."""
    assignment = db.query(SalaryStructureAssignment).filter(SalaryStructureAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")

    decimal_fields = ["base", "variable"]
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field in decimal_fields:
                setattr(assignment, field, decimal_or_default(value))
            else:
                setattr(assignment, field, value)

    db.commit()
    return get_salary_structure_assignment(assignment.id, db)


@router.delete("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_structure_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a salary structure assignment."""
    assignment = db.query(SalaryStructureAssignment).filter(SalaryStructureAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Salary structure assignment not found")

    db.delete(assignment)
    db.commit()
    return {"message": "Salary structure assignment deleted", "id": assignment_id}


