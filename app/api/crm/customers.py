"""
Customer CRUD Endpoints

This module is the single source of truth for customer master data.
Other modules (accounting, sales, support) reference Customer IDs but
should use this API for creates/updates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType

router = APIRouter(prefix="/customers", tags=["crm-customers"])


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class CustomerCreate(BaseModel):
    """Schema for creating a customer."""
    name: str
    email: Optional[str] = None
    billing_email: Optional[str] = None
    phone: Optional[str] = None
    phone_secondary: Optional[str] = None
    address: Optional[str] = None
    address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "Nigeria"
    gps: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    customer_type: Optional[str] = "residential"
    status: Optional[str] = "active"
    billing_type: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    name: Optional[str] = None
    email: Optional[str] = None
    billing_email: Optional[str] = None
    phone: Optional[str] = None
    phone_secondary: Optional[str] = None
    address: Optional[str] = None
    address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    gps: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    customer_type: Optional[str] = None
    status: Optional[str] = None
    billing_type: Optional[str] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_customer_type(value: Optional[str]) -> Optional[CustomerType]:
    """Parse customer type string to enum."""
    if not value:
        return None
    try:
        return CustomerType(value.lower())
    except ValueError:
        return None


def _parse_customer_status(value: Optional[str]) -> Optional[CustomerStatus]:
    """Parse customer status string to enum."""
    if not value:
        return None
    try:
        return CustomerStatus(value.lower())
    except ValueError:
        return None


def _parse_billing_type(value: Optional[str]) -> Optional[BillingType]:
    """Parse billing type string to enum."""
    if not value:
        return None
    try:
        return BillingType(value.lower())
    except ValueError:
        return None


def _serialize_customer(customer: Customer) -> Dict[str, Any]:
    """Serialize customer to dict."""
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "billing_email": customer.billing_email,
        "phone": customer.phone,
        "phone_secondary": customer.phone_secondary,
        "address": customer.address,
        "address_2": customer.address_2,
        "city": customer.city,
        "state": customer.state,
        "zip_code": customer.zip_code,
        "country": customer.country,
        "gps": customer.gps,
        "latitude": customer.latitude,
        "longitude": customer.longitude,
        "customer_type": customer.customer_type.value if customer.customer_type else None,
        "status": customer.status.value if customer.status else None,
        "billing_type": customer.billing_type.value if customer.billing_type else None,
        "external_ids": {
            "splynx_id": customer.splynx_id,
            "erpnext_id": customer.erpnext_id,
            "chatwoot_contact_id": customer.chatwoot_contact_id,
            "zoho_id": customer.zoho_id,
        },
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


# =============================================================================
# LIST & DETAIL
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
def list_customers(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List customers with filters."""
    query = db.query(Customer).filter(Customer.is_deleted == False)

    if status:
        status_enum = _parse_customer_status(status)
        if status_enum:
            query = query.filter(Customer.status == status_enum)

    if customer_type:
        type_enum = _parse_customer_type(customer_type)
        if type_enum:
            query = query.filter(Customer.customer_type == type_enum)

    if city:
        query = query.filter(Customer.city.ilike(f"%{city}%"))

    if state:
        query = query.filter(Customer.state.ilike(f"%{state}%"))

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Customer.name.ilike(like),
                Customer.email.ilike(like),
                Customer.phone.ilike(like),
                Customer.address.ilike(like),
            )
        )

    total = query.count()
    customers = query.order_by(Customer.name.asc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "customers": [_serialize_customer(c) for c in customers],
    }


@router.get("/{customer_id}", dependencies=[Depends(Require("crm:read"))])
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer detail."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return _serialize_customer(customer)


# =============================================================================
# CRUD
# =============================================================================

@router.post("", dependencies=[Depends(Require("crm:write"))])
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new customer."""
    customer = Customer(
        name=data.name,
        email=data.email,
        billing_email=data.billing_email,
        phone=data.phone,
        phone_secondary=data.phone_secondary,
        address=data.address,
        address_2=data.address_2,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
        country=data.country or "Nigeria",
        gps=data.gps,
        latitude=data.latitude,
        longitude=data.longitude,
        customer_type=_parse_customer_type(data.customer_type) or CustomerType.RESIDENTIAL,
        status=_parse_customer_status(data.status) or CustomerStatus.ACTIVE,
        billing_type=_parse_billing_type(data.billing_type),
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return {
        "message": "Customer created",
        "id": customer.id,
        "customer": _serialize_customer(customer),
    }


@router.patch("/{customer_id}", dependencies=[Depends(Require("crm:write"))])
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a customer."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if data.name is not None:
        customer.name = data.name
    if data.email is not None:
        customer.email = data.email
    if data.billing_email is not None:
        customer.billing_email = data.billing_email
    if data.phone is not None:
        customer.phone = data.phone
    if data.phone_secondary is not None:
        customer.phone_secondary = data.phone_secondary
    if data.address is not None:
        customer.address = data.address
    if data.address_2 is not None:
        customer.address_2 = data.address_2
    if data.city is not None:
        customer.city = data.city
    if data.state is not None:
        customer.state = data.state
    if data.zip_code is not None:
        customer.zip_code = data.zip_code
    if data.country is not None:
        customer.country = data.country
    if data.gps is not None:
        customer.gps = data.gps
    if data.latitude is not None:
        customer.latitude = data.latitude
    if data.longitude is not None:
        customer.longitude = data.longitude
    if data.customer_type is not None:
        customer.customer_type = _parse_customer_type(data.customer_type) or customer.customer_type
    if data.status is not None:
        customer.status = _parse_customer_status(data.status) or customer.status
    if data.billing_type is not None:
        customer.billing_type = _parse_billing_type(data.billing_type)

    db.commit()
    db.refresh(customer)

    return {
        "message": "Customer updated",
        "id": customer.id,
        "customer": _serialize_customer(customer),
    }


@router.delete("/{customer_id}", dependencies=[Depends(Require("crm:write"))])
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.is_deleted = True
    customer.deleted_at = datetime.now(timezone.utc)
    customer.deleted_by_id = principal.id
    db.commit()

    return {"message": "Customer deleted", "id": customer_id}


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.get("/stats/summary", dependencies=[Depends(Require("crm:read"))])
def get_customer_stats(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer statistics summary."""
    from sqlalchemy import func

    total = db.query(func.count(Customer.id)).filter(Customer.is_deleted == False).scalar() or 0

    by_status = (
        db.query(Customer.status, func.count(Customer.id))
        .filter(Customer.is_deleted == False)
        .group_by(Customer.status)
        .all()
    )

    by_type = (
        db.query(Customer.customer_type, func.count(Customer.id))
        .filter(Customer.is_deleted == False)
        .group_by(Customer.customer_type)
        .all()
    )

    return {
        "total": total,
        "by_status": {s.value if s else "unknown": c for s, c in by_status},
        "by_type": {t.value if t else "unknown": c for t, c in by_type},
    }
