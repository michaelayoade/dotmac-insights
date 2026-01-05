"""
Masters Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup, 
    Territory, SalesPerson
)
from app.api.sales_pkg.common import (
    CustomerGroupRequest,
    CustomerGroupUpdateRequest,
    TerritoryRequest,
    TerritoryUpdateRequest,
    SalesPersonRequest,
    SalesPersonUpdateRequest,
)

router = APIRouter()

@router.get("/customer-groups", dependencies=[Depends(Require("explorer:read"))])
async def list_customer_groups(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List customer groups."""
    query = db.query(CustomerGroup)
    if search:
        query = query.filter(CustomerGroup.customer_group_name.ilike(f"%{search}%"))

    total = query.count()
    groups = query.order_by(CustomerGroup.customer_group_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "customer_groups": [
            {
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
            for group in groups
        ],
    }


@router.get("/customer-groups/{group_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_customer_group(
    group_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a customer group by id."""
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


@router.post("/customer-groups", dependencies=[Depends(Require("sales:write"))])
async def create_customer_group(
    payload: CustomerGroupRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a customer group locally."""
    group = CustomerGroup(
        customer_group_name=payload.customer_group_name,
        parent_customer_group=payload.parent_customer_group,
        is_group=payload.is_group,
        default_price_list=payload.default_price_list,
        default_payment_terms_template=payload.default_payment_terms_template,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"id": group.id}


@router.patch("/customer-groups/{group_id}", dependencies=[Depends(Require("sales:write"))])
async def update_customer_group(
    group_id: int,
    payload: CustomerGroupUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a customer group locally."""
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Customer group not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)

    db.commit()
    db.refresh(group)
    return {"id": group.id}


@router.delete("/customer-groups/{group_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_customer_group(
    group_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a customer group."""
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Customer group not found")

    db.delete(group)
    db.commit()
    return {"status": "deleted", "customer_group_id": group_id}


@router.get("/territories", dependencies=[Depends(Require("explorer:read"))])
async def list_territories(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List territories."""
    query = db.query(Territory)
    if search:
        query = query.filter(Territory.territory_name.ilike(f"%{search}%"))

    total = query.count()
    territories = query.order_by(Territory.territory_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "territories": [
            {
                "id": terr.id,
                "erpnext_id": terr.erpnext_id,
                "territory_name": terr.territory_name,
                "parent_territory": terr.parent_territory,
                "is_group": terr.is_group,
                "territory_manager": terr.territory_manager,
                "lft": terr.lft,
                "rgt": terr.rgt,
            }
            for terr in territories
        ],
    }


@router.get("/territories/{territory_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_territory(
    territory_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a territory by id."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    return {
        "id": territory.id,
        "erpnext_id": territory.erpnext_id,
        "territory_name": territory.territory_name,
        "parent_territory": territory.parent_territory,
        "is_group": territory.is_group,
        "territory_manager": territory.territory_manager,
        "lft": territory.lft,
        "rgt": territory.rgt,
    }


@router.post("/territories", dependencies=[Depends(Require("sales:write"))])
async def create_territory(
    payload: TerritoryRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a territory locally."""
    territory = Territory(
        territory_name=payload.territory_name,
        parent_territory=payload.parent_territory,
        is_group=payload.is_group,
        territory_manager=payload.territory_manager,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    db.add(territory)
    db.commit()
    db.refresh(territory)
    return {"id": territory.id}


@router.patch("/territories/{territory_id}", dependencies=[Depends(Require("sales:write"))])
async def update_territory(
    territory_id: int,
    payload: TerritoryUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a territory locally."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(territory, key, value)

    db.commit()
    db.refresh(territory)
    return {"id": territory.id}


@router.delete("/territories/{territory_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_territory(
    territory_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a territory."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    db.delete(territory)
    db.commit()
    return {"status": "deleted", "territory_id": territory_id}


@router.get("/sales-persons", dependencies=[Depends(Require("explorer:read"))])
async def list_sales_persons(
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List sales persons."""
    query = db.query(SalesPerson)
    if not include_disabled:
        query = query.filter(SalesPerson.enabled == True)
    if search:
        query = query.filter(SalesPerson.sales_person_name.ilike(f"%{search}%"))

    total = query.count()
    sales_people = query.order_by(SalesPerson.sales_person_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sales_persons": [
            {
                "id": person.id,
                "erpnext_id": person.erpnext_id,
                "sales_person_name": person.sales_person_name,
                "parent_sales_person": person.parent_sales_person,
                "is_group": person.is_group,
                "employee": person.employee,
                "department": person.department,
                "employee_id": person.employee_id,
                "enabled": person.enabled,
                "commission_rate": float(person.commission_rate or 0),
                "lft": person.lft,
                "rgt": person.rgt,
            }
            for person in sales_people
        ],
    }


@router.get("/sales-persons/{person_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_sales_person(
    person_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a sales person by id."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    return {
        "id": person.id,
        "erpnext_id": person.erpnext_id,
        "sales_person_name": person.sales_person_name,
        "parent_sales_person": person.parent_sales_person,
        "is_group": person.is_group,
        "employee": person.employee,
        "department": person.department,
        "employee_id": person.employee_id,
        "enabled": person.enabled,
        "commission_rate": float(person.commission_rate or 0),
        "lft": person.lft,
        "rgt": person.rgt,
    }


@router.post("/sales-persons", dependencies=[Depends(Require("sales:write"))])
async def create_sales_person(
    payload: SalesPersonRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a sales person locally."""
    person = SalesPerson(
        sales_person_name=payload.sales_person_name,
        parent_sales_person=payload.parent_sales_person,
        is_group=payload.is_group,
        employee=payload.employee,
        department=payload.department,
        employee_id=payload.employee_id,
        enabled=payload.enabled,
        commission_rate=payload.commission_rate,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"id": person.id}


@router.patch("/sales-persons/{person_id}", dependencies=[Depends(Require("sales:write"))])
async def update_sales_person(
    person_id: int,
    payload: SalesPersonUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a sales person locally."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(person, key, value)

    db.commit()
    db.refresh(person)
    return {"id": person.id}


@router.delete("/sales-persons/{person_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_sales_person(
    person_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a sales person."""
    person = db.query(SalesPerson).filter(SalesPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Sales person not found")

    person.enabled = False
    db.commit()
    return {"status": "disabled", "sales_person_id": person_id}
