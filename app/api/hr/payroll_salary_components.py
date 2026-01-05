"""
Salary Components Endpoints

Uses PayrollService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_payroll import SalaryComponentType
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import SalaryComponentCreateData, SalaryComponentUpdateData
from app.services.types import PaginationParams
from app.services.hr.errors import SalaryComponentNotFoundError, ValidationError as HRValidationError

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


def _serialize_component(c, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a SalaryComponent model to dict."""
    result = {
        "id": c.id,
        "erpnext_id": c.erpnext_id,
        "salary_component_name": c.salary_component_name,
        "salary_component_abbr": c.salary_component_abbr,
        "type": c.type.value if c.type else None,
        "is_tax_applicable": c.is_tax_applicable,
        "disabled": c.disabled,
    }
    if include_timestamps:
        result["description"] = c.description
        result["is_payable"] = c.is_payable
        result["is_flexible_benefit"] = c.is_flexible_benefit
        result["depends_on_payment_days"] = c.depends_on_payment_days
        result["variable_based_on_taxable_salary"] = c.variable_based_on_taxable_salary
        result["exempted_from_income_tax"] = c.exempted_from_income_tax
        result["statistical_component"] = c.statistical_component
        result["do_not_include_in_total"] = c.do_not_include_in_total
        result["default_account"] = c.default_account
        result["created_at"] = c.created_at.isoformat() if c.created_at else None
        result["updated_at"] = c.updated_at.isoformat() if c.updated_at else None
    return result


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
    service = PayrollService(db)

    # Parse type enum
    type_enum = None
    if type:
        try:
            type_enum = SalaryComponentType(type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type: {type}")

    # Determine include_disabled based on disabled filter
    include_disabled = True if disabled is not None else False

    result = service.list_salary_components(
        type=type_enum,
        include_disabled=include_disabled,
        pagination=PaginationParams(offset=offset, limit=limit),
    )

    # Apply search and disabled filters post-query (service doesn't support them directly)
    items = result.items
    if search:
        search_lower = search.lower()
        items = [c for c in items if c.salary_component_name and search_lower in c.salary_component_name.lower()]
    if disabled is not None:
        items = [c for c in items if c.disabled == disabled]

    return {
        "total": len(items) if search or disabled is not None else result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_component(c) for c in items],
    }


@router.get("/salary-components/{component_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_component(
    component_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary component detail."""
    service = PayrollService(db)
    try:
        c = service.get_salary_component(component_id)
    except SalaryComponentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary component not found")

    return _serialize_component(c, include_timestamps=True)


@router.post("/salary-components", dependencies=[Depends(Require("hr:write"))])
def create_salary_component(
    payload: SalaryComponentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new salary component."""
    service = PayrollService(db, current_user)

    create_data = SalaryComponentCreateData(
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

    try:
        component = service.create_salary_component(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_component(component.id, db)


@router.patch("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_component(
    component_id: int,
    payload: SalaryComponentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a salary component."""
    service = PayrollService(db, current_user)

    update_data = SalaryComponentUpdateData(
        salary_component_name=payload.salary_component_name,
        salary_component_abbr=payload.salary_component_abbr,
        type=payload.type,
        description=payload.description,
        is_tax_applicable=payload.is_tax_applicable,
        is_payable=payload.is_payable,
        is_flexible_benefit=payload.is_flexible_benefit,
        depends_on_payment_days=payload.depends_on_payment_days,
        variable_based_on_taxable_salary=payload.variable_based_on_taxable_salary,
        exempted_from_income_tax=payload.exempted_from_income_tax,
        statistical_component=payload.statistical_component,
        do_not_include_in_total=payload.do_not_include_in_total,
        disabled=payload.disabled,
        default_account=payload.default_account,
    )

    try:
        service.update_salary_component(component_id, update_data)
        db.commit()
    except SalaryComponentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary component not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_component(component_id, db)


@router.delete("/salary-components/{component_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_component(
    component_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a salary component."""
    service = PayrollService(db, current_user)

    try:
        service.delete_salary_component(component_id)
        db.commit()
    except SalaryComponentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary component not found")

    return {"message": "Salary component deleted", "id": component_id}
