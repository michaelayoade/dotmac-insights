"""
Customer Groups API

Manages customer categorization groups for CRM.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.sales import CustomerGroup

router = APIRouter(prefix="/customer-groups", tags=["crm-config-customer-groups"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CustomerGroupBase(BaseModel):
    """Base schema for customer groups."""
    customer_group_name: str
    parent_customer_group: Optional[str] = None
    is_group: bool = False
    default_price_list: Optional[str] = None
    default_payment_terms_template: Optional[str] = None


class CustomerGroupCreate(CustomerGroupBase):
    """Schema for creating a customer group."""
    pass


class CustomerGroupUpdate(BaseModel):
    """Schema for updating a customer group."""
    customer_group_name: Optional[str] = None
    parent_customer_group: Optional[str] = None
    is_group: Optional[bool] = None
    default_price_list: Optional[str] = None
    default_payment_terms_template: Optional[str] = None


class CustomerGroupResponse(BaseModel):
    """Schema for customer group response."""
    id: int
    erpnext_id: Optional[str]
    customer_group_name: str
    parent_customer_group: Optional[str]
    is_group: bool
    default_price_list: Optional[str]
    default_payment_terms_template: Optional[str]
    lft: Optional[int]
    rgt: Optional[int]

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
async def list_customer_groups(
    search: Optional[str] = None,
    parent: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List customer groups with filtering."""
    query = db.query(CustomerGroup)

    if search:
        query = query.filter(CustomerGroup.customer_group_name.ilike(f"%{search}%"))

    if parent:
        query = query.filter(CustomerGroup.parent_customer_group == parent)

    total = query.count()
    groups = query.order_by(CustomerGroup.customer_group_name).offset(offset).limit(limit).all()

    return {
        "data": [
            {
                "id": g.id,
                "erpnext_id": g.erpnext_id,
                "customer_group_name": g.customer_group_name,
                "parent_customer_group": g.parent_customer_group,
                "is_group": g.is_group,
                "default_price_list": g.default_price_list,
                "default_payment_terms_template": g.default_payment_terms_template,
                "lft": g.lft,
                "rgt": g.rgt,
            }
            for g in groups
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{group_id}", dependencies=[Depends(Require("crm:read"))])
async def get_customer_group(group_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a customer group by ID."""
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Customer group not found")

    return {
        "id": group.id,
        "erpnext_id": group.erpnext_id,
        "customer_group_name": group.customer_group_name,
        "parent_customer_group": group.parent_customer_group,
        "is_group": group.is_group,
        "default_price_list": group.default_price_list,
        "default_payment_terms_template": group.default_payment_terms_template,
        "lft": group.lft,
        "rgt": group.rgt,
    }


@router.post("", dependencies=[Depends(Require("crm:write"))], status_code=201)
async def create_customer_group(
    payload: CustomerGroupCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new customer group."""
    # Check for duplicate name
    existing = db.query(CustomerGroup).filter(
        CustomerGroup.customer_group_name == payload.customer_group_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Customer group name already exists")

    group = CustomerGroup(
        customer_group_name=payload.customer_group_name,
        parent_customer_group=payload.parent_customer_group,
        is_group=payload.is_group,
        default_price_list=payload.default_price_list,
        default_payment_terms_template=payload.default_payment_terms_template,
    )

    db.add(group)
    db.commit()
    db.refresh(group)

    return {"id": group.id, "customer_group_name": group.customer_group_name}


@router.patch("/{group_id}", dependencies=[Depends(Require("crm:write"))])
async def update_customer_group(
    group_id: int,
    payload: CustomerGroupUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a customer group."""
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Customer group not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Check for duplicate name if updating
    if "customer_group_name" in update_data:
        existing = db.query(CustomerGroup).filter(
            CustomerGroup.customer_group_name == update_data["customer_group_name"],
            CustomerGroup.id != group_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Customer group name already exists")

    for key, value in update_data.items():
        setattr(group, key, value)

    db.commit()
    db.refresh(group)

    return {"id": group.id, "customer_group_name": group.customer_group_name}


@router.delete("/{group_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_customer_group(group_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a customer group."""
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Customer group not found")

    # Check for child groups
    children = db.query(CustomerGroup).filter(
        CustomerGroup.parent_customer_group == group.customer_group_name
    ).count()
    if children > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete customer group with child groups"
        )

    db.delete(group)
    db.commit()

    return {"success": True, "message": "Customer group deleted"}
