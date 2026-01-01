"""
Orders Endpoints
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
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup, 
    Territory, SalesPerson
)
from app.api.sales_pkg.common import (
    _parse_sales_order_status,
    _parse_quotation_status,
    _serialize_sales_order,
    _serialize_quotation,
)

router = APIRouter()

@router.get("/orders", dependencies=[Depends(Require("explorer:read"))])
async def list_sales_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List sales orders."""
    query = db.query(SalesOrder)

    if status:
        status_enum = _parse_sales_order_status(status)
        if status_enum:
            query = query.filter(SalesOrder.status == status_enum)
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)

    total = query.count()
    orders = query.order_by(SalesOrder.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "orders": [_serialize_sales_order(order) for order in orders],
    }


@router.get("/orders/{order_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_sales_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a sales order by id."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    return _serialize_sales_order(order)


@router.get("/quotations", dependencies=[Depends(Require("explorer:read"))])
async def list_quotations(
    status: Optional[str] = None,
    customer_name: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List quotations."""
    query = db.query(Quotation).filter(Quotation.is_deleted == False)

    if status:
        status_enum = _parse_quotation_status(status)
        if status_enum:
            query = query.filter(Quotation.status == status_enum)
    if customer_name:
        query = query.filter(Quotation.customer_name.ilike(f"%{customer_name}%"))

    total = query.count()
    quotes = query.order_by(Quotation.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "quotations": [_serialize_quotation(quote) for quote in quotes],
    }


@router.get("/quotations/{quotation_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a quotation by id."""
    quote = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    return _serialize_quotation(quote)

