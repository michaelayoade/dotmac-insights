"""
Sales Orders API

Manages sales orders within the CRM module.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.sales import SalesOrder, SalesOrderStatus
from app.models.contact import Contact

router = APIRouter(prefix="/orders", tags=["crm-sales-orders"])


# =============================================================================
# SCHEMAS
# =============================================================================

class SalesOrderBase(BaseModel):
    """Base schema for sales orders."""
    contact_id: Optional[int] = None
    customer_name: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    currency: str = "NGN"
    total_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    notes: Optional[str] = None


class SalesOrderCreate(SalesOrderBase):
    """Schema for creating a sales order."""
    pass


class SalesOrderUpdate(BaseModel):
    """Schema for updating a sales order."""
    contact_id: Optional[int] = None
    customer_name: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    status: Optional[str] = None
    total_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None
    notes: Optional[str] = None


class SalesOrderResponse(BaseModel):
    """Schema for sales order response."""
    id: int
    erpnext_id: Optional[str]
    contact_id: Optional[int]
    customer_id: Optional[int]
    customer_name: Optional[str]
    status: str
    order_date: Optional[datetime]
    delivery_date: Optional[datetime]
    currency: str
    total_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_status(status: Optional[str]) -> Optional[SalesOrderStatus]:
    """Parse status string to enum."""
    if status is None:
        return None
    try:
        return SalesOrderStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status}. Allowed: {', '.join(s.value for s in SalesOrderStatus)}",
        )


def _serialize_order(order: SalesOrder) -> Dict[str, Any]:
    """Serialize a sales order to dict."""
    return {
        "id": order.id,
        "erpnext_id": order.erpnext_id,
        "contact_id": order.contact_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "status": order.status.value if order.status else None,
        "order_date": order.transaction_date.isoformat() if order.transaction_date else None,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "currency": order.currency,
        "total_amount": float(order.total or 0),
        "tax_amount": float(order.total_taxes_and_charges or 0),
        "grand_total": float(order.grand_total or 0),
        "notes": None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
async def list_orders(
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List sales orders with filtering."""
    query = db.query(SalesOrder)

    if status:
        status_enum = _parse_status(status)
        if status_enum:
            query = query.filter(SalesOrder.status == status_enum)

    if contact_id:
        query = query.filter(SalesOrder.contact_id == contact_id)

    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)

    total = query.count()
    orders = query.order_by(SalesOrder.id.desc()).offset(offset).limit(limit).all()

    return {
        "data": [_serialize_order(order) for order in orders],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{order_id}", dependencies=[Depends(Require("crm:read"))])
async def get_order(order_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a sales order by ID."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    return _serialize_order(order)


@router.post("", dependencies=[Depends(Require("crm:write"))], status_code=201)
async def create_order(
    payload: SalesOrderCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new sales order."""
    # Validate contact if provided
    if payload.contact_id:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    order = SalesOrder(
        contact_id=payload.contact_id,
        customer_name=payload.customer_name,
        transaction_date=payload.order_date,
        delivery_date=payload.delivery_date,
        currency=payload.currency,
        total=payload.total_amount,
        total_taxes_and_charges=payload.tax_amount,
        grand_total=payload.grand_total,
        status=SalesOrderStatus.DRAFT,
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return _serialize_order(order)


@router.patch("/{order_id}", dependencies=[Depends(Require("crm:write"))])
async def update_order(
    order_id: int,
    payload: SalesOrderUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a sales order."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle status conversion
    if "status" in update_data and update_data["status"]:
        update_data["status"] = _parse_status(update_data["status"])

    # Map field names
    field_mapping = {
        "order_date": "transaction_date",
        "total_amount": "total",
        "tax_amount": "total_taxes_and_charges",
    }

    for key, value in update_data.items():
        mapped_key = field_mapping.get(key, key)
        if hasattr(order, mapped_key):
            setattr(order, mapped_key, value)

    db.commit()
    db.refresh(order)

    return _serialize_order(order)


@router.delete("/{order_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_order(order_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a sales order."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    # Soft delete by setting status to cancelled
    order.status = SalesOrderStatus.CANCELLED
    db.commit()

    return {"success": True, "message": "Sales order cancelled"}


@router.post("/{order_id}/submit", dependencies=[Depends(Require("crm:write"))])
async def submit_order(order_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Submit a sales order (move from draft to submitted)."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if order.status != SalesOrderStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft orders can be submitted")

    order.status = SalesOrderStatus.SUBMITTED
    order.docstatus = 1
    db.commit()
    db.refresh(order)

    return _serialize_order(order)
