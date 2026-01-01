"""
Salary Components Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.hr_payroll import SalaryComponent, SalaryComponentType

router = APIRouter()


# =============================================================================
# SCHEMAS
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
def list_salary_components(
    type: Optional[str] = None,
    search: Optional[str] = None,
    disabled: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
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
def get_salary_component(
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
def create_salary_component(
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
    return get_salary_component(component.id, db)


@router.patch("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_component(
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
    return get_salary_component(component.id, db)


@router.delete("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_component(
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


