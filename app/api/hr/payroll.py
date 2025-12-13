"""
Payroll Management Router

Endpoints for SalaryComponent, SalaryStructure, SalaryStructureAssignment, PayrollEntry, SalarySlip.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_payroll import (
    SalaryComponent,
    SalaryComponentType,
    SalaryStructure,
    SalaryStructureEarning,
    SalaryStructureDeduction,
    SalaryStructureAssignment,
    PayrollEntry,
    SalarySlip,
    SalarySlipStatus,
    SalarySlipEarning,
    SalarySlipDeduction,
)
from app.models.employee import Employee
from .helpers import decimal_or_default, csv_response, validate_date_order, status_counts, now

router = APIRouter()


# =============================================================================
# SALARY COMPONENT
# =============================================================================

class SalaryComponentCreate(BaseModel):
    salary_component_name: str
    salary_component_abbr: Optional[str] = None
    type: Optional[SalaryComponentType] = SalaryComponentType.EARNING
    description: Optional[str] = None
    is_tax_applicable: Optional[bool] = False
    is_payable: Optional[bool] = True
    is_flexible_benefit: Optional[bool] = False
    depends_on_payment_days: Optional[bool] = True
    variable_based_on_taxable_salary: Optional[bool] = False
    exempted_from_income_tax: Optional[bool] = False
    statistical_component: Optional[bool] = False
    do_not_include_in_total: Optional[bool] = False
    disabled: Optional[bool] = False
    default_account: Optional[str] = None


class SalaryComponentUpdate(BaseModel):
    salary_component_name: Optional[str] = None
    salary_component_abbr: Optional[str] = None
    type: Optional[SalaryComponentType] = None
    description: Optional[str] = None
    is_tax_applicable: Optional[bool] = None
    is_payable: Optional[bool] = None
    is_flexible_benefit: Optional[bool] = None
    depends_on_payment_days: Optional[bool] = None
    variable_based_on_taxable_salary: Optional[bool] = None
    exempted_from_income_tax: Optional[bool] = None
    statistical_component: Optional[bool] = None
    do_not_include_in_total: Optional[bool] = None
    disabled: Optional[bool] = None
    default_account: Optional[str] = None


@router.get("/salary-components", dependencies=[Depends(Require("hr:read"))])
async def list_salary_components(
    type: Optional[str] = None,
    search: Optional[str] = None,
    disabled: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List salary components with filtering."""
    query = db.query(SalaryComponent)

    if type:
        try:
            type_enum = SalaryComponentType(type)
            query = query.filter(SalaryComponent.type == type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type: {type}")
    if search:
        query = query.filter(SalaryComponent.salary_component_name.ilike(f"%{search}%"))
    if disabled is not None:
        query = query.filter(SalaryComponent.disabled == disabled)

    total = query.count()
    components = query.order_by(SalaryComponent.salary_component_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": c.id,
                "erpnext_id": c.erpnext_id,
                "salary_component_name": c.salary_component_name,
                "salary_component_abbr": c.salary_component_abbr,
                "type": c.type.value if c.type else None,
                "is_tax_applicable": c.is_tax_applicable,
                "disabled": c.disabled,
            }
            for c in components
        ],
    }


@router.get("/salary-components/{component_id}", dependencies=[Depends(Require("hr:read"))])
async def get_salary_component(
    component_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary component detail."""
    c = db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Salary component not found")

    return {
        "id": c.id,
        "erpnext_id": c.erpnext_id,
        "salary_component_name": c.salary_component_name,
        "salary_component_abbr": c.salary_component_abbr,
        "type": c.type.value if c.type else None,
        "description": c.description,
        "is_tax_applicable": c.is_tax_applicable,
        "is_payable": c.is_payable,
        "is_flexible_benefit": c.is_flexible_benefit,
        "depends_on_payment_days": c.depends_on_payment_days,
        "variable_based_on_taxable_salary": c.variable_based_on_taxable_salary,
        "exempted_from_income_tax": c.exempted_from_income_tax,
        "statistical_component": c.statistical_component,
        "do_not_include_in_total": c.do_not_include_in_total,
        "disabled": c.disabled,
        "default_account": c.default_account,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.post("/salary-components", dependencies=[Depends(Require("hr:write"))])
async def create_salary_component(
    payload: SalaryComponentCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new salary component."""
    component = SalaryComponent(
        salary_component_name=payload.salary_component_name,
        salary_component_abbr=payload.salary_component_abbr,
        type=payload.type or SalaryComponentType.EARNING,
        description=payload.description,
        is_tax_applicable=payload.is_tax_applicable or False,
        is_payable=payload.is_payable if payload.is_payable is not None else True,
        is_flexible_benefit=payload.is_flexible_benefit or False,
        depends_on_payment_days=payload.depends_on_payment_days if payload.depends_on_payment_days is not None else True,
        variable_based_on_taxable_salary=payload.variable_based_on_taxable_salary or False,
        exempted_from_income_tax=payload.exempted_from_income_tax or False,
        statistical_component=payload.statistical_component or False,
        do_not_include_in_total=payload.do_not_include_in_total or False,
        disabled=payload.disabled or False,
        default_account=payload.default_account,
    )
    db.add(component)
    db.commit()
    return await get_salary_component(component.id, db)


@router.patch("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
async def update_salary_component(
    component_id: int,
    payload: SalaryComponentUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a salary component."""
    component = db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Salary component not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(component, field, value)

    db.commit()
    return await get_salary_component(component.id, db)


@router.delete("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_salary_component(
    component_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a salary component."""
    component = db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Salary component not found")

    db.delete(component)
    db.commit()
    return {"message": "Salary component deleted", "id": component_id}


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
async def list_salary_structures(
    is_active: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
async def get_salary_structure(
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
async def create_salary_structure(
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
    return await get_salary_structure(structure.id, db)


@router.patch("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
async def update_salary_structure(
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
    return await get_salary_structure(structure.id, db)


@router.delete("/salary-structures/{structure_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_salary_structure(
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
async def list_salary_structure_assignments(
    employee_id: Optional[int] = None,
    salary_structure_id: Optional[int] = None,
    from_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
async def get_salary_structure_assignment(
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
async def create_salary_structure_assignment(
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
    return await get_salary_structure_assignment(assignment.id, db)


@router.patch("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def update_salary_structure_assignment(
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
    return await get_salary_structure_assignment(assignment.id, db)


@router.delete("/salary-structure-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_salary_structure_assignment(
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


# =============================================================================
# PAYROLL ENTRY
# =============================================================================

class PayrollEntryCreate(BaseModel):
    posting_date: date
    payroll_frequency: Optional[str] = None
    start_date: date
    end_date: date
    company: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: Optional[str] = "USD"
    exchange_rate: Optional[Decimal] = Decimal("1")
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None
    docstatus: Optional[int] = 0


class PayrollEntryUpdate(BaseModel):
    posting_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None
    salary_slips_created: Optional[bool] = None
    salary_slips_submitted: Optional[bool] = None
    docstatus: Optional[int] = None


@router.get("/payroll-entries", dependencies=[Depends(Require("hr:read"))])
async def list_payroll_entries(
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payroll entries with filtering."""
    query = db.query(PayrollEntry)

    if company:
        query = query.filter(PayrollEntry.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(PayrollEntry.start_date >= from_date)
    if to_date:
        query = query.filter(PayrollEntry.end_date <= to_date)

    total = query.count()
    entries = query.order_by(PayrollEntry.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "payroll_frequency": e.payroll_frequency,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "company": e.company,
                "salary_slips_created": e.salary_slips_created,
                "salary_slips_submitted": e.salary_slips_submitted,
            }
            for e in entries
        ],
    }


@router.get("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:read"))])
async def get_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll entry detail."""
    e = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    return {
        "id": e.id,
        "erpnext_id": e.erpnext_id,
        "posting_date": e.posting_date.isoformat() if e.posting_date else None,
        "payroll_frequency": e.payroll_frequency,
        "start_date": e.start_date.isoformat() if e.start_date else None,
        "end_date": e.end_date.isoformat() if e.end_date else None,
        "company": e.company,
        "department": e.department,
        "branch": e.branch,
        "designation": e.designation,
        "currency": e.currency,
        "exchange_rate": float(e.exchange_rate) if e.exchange_rate else 1,
        "payment_account": e.payment_account,
        "bank_account": e.bank_account,
        "salary_slips_created": e.salary_slips_created,
        "salary_slips_submitted": e.salary_slips_submitted,
        "docstatus": e.docstatus,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.post("/payroll-entries", dependencies=[Depends(Require("hr:write"))])
async def create_payroll_entry(
    payload: PayrollEntryCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new payroll entry."""
    validate_date_order(payload.start_date, payload.end_date)

    entry = PayrollEntry(
        posting_date=payload.posting_date,
        payroll_frequency=payload.payroll_frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
        department=payload.department,
        branch=payload.branch,
        designation=payload.designation,
        currency=payload.currency or "USD",
        exchange_rate=decimal_or_default(payload.exchange_rate, Decimal("1")),
        payment_account=payload.payment_account,
        bank_account=payload.bank_account,
        docstatus=payload.docstatus or 0,
    )
    db.add(entry)
    db.commit()
    return await get_payroll_entry(entry.id, db)


@router.patch("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
async def update_payroll_entry(
    entry_id: int,
    payload: PayrollEntryUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payroll entry."""
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "exchange_rate":
                setattr(entry, field, decimal_or_default(value, Decimal("1")))
            else:
                setattr(entry, field, value)

    validate_date_order(entry.start_date, entry.end_date)

    db.commit()
    return await get_payroll_entry(entry.id, db)


@router.delete("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a payroll entry."""
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    db.delete(entry)
    db.commit()
    return {"message": "Payroll entry deleted", "id": entry_id}


# =============================================================================
# SALARY SLIP
# =============================================================================

class SalarySlipComponentPayload(BaseModel):
    salary_component: str
    abbr: Optional[str] = None
    amount: Optional[Decimal] = Decimal("0")
    default_amount: Optional[Decimal] = Decimal("0")
    additional_amount: Optional[Decimal] = Decimal("0")
    year_to_date: Optional[Decimal] = Decimal("0")
    statistical_component: Optional[bool] = False
    do_not_include_in_total: Optional[bool] = False
    idx: Optional[int] = 0


class SalarySlipCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    salary_structure: Optional[str] = None
    posting_date: date
    start_date: date
    end_date: date
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = "USD"
    total_working_days: Optional[Decimal] = Decimal("0")
    absent_days: Optional[Decimal] = Decimal("0")
    payment_days: Optional[Decimal] = Decimal("0")
    leave_without_pay: Optional[Decimal] = Decimal("0")
    gross_pay: Optional[Decimal] = Decimal("0")
    total_deduction: Optional[Decimal] = Decimal("0")
    net_pay: Optional[Decimal] = Decimal("0")
    rounded_total: Optional[Decimal] = Decimal("0")
    status: Optional[SalarySlipStatus] = SalarySlipStatus.DRAFT
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    payroll_entry: Optional[str] = None
    docstatus: Optional[int] = 0
    earnings: Optional[List[SalarySlipComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalarySlipComponentPayload]] = Field(default=None)


class SalarySlipUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    salary_structure: Optional[str] = None
    posting_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    total_working_days: Optional[Decimal] = None
    absent_days: Optional[Decimal] = None
    payment_days: Optional[Decimal] = None
    leave_without_pay: Optional[Decimal] = None
    gross_pay: Optional[Decimal] = None
    total_deduction: Optional[Decimal] = None
    net_pay: Optional[Decimal] = None
    rounded_total: Optional[Decimal] = None
    status: Optional[SalarySlipStatus] = None
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    payroll_entry: Optional[str] = None
    docstatus: Optional[int] = None
    earnings: Optional[List[SalarySlipComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalarySlipComponentPayload]] = Field(default=None)


class SalarySlipBulkAction(BaseModel):
    slip_ids: List[int]


def _require_slip_status(slip: SalarySlip, allowed: List[SalarySlipStatus]):
    if slip.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {slip.status.value if slip.status else None}",
        )


def _load_slip(db: Session, slip_id: int) -> SalarySlip:
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    return slip


@router.get("/salary-slips", dependencies=[Depends(Require("hr:read"))])
async def list_salary_slips(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    payroll_entry: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List salary slips with filtering."""
    query = db.query(SalarySlip)

    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    if status:
        try:
            status_enum = SalarySlipStatus(status)
            query = query.filter(SalarySlip.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(SalarySlip.start_date >= from_date)
    if to_date:
        query = query.filter(SalarySlip.end_date <= to_date)
    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))
    if payroll_entry:
        query = query.filter(SalarySlip.payroll_entry == payroll_entry)

    total = query.count()
    slips = query.order_by(SalarySlip.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "employee": s.employee,
                "employee_id": s.employee_id,
                "employee_name": s.employee_name,
                "posting_date": s.posting_date.isoformat() if s.posting_date else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "gross_pay": float(s.gross_pay) if s.gross_pay else 0,
                "total_deduction": float(s.total_deduction) if s.total_deduction else 0,
                "net_pay": float(s.net_pay) if s.net_pay else 0,
                "status": s.status.value if s.status else None,
                "company": s.company,
            }
            for s in slips
        ],
    }


@router.get("/salary-slips/export", dependencies=[Depends(Require("hr:read"))])
async def export_salary_slips(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export salary slips to CSV."""
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    if status:
        try:
            status_enum = SalarySlipStatus(status)
            query = query.filter(SalarySlip.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(SalarySlip.start_date >= from_date)
    if to_date:
        query = query.filter(SalarySlip.end_date <= to_date)
    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))

    rows = [["id", "employee", "employee_name", "posting_date", "start_date", "end_date", "gross_pay", "total_deduction", "net_pay", "status", "company"]]
    for s in query.order_by(SalarySlip.posting_date.desc()).all():
        rows.append([
            s.id,
            s.employee,
            s.employee_name or "",
            s.posting_date.isoformat() if s.posting_date else "",
            s.start_date.isoformat() if s.start_date else "",
            s.end_date.isoformat() if s.end_date else "",
            float(s.gross_pay or 0),
            float(s.total_deduction or 0),
            float(s.net_pay or 0),
            s.status.value if s.status else "",
            s.company or "",
        ])
    return csv_response(rows, "salary_slips.csv")


@router.get("/salary-slips/summary", dependencies=[Depends(Require("hr:read"))])
async def salary_slips_summary(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary slips summary statistics."""
    query = db.query(
        SalarySlip.status,
        func.count(SalarySlip.id),
        func.sum(SalarySlip.gross_pay),
        func.sum(SalarySlip.net_pay),
    )

    if from_date:
        query = query.filter(SalarySlip.start_date >= from_date)
    if to_date:
        query = query.filter(SalarySlip.end_date <= to_date)
    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))

    results = query.group_by(SalarySlip.status).all()

    summary = {}
    total_gross = Decimal("0")
    total_net = Decimal("0")
    total_count = 0

    for row in results:
        status_val = row[0].value if row[0] else None
        count = int(row[1] or 0)
        gross = row[2] or Decimal("0")
        net = row[3] or Decimal("0")

        summary[status_val] = {
            "count": count,
            "gross_pay": float(gross),
            "net_pay": float(net),
        }
        total_count += count
        total_gross += gross
        total_net += net

    return {
        "by_status": summary,
        "totals": {
            "count": total_count,
            "gross_pay": float(total_gross),
            "net_pay": float(total_net),
        },
    }


@router.get("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:read"))])
async def get_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary slip detail with earnings and deductions."""
    s = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    earnings = [
        {
            "id": e.id,
            "salary_component": e.salary_component,
            "abbr": e.abbr,
            "amount": float(e.amount) if e.amount else 0,
            "default_amount": float(e.default_amount) if e.default_amount else 0,
            "additional_amount": float(e.additional_amount) if e.additional_amount else 0,
            "year_to_date": float(e.year_to_date) if e.year_to_date else 0,
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
            "default_amount": float(d.default_amount) if d.default_amount else 0,
            "additional_amount": float(d.additional_amount) if d.additional_amount else 0,
            "year_to_date": float(d.year_to_date) if d.year_to_date else 0,
            "statistical_component": d.statistical_component,
            "do_not_include_in_total": d.do_not_include_in_total,
            "idx": d.idx,
        }
        for d in sorted(s.deductions, key=lambda x: x.idx)
    ]

    return {
        "id": s.id,
        "erpnext_id": s.erpnext_id,
        "employee": s.employee,
        "employee_id": s.employee_id,
        "employee_name": s.employee_name,
        "department": s.department,
        "designation": s.designation,
        "branch": s.branch,
        "salary_structure": s.salary_structure,
        "posting_date": s.posting_date.isoformat() if s.posting_date else None,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "payroll_frequency": s.payroll_frequency,
        "company": s.company,
        "currency": s.currency,
        "total_working_days": float(s.total_working_days) if s.total_working_days else 0,
        "absent_days": float(s.absent_days) if s.absent_days else 0,
        "payment_days": float(s.payment_days) if s.payment_days else 0,
        "leave_without_pay": float(s.leave_without_pay) if s.leave_without_pay else 0,
        "gross_pay": float(s.gross_pay) if s.gross_pay else 0,
        "total_deduction": float(s.total_deduction) if s.total_deduction else 0,
        "net_pay": float(s.net_pay) if s.net_pay else 0,
        "rounded_total": float(s.rounded_total) if s.rounded_total else 0,
        "status": s.status.value if s.status else None,
        "bank_name": s.bank_name,
        "bank_account_no": s.bank_account_no,
        "payroll_entry": s.payroll_entry,
        "docstatus": s.docstatus,
        "earnings": earnings,
        "deductions": deductions,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post("/salary-slips", dependencies=[Depends(Require("hr:write"))])
async def create_salary_slip(
    payload: SalarySlipCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new salary slip with earnings and deductions."""
    validate_date_order(payload.start_date, payload.end_date)

    decimal_fields = [
        "total_working_days", "absent_days", "payment_days", "leave_without_pay",
        "gross_pay", "total_deduction", "net_pay", "rounded_total"
    ]

    slip_data = {
        "employee": payload.employee,
        "employee_id": payload.employee_id,
        "employee_name": payload.employee_name,
        "department": payload.department,
        "designation": payload.designation,
        "branch": payload.branch,
        "salary_structure": payload.salary_structure,
        "posting_date": payload.posting_date,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "payroll_frequency": payload.payroll_frequency,
        "company": payload.company,
        "currency": payload.currency or "USD",
        "status": payload.status or SalarySlipStatus.DRAFT,
        "bank_name": payload.bank_name,
        "bank_account_no": payload.bank_account_no,
        "payroll_entry": payload.payroll_entry,
        "docstatus": payload.docstatus or 0,
    }

    for field in decimal_fields:
        slip_data[field] = decimal_or_default(getattr(payload, field))

    slip = SalarySlip(**slip_data)
    db.add(slip)
    db.flush()

    if payload.earnings:
        for idx, e in enumerate(payload.earnings):
            earning = SalarySlipEarning(
                salary_slip_id=slip.id,
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=decimal_or_default(e.amount),
                default_amount=decimal_or_default(e.default_amount),
                additional_amount=decimal_or_default(e.additional_amount),
                year_to_date=decimal_or_default(e.year_to_date),
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            )
            db.add(earning)

    if payload.deductions:
        for idx, d in enumerate(payload.deductions):
            deduction = SalarySlipDeduction(
                salary_slip_id=slip.id,
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=decimal_or_default(d.amount),
                default_amount=decimal_or_default(d.default_amount),
                additional_amount=decimal_or_default(d.additional_amount),
                year_to_date=decimal_or_default(d.year_to_date),
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(deduction)

    db.commit()
    return await get_salary_slip(slip.id, db)


@router.patch("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:write"))])
async def update_salary_slip(
    slip_id: int,
    payload: SalarySlipUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a salary slip and optionally replace earnings/deductions."""
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    update_data = payload.model_dump(exclude_unset=True)
    earnings_data = update_data.pop("earnings", None)
    deductions_data = update_data.pop("deductions", None)

    decimal_fields = [
        "total_working_days", "absent_days", "payment_days", "leave_without_pay",
        "gross_pay", "total_deduction", "net_pay", "rounded_total"
    ]

    for field, value in update_data.items():
        if value is not None:
            if field in decimal_fields:
                setattr(slip, field, decimal_or_default(value))
            else:
                setattr(slip, field, value)

    validate_date_order(slip.start_date, slip.end_date)

    if earnings_data is not None:
        db.query(SalarySlipEarning).filter(
            SalarySlipEarning.salary_slip_id == slip.id
        ).delete(synchronize_session=False)
        for idx, e in enumerate(earnings_data):
            earning = SalarySlipEarning(
                salary_slip_id=slip.id,
                salary_component=e.get("salary_component"),
                abbr=e.get("abbr"),
                amount=decimal_or_default(e.get("amount")),
                default_amount=decimal_or_default(e.get("default_amount")),
                additional_amount=decimal_or_default(e.get("additional_amount")),
                year_to_date=decimal_or_default(e.get("year_to_date")),
                statistical_component=e.get("statistical_component", False),
                do_not_include_in_total=e.get("do_not_include_in_total", False),
                idx=e.get("idx") if e.get("idx") is not None else idx,
            )
            db.add(earning)

    if deductions_data is not None:
        db.query(SalarySlipDeduction).filter(
            SalarySlipDeduction.salary_slip_id == slip.id
        ).delete(synchronize_session=False)
        for idx, d in enumerate(deductions_data):
            deduction = SalarySlipDeduction(
                salary_slip_id=slip.id,
                salary_component=d.get("salary_component"),
                abbr=d.get("abbr"),
                amount=decimal_or_default(d.get("amount")),
                default_amount=decimal_or_default(d.get("default_amount")),
                additional_amount=decimal_or_default(d.get("additional_amount")),
                year_to_date=decimal_or_default(d.get("year_to_date")),
                statistical_component=d.get("statistical_component", False),
                do_not_include_in_total=d.get("do_not_include_in_total", False),
                idx=d.get("idx") if d.get("idx") is not None else idx,
            )
            db.add(deduction)

    db.commit()
    return await get_salary_slip(slip.id, db)


@router.delete("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a salary slip."""
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    db.delete(slip)
    db.commit()
    return {"message": "Salary slip deleted", "id": slip_id}


@router.post("/salary-slips/{slip_id}/submit", dependencies=[Depends(Require("hr:write"))])
async def submit_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a salary slip."""
    slip = _load_slip(db, slip_id)
    _require_slip_status(slip, [SalarySlipStatus.DRAFT])
    slip.status = SalarySlipStatus.SUBMITTED
    slip.docstatus = 1
    db.commit()
    return await get_salary_slip(slip_id, db)


@router.post("/salary-slips/{slip_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel a salary slip."""
    slip = _load_slip(db, slip_id)
    _require_slip_status(slip, [SalarySlipStatus.SUBMITTED])
    slip.status = SalarySlipStatus.CANCELLED
    slip.docstatus = 2
    db.commit()
    return await get_salary_slip(slip_id, db)


@router.post("/salary-slips/bulk/submit", dependencies=[Depends(Require("hr:write"))])
async def bulk_submit_salary_slips(
    payload: SalarySlipBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk submit salary slips."""
    updated = 0
    for slip_id in payload.slip_ids:
        slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
        if slip and slip.status == SalarySlipStatus.DRAFT:
            slip.status = SalarySlipStatus.SUBMITTED
            slip.docstatus = 1
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.slip_ids)}


@router.post("/salary-slips/bulk/cancel", dependencies=[Depends(Require("hr:write"))])
async def bulk_cancel_salary_slips(
    payload: SalarySlipBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk cancel salary slips."""
    updated = 0
    for slip_id in payload.slip_ids:
        slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
        if slip and slip.status == SalarySlipStatus.SUBMITTED:
            slip.status = SalarySlipStatus.CANCELLED
            slip.docstatus = 2
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.slip_ids)}


# =============================================================================
# PAYROLL GENERATION
# =============================================================================

@router.post("/payroll-entries/{entry_id}/generate-slips", dependencies=[Depends(Require("hr:write"))])
async def generate_payroll_slips(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Generate draft salary slips for a payroll entry.

    Finds employees with active salary structure assignments matching the
    payroll entry's filters (company, department, designation) and
    creates draft salary slips for each.

    An assignment is considered active for the period if:
    - assignment.from_date <= entry.end_date (assignment started before period ends)
    - There is no newer assignment for the same employee that starts before entry.end_date
    """
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    if entry.salary_slips_created:
        raise HTTPException(status_code=400, detail="Salary slips already created for this entry")

    # Build query with proper date filtering
    query = db.query(SalaryStructureAssignment).filter(
        SalaryStructureAssignment.from_date <= entry.end_date,
    )

    # Apply company filter from payroll entry
    if entry.company:
        query = query.filter(SalaryStructureAssignment.company == entry.company)

    # Apply department/designation filters by joining with Employee
    if entry.department or entry.designation:
        query = query.join(
            Employee, SalaryStructureAssignment.employee_id == Employee.id
        )
        if entry.department:
            query = query.filter(Employee.department == entry.department)
        if entry.designation:
            query = query.filter(Employee.designation == entry.designation)

    assignments = query.all()

    # Filter to only the most recent assignment per employee
    # (in case of multiple assignments, take the one with latest from_date before period)
    employee_assignments: Dict[int, SalaryStructureAssignment] = {}
    for assignment in assignments:
        if assignment.employee_id is None:
            continue
        existing = employee_assignments.get(assignment.employee_id)
        if existing is None or (assignment.from_date and existing.from_date and assignment.from_date > existing.from_date):
            employee_assignments[assignment.employee_id] = assignment

    assignments = list(employee_assignments.values())
    created = []
    skipped = []
    audit = AuditLogger(db)

    for assignment in assignments:
        # Check if slip already exists for this employee and period
        existing = db.query(SalarySlip).filter(
            SalarySlip.employee_id == assignment.employee_id,
            SalarySlip.start_date == entry.start_date,
            SalarySlip.end_date == entry.end_date,
        ).first()

        if existing:
            skipped.append({
                "employee_id": assignment.employee_id,
                "employee": assignment.employee,
                "reason": "Salary slip already exists",
            })
            continue

        # Get salary structure with earnings and deductions
        structure = db.query(SalaryStructure).filter(
            SalaryStructure.id == assignment.salary_structure_id
        ).first()

        if not structure:
            skipped.append({
                "employee_id": assignment.employee_id,
                "employee": assignment.employee,
                "reason": "Salary structure not found",
            })
            continue

        # Calculate totals from structure
        gross_pay = Decimal("0")
        total_deduction = Decimal("0")

        for earning in structure.earnings:
            if not earning.statistical_component and not earning.do_not_include_in_total:
                gross_pay += earning.amount or Decimal("0")

        for deduction in structure.deductions:
            if not deduction.statistical_component and not deduction.do_not_include_in_total:
                total_deduction += deduction.amount or Decimal("0")

        net_pay = gross_pay - total_deduction

        # Create salary slip
        slip = SalarySlip(
            employee=assignment.employee,
            employee_id=assignment.employee_id,
            employee_name=assignment.employee_name,
            salary_structure=structure.salary_structure_name,
            posting_date=entry.posting_date,
            start_date=entry.start_date,
            end_date=entry.end_date,
            payroll_frequency=structure.payroll_frequency,
            company=entry.company or structure.company,
            currency=entry.currency or structure.currency,
            gross_pay=gross_pay,
            total_deduction=total_deduction,
            net_pay=net_pay,
            rounded_total=net_pay,
            status=SalarySlipStatus.DRAFT,
            payroll_entry=f"PAYROLL-{entry.id}",
            created_by_id=current_user.id if current_user else None,
        )
        db.add(slip)
        db.flush()

        # Copy earnings from structure
        for idx, earning in enumerate(structure.earnings):
            slip_earning = SalarySlipEarning(
                salary_slip_id=slip.id,
                salary_component=earning.salary_component,
                abbr=earning.abbr,
                amount=earning.amount or Decimal("0"),
                default_amount=earning.amount or Decimal("0"),
                statistical_component=earning.statistical_component,
                do_not_include_in_total=earning.do_not_include_in_total,
                idx=idx,
            )
            db.add(slip_earning)

        # Copy deductions from structure
        for idx, deduction in enumerate(structure.deductions):
            slip_deduction = SalarySlipDeduction(
                salary_slip_id=slip.id,
                salary_component=deduction.salary_component,
                abbr=deduction.abbr,
                amount=deduction.amount or Decimal("0"),
                default_amount=deduction.amount or Decimal("0"),
                statistical_component=deduction.statistical_component,
                do_not_include_in_total=deduction.do_not_include_in_total,
                idx=idx,
            )
            db.add(slip_deduction)

        created.append({
            "id": slip.id,
            "employee": assignment.employee,
            "employee_id": assignment.employee_id,
            "gross_pay": float(gross_pay),
            "net_pay": float(net_pay),
        })

    # Mark entry as having slips created
    entry.salary_slips_created = True
    entry.updated_by_id = current_user.id if current_user else None

    # Log audit
    audit.log_create(
        doctype="payroll_entry",
        document_id=entry.id,
        new_values={"slip_count": len(created)},
        user_id=current_user.id if current_user else None,
        document_name=f"Payroll {entry.start_date} to {entry.end_date}",
        remarks=f"Generated {len(created)} salary slips",
    )

    db.commit()
    return {
        "created": len(created),
        "skipped": len(skipped),
        "created_details": created,
        "skipped_details": skipped,
    }


@router.post("/payroll-entries/{entry_id}/regenerate-slips", dependencies=[Depends(Require("hr:write"))])
async def regenerate_payroll_slips(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Delete existing draft slips and regenerate for a payroll entry.
    Only draft slips will be deleted; submitted/paid slips are preserved.
    """
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    # Delete only draft slips for this entry
    deleted_count = db.query(SalarySlip).filter(
        SalarySlip.payroll_entry == f"PAYROLL-{entry.id}",
        SalarySlip.status == SalarySlipStatus.DRAFT,
    ).delete(synchronize_session=False)

    # Reset the flag to allow regeneration
    entry.salary_slips_created = False

    db.commit()

    # Now generate fresh slips
    result = await generate_payroll_slips(entry_id, db, current_user)
    result["deleted_drafts"] = deleted_count
    return result


# =============================================================================
# PAYMENT AND VOID
# =============================================================================

class MarkPaidPayload(BaseModel):
    payment_reference: Optional[str] = None
    payment_mode: Optional[str] = None


class VoidSlipPayload(BaseModel):
    reason: str


@router.post("/salary-slips/{slip_id}/mark-paid", dependencies=[Depends(Require("hr:write"))])
async def mark_salary_slip_paid(
    slip_id: int,
    payload: MarkPaidPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a submitted salary slip as paid with payment metadata."""
    slip = _load_slip(db, slip_id)
    _require_slip_status(slip, [SalarySlipStatus.SUBMITTED])

    slip.status = SalarySlipStatus.PAID
    slip.paid_at = now()
    slip.paid_by_id = current_user.id if current_user else None
    slip.payment_reference = payload.payment_reference
    slip.payment_mode = payload.payment_mode
    slip.status_changed_by_id = current_user.id if current_user else None
    slip.status_changed_at = now()

    # Log audit
    audit = AuditLogger(db)
    audit.log_update(
        doctype="salary_slip",
        document_id=slip.id,
        old_values={"status": "submitted"},
        new_values={
            "status": "paid",
            "payment_reference": payload.payment_reference,
            "payment_mode": payload.payment_mode,
        },
        user_id=current_user.id if current_user else None,
        document_name=f"{slip.employee} - {slip.start_date}",
        remarks="Marked as paid",
    )

    db.commit()
    return await get_salary_slip(slip_id, db)


@router.post("/salary-slips/{slip_id}/void", dependencies=[Depends(Require("hr:write"))])
async def void_salary_slip(
    slip_id: int,
    payload: VoidSlipPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Void a salary slip with reason. Only submitted slips can be voided."""
    slip = _load_slip(db, slip_id)
    _require_slip_status(slip, [SalarySlipStatus.SUBMITTED])

    old_status = slip.status.value
    slip.status = SalarySlipStatus.VOIDED
    slip.voided_at = now()
    slip.voided_by_id = current_user.id if current_user else None
    slip.void_reason = payload.reason
    slip.status_changed_by_id = current_user.id if current_user else None
    slip.status_changed_at = now()

    # Log audit
    audit = AuditLogger(db)
    audit.log_cancel(
        doctype="salary_slip",
        document_id=slip.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{slip.employee} - {slip.start_date}",
        remarks=f"Voided: {payload.reason}",
    )

    db.commit()
    return await get_salary_slip(slip_id, db)


# =============================================================================
# PAYROLL REGISTER EXPORT
# =============================================================================

@router.get("/salary-slips/register/export", dependencies=[Depends(Require("hr:read"))])
async def export_payroll_register(
    start_date: date,
    end_date: date,
    company: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Any:
    """
    Export payroll register as CSV for a date range.

    Returns a CSV with all salary slip details for the period.
    """
    query = db.query(SalarySlip).filter(
        SalarySlip.start_date >= start_date,
        SalarySlip.end_date <= end_date,
    )

    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))
    if status:
        try:
            status_enum = SalarySlipStatus(status)
            query = query.filter(SalarySlip.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    slips = query.order_by(SalarySlip.employee, SalarySlip.start_date).all()

    # Build CSV rows
    headers = [
        "Employee ID", "Employee", "Employee Name", "Department", "Designation",
        "Period Start", "Period End", "Gross Pay", "Total Deduction", "Net Pay",
        "Status", "Payment Reference", "Paid At", "Company"
    ]
    rows = [headers]

    for slip in slips:
        rows.append([
            slip.employee_id or "",
            slip.employee,
            slip.employee_name or "",
            slip.department or "",
            slip.designation or "",
            slip.start_date.isoformat() if slip.start_date else "",
            slip.end_date.isoformat() if slip.end_date else "",
            float(slip.gross_pay) if slip.gross_pay else 0,
            float(slip.total_deduction) if slip.total_deduction else 0,
            float(slip.net_pay) if slip.net_pay else 0,
            slip.status.value if slip.status else "",
            slip.payment_reference or "",
            slip.paid_at.isoformat() if slip.paid_at else "",
            slip.company or "",
        ])

    # Log export audit
    audit = AuditLogger(db)
    audit.log_export(
        doctype="salary_slip",
        document_id=0,
        user_id=current_user.id if current_user else None,
        document_name=f"Payroll Register {start_date} to {end_date}",
        remarks=f"Exported {len(slips)} salary slips",
    )

    return csv_response(rows, f"payroll_register_{start_date}_{end_date}.csv")
