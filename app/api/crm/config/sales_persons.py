"""
Sales Persons API

Manages sales team members for CRM.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.sales import SalesPerson

router = APIRouter(prefix="/sales-persons", tags=["crm-config-sales-persons"])


# =============================================================================
# SCHEMAS
# =============================================================================

class SalesPersonBase(BaseModel):
    """Base schema for sales persons."""
    sales_person_name: str
    parent_sales_person: Optional[str] = None
    is_group: bool = False
    employee: Optional[str] = None
    commission_rate: Decimal = Decimal("0")
    department: Optional[str] = None


class SalesPersonCreate(SalesPersonBase):
    """Schema for creating a sales person."""
    pass


class SalesPersonUpdate(BaseModel):
    """Schema for updating a sales person."""
    sales_person_name: Optional[str] = None
    parent_sales_person: Optional[str] = None
    is_group: Optional[bool] = None
    enabled: Optional[bool] = None
    employee: Optional[str] = None
    commission_rate: Optional[Decimal] = None
    department: Optional[str] = None


class SalesPersonResponse(BaseModel):
    """Schema for sales person response."""
    id: int
    erpnext_id: Optional[str]
    sales_person_name: str
    parent_sales_person: Optional[str]
    is_group: bool
    enabled: bool
    employee: Optional[str]
    commission_rate: Decimal
    department: Optional[str]
    lft: Optional[int]
    rgt: Optional[int]

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
async def list_sales_persons(
    search: Optional[str] = None,
    enabled: Optional[bool] = True,
    department: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List sales persons with filtering."""
    query = db.query(SalesPerson)

    if search:
        query = query.filter(SalesPerson.sales_person_name.ilike(f"%{search}%"))

    if enabled is not None:
        query = query.filter(SalesPerson.enabled == enabled)

    if department:
        query = query.filter(SalesPerson.department == department)

    total = query.count()
    persons = query.order_by(SalesPerson.sales_person_name).offset(offset).limit(limit).all()

    return {
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "sales_person_name": p.sales_person_name,
                "parent_sales_person": p.parent_sales_person,
                "is_group": p.is_group,
                "enabled": p.enabled,
                "employee": p.employee,
                "commission_rate": float(p.commission_rate or 0),
                "department": p.department,
                "lft": p.lft,
                "rgt": p.rgt,
            }
            for p in persons
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{person_id}", dependencies=[Depends(Require("crm:read"))])
async def get_sales_person(person_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a sales person by ID."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    return {
        "id": person.id,
        "erpnext_id": person.erpnext_id,
        "sales_person_name": person.sales_person_name,
        "parent_sales_person": person.parent_sales_person,
        "is_group": person.is_group,
        "enabled": person.enabled,
        "employee": person.employee,
        "commission_rate": float(person.commission_rate or 0),
        "department": person.department,
        "lft": person.lft,
        "rgt": person.rgt,
    }


@router.post("", dependencies=[Depends(Require("crm:write"))], status_code=201)
async def create_sales_person(
    payload: SalesPersonCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new sales person."""
    # Check for duplicate name
    existing = db.query(SalesPerson).filter(
        SalesPerson.sales_person_name == payload.sales_person_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Sales person name already exists")

    person = SalesPerson(
        sales_person_name=payload.sales_person_name,
        parent_sales_person=payload.parent_sales_person,
        is_group=payload.is_group,
        employee=payload.employee,
        commission_rate=payload.commission_rate,
        department=payload.department,
        enabled=True,
    )

    db.add(person)
    db.commit()
    db.refresh(person)

    return {"id": person.id, "sales_person_name": person.sales_person_name}


@router.patch("/{person_id}", dependencies=[Depends(Require("crm:write"))])
async def update_sales_person(
    person_id: int,
    payload: SalesPersonUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a sales person."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Check for duplicate name if updating
    if "sales_person_name" in update_data:
        existing = db.query(SalesPerson).filter(
            SalesPerson.sales_person_name == update_data["sales_person_name"],
            SalesPerson.id != person_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Sales person name already exists")

    for key, value in update_data.items():
        setattr(person, key, value)

    db.commit()
    db.refresh(person)

    return {"id": person.id, "sales_person_name": person.sales_person_name}


@router.delete("/{person_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_sales_person(person_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete (disable) a sales person."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    # Soft delete by disabling
    person.enabled = False
    db.commit()

    return {"success": True, "message": "Sales person disabled"}
