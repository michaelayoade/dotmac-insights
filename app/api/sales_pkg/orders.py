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
from app.models.party import CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup,
    Territory, SalesPerson
)
from app.api.sales_pkg.common import (
    Principal,
    SalesOrderRequest,
    SalesOrderUpdateRequest,
    QuotationRequest,
    QuotationUpdateRequest,
    SalesOrderStatus,
    QuotationStatus,
    _parse_date_only,
    _parse_sales_order_status,
    _parse_quotation_status,
    _serialize_sales_order,
    _serialize_quotation,
    get_company_context,
    get_current_principal,
)

router = APIRouter()


# ==================== READ ENDPOINTS ====================

@router.get("/orders", dependencies=[Depends(Require("explorer:read"))])
async def list_sales_orders(
    status: Optional[str] = None,
    customer_account_id: Optional[int] = None,
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
    if customer_account_id:
        query = query.filter(SalesOrder.customer_account_id == customer_account_id)

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


# ==================== WRITE ENDPOINTS ====================

@router.post("/orders", dependencies=[Depends(Require("sales:write"))])
async def create_sales_order(
    payload: SalesOrderRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a sales order locally."""
    if payload.customer_account_id:
        if not db.query(CustomerAccount.id).filter(CustomerAccount.id == payload.customer_account_id).first():
            raise HTTPException(
                status_code=400,
                detail=f"Customer account {payload.customer_account_id} not found",
            )

    order = SalesOrder(
        erpnext_id=None,
        customer_account_id=payload.customer_account_id,
        customer_name=payload.customer_name,
        order_type=payload.order_type,
        company=payload.company or get_company_context(allow_null=True),
        currency=payload.currency,
        transaction_date=_parse_date_only(payload.transaction_date),
        delivery_date=_parse_date_only(payload.delivery_date),
        total_qty=payload.total_qty,
        total=payload.total,
        net_total=payload.net_total,
        grand_total=payload.grand_total,
        rounded_total=payload.rounded_total,
        total_taxes_and_charges=payload.total_taxes_and_charges,
        per_delivered=payload.per_delivered,
        per_billed=payload.per_billed,
        billing_status=payload.billing_status,
        delivery_status=payload.delivery_status,
        status=_parse_sales_order_status(payload.status) or SalesOrderStatus.DRAFT,
        sales_partner=payload.sales_partner,
        territory=payload.territory,
        source=payload.source or "local",
        campaign=payload.campaign,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _serialize_sales_order(order)


@router.patch("/orders/{order_id}", dependencies=[Depends(Require("sales:write"))])
async def update_sales_order(
    order_id: int,
    payload: SalesOrderUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a sales order locally."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if payload.customer_account_id is not None:
        if (
            payload.customer_account_id
            and not db.query(CustomerAccount.id)
                .filter(CustomerAccount.id == payload.customer_account_id)
                .first()
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Customer account {payload.customer_account_id} not found",
            )
        order.customer_account_id = payload.customer_account_id
    if payload.customer_name is not None:
        order.customer_name = payload.customer_name
    if payload.order_type is not None:
        order.order_type = payload.order_type
    if payload.company is not None:
        order.company = payload.company
    if payload.currency is not None:
        order.currency = payload.currency
    if payload.transaction_date is not None:
        order.transaction_date = _parse_date_only(payload.transaction_date)
    if payload.delivery_date is not None:
        order.delivery_date = _parse_date_only(payload.delivery_date)
    if payload.total_qty is not None:
        order.total_qty = payload.total_qty
    if payload.total is not None:
        order.total = payload.total
    if payload.net_total is not None:
        order.net_total = payload.net_total
    if payload.grand_total is not None:
        order.grand_total = payload.grand_total
    if payload.rounded_total is not None:
        order.rounded_total = payload.rounded_total
    if payload.total_taxes_and_charges is not None:
        order.total_taxes_and_charges = payload.total_taxes_and_charges
    if payload.per_delivered is not None:
        order.per_delivered = payload.per_delivered
    if payload.per_billed is not None:
        order.per_billed = payload.per_billed
    if payload.billing_status is not None:
        order.billing_status = payload.billing_status
    if payload.delivery_status is not None:
        order.delivery_status = payload.delivery_status
    if payload.status is not None:
        order.status = _parse_sales_order_status(payload.status) or order.status
    if payload.sales_partner is not None:
        order.sales_partner = payload.sales_partner
    if payload.territory is not None:
        order.territory = payload.territory
    if payload.source is not None:
        order.source = payload.source
    if payload.campaign is not None:
        order.campaign = payload.campaign

    db.commit()
    db.refresh(order)
    return _serialize_sales_order(order)


@router.delete("/orders/{order_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_sales_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a sales order."""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    db.delete(order)
    db.commit()
    return {"status": "deleted", "order_id": order_id}


@router.post("/quotations", dependencies=[Depends(Require("sales:write"))])
async def create_quotation(
    payload: QuotationRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a quotation locally."""
    quote = Quotation(
        erpnext_id=None,
        quotation_to=payload.quotation_to,
        party_name=payload.party_name,
        customer_name=payload.customer_name,
        order_type=payload.order_type,
        company=payload.company or get_company_context(allow_null=True),
        currency=payload.currency,
        transaction_date=_parse_date_only(payload.transaction_date),
        valid_till=_parse_date_only(payload.valid_till),
        total_qty=payload.total_qty,
        total=payload.total,
        net_total=payload.net_total,
        grand_total=payload.grand_total,
        rounded_total=payload.rounded_total,
        total_taxes_and_charges=payload.total_taxes_and_charges,
        status=_parse_quotation_status(payload.status) or QuotationStatus.DRAFT,
        sales_partner=payload.sales_partner,
        territory=payload.territory,
        source=payload.source or "local",
        campaign=payload.campaign,
        order_lost_reason=payload.order_lost_reason,
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return _serialize_quotation(quote)


@router.patch("/quotations/{quotation_id}", dependencies=[Depends(Require("sales:write"))])
async def update_quotation(
    quotation_id: int,
    payload: QuotationUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a quotation locally."""
    quote = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    if payload.quotation_to is not None:
        quote.quotation_to = payload.quotation_to
    if payload.party_name is not None:
        quote.party_name = payload.party_name
    if payload.customer_name is not None:
        quote.customer_name = payload.customer_name
    if payload.order_type is not None:
        quote.order_type = payload.order_type
    if payload.company is not None:
        quote.company = payload.company
    if payload.currency is not None:
        quote.currency = payload.currency
    if payload.transaction_date is not None:
        quote.transaction_date = _parse_date_only(payload.transaction_date)
    if payload.valid_till is not None:
        quote.valid_till = _parse_date_only(payload.valid_till)
    if payload.total_qty is not None:
        quote.total_qty = payload.total_qty
    if payload.total is not None:
        quote.total = payload.total
    if payload.net_total is not None:
        quote.net_total = payload.net_total
    if payload.grand_total is not None:
        quote.grand_total = payload.grand_total
    if payload.rounded_total is not None:
        quote.rounded_total = payload.rounded_total
    if payload.total_taxes_and_charges is not None:
        quote.total_taxes_and_charges = payload.total_taxes_and_charges
    if payload.status is not None:
        quote.status = _parse_quotation_status(payload.status) or quote.status
    if payload.sales_partner is not None:
        quote.sales_partner = payload.sales_partner
    if payload.territory is not None:
        quote.territory = payload.territory
    if payload.source is not None:
        quote.source = payload.source
    if payload.campaign is not None:
        quote.campaign = payload.campaign
    if payload.order_lost_reason is not None:
        quote.order_lost_reason = payload.order_lost_reason

    if hasattr(quote, "updated_by_id"):
        setattr(quote, "updated_by_id", principal.id)
    if hasattr(quote, "write_back_status"):
        setattr(quote, "write_back_status", "pending")
    db.commit()
    db.refresh(quote)
    return _serialize_quotation(quote)


@router.delete("/quotations/{quotation_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_quotation(
    quotation_id: int,
    soft: bool = Query(default=True, description="Soft delete by marking is_deleted"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a quotation."""
    quote = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    quote.is_deleted = True
    quote.deleted_at = datetime.now(timezone.utc)
    quote.deleted_by_id = principal.id
    if hasattr(quote, "write_back_status"):
        setattr(quote, "write_back_status", "pending")
    db.commit()
    return {"status": "disabled", "quotation_id": quotation_id}
