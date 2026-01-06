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
from app.utils.normalizers import normalize_phone
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.party import CustomerAccount, Party
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup,
    Territory, SalesPerson
)
from app.models.document_lines import SalesOrderItem, QuotationItem
from app.models.tax import TaxCode
from app.api.sales_pkg.common import (
    Principal,
    SalesOrderRequest,
    SalesOrderUpdateRequest,
    SalesOrderLineItemRequest,
    QuotationRequest,
    QuotationUpdateRequest,
    QuotationLineItemRequest,
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


def _resolve_tax_rate(db: Session, tax_code_id: Optional[int], tax_rate: Decimal) -> Decimal:
    if tax_code_id and (tax_rate is None or tax_rate == Decimal("0")):
        code = db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
        if code:
            return Decimal(str(code.rate or 0))
    return tax_rate or Decimal("0")


def _compute_line_amount(qty: Decimal, rate: Decimal, discount_percentage: Decimal, discount_amount: Decimal) -> Decimal:
    amount = qty * rate
    if discount_percentage:
        amount = amount * (Decimal("1") - (discount_percentage / Decimal("100")))
    elif discount_amount:
        amount = amount - discount_amount
    return amount


def _compose_address(
    line1: Optional[str],
    line2: Optional[str],
    city: Optional[str],
    state: Optional[str],
    postal_code: Optional[str],
    country: Optional[str],
) -> Optional[str]:
    parts = [line1, line2, city, state, postal_code, country]
    cleaned = [part for part in parts if part]
    return ", ".join(cleaned) if cleaned else None


def _extract_party_address(addresses: Optional[list]) -> dict:
    if not addresses:
        return {}
    for address in addresses:
        if isinstance(address, dict) and (address.get("address_line1") or address.get("address")):
            return address
    return addresses[0] if isinstance(addresses[0], dict) else {}


def _normalize_contact_phone(phone: Optional[str], country: Optional[str]) -> Optional[str]:
    if not phone:
        return phone
    normalized = normalize_phone(phone, country=country or "NG")
    return normalized.normalized or phone


def _build_sales_order_items(
    db: Session,
    order_id: int,
    items_payload: List[SalesOrderLineItemRequest],
) -> Dict[str, Decimal]:
    totals = {
        "total_qty": Decimal("0"),
        "total": Decimal("0"),
        "tax_total": Decimal("0"),
    }
    for item in items_payload:
        qty = item.qty or Decimal("0")
        rate = item.rate or Decimal("0")
        discount_percentage = item.discount_percentage or Decimal("0")
        discount_amount = item.discount_amount or Decimal("0")
        tax_rate = _resolve_tax_rate(db, item.tax_code_id, item.tax_rate)
        amount = _compute_line_amount(qty, rate, discount_percentage, discount_amount)
        tax_amount = item.tax_amount or (amount * (tax_rate / Decimal("100")) if tax_rate else Decimal("0"))
        so_item = SalesOrderItem(
            sales_order_id=order_id,
            item_code=item.item_code,
            item_name=item.item_name or item.description,
            description=item.description,
            qty=qty,
            rate=rate,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            amount=amount,
            net_amount=amount,
            uom=item.uom,
            warehouse=item.warehouse,
            tax_code_id=item.tax_code_id,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            is_tax_inclusive=item.is_tax_inclusive,
        )
        db.add(so_item)
        totals["total_qty"] += qty
        totals["total"] += amount
        totals["tax_total"] += tax_amount

    return totals


def _build_quotation_items(
    db: Session,
    quotation_id: int,
    items_payload: List[QuotationLineItemRequest],
) -> Dict[str, Decimal]:
    totals = {
        "total_qty": Decimal("0"),
        "total": Decimal("0"),
        "tax_total": Decimal("0"),
    }
    for item in items_payload:
        qty = item.qty or Decimal("0")
        rate = item.rate or Decimal("0")
        discount_percentage = item.discount_percentage or Decimal("0")
        discount_amount = item.discount_amount or Decimal("0")
        tax_rate = _resolve_tax_rate(db, item.tax_code_id, item.tax_rate)
        amount = _compute_line_amount(qty, rate, discount_percentage, discount_amount)
        tax_amount = item.tax_amount or (amount * (tax_rate / Decimal("100")) if tax_rate else Decimal("0"))
        quote_item = QuotationItem(
            quotation_id=quotation_id,
            item_code=item.item_code,
            item_name=item.item_name or item.description,
            description=item.description,
            qty=qty,
            rate=rate,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            amount=amount,
            net_amount=amount,
            uom=item.uom,
            warehouse=item.warehouse,
            tax_code_id=item.tax_code_id,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            is_tax_inclusive=item.is_tax_inclusive,
        )
        db.add(quote_item)
        totals["total_qty"] += qty
        totals["total"] += amount
        totals["tax_total"] += tax_amount

    return totals


# ==================== READ ENDPOINTS ====================

@router.get("/orders", dependencies=[Depends(Require("explorer:read"))])
async def list_sales_orders(
    status: Optional[str] = None,
    customer_account_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    party_id: Optional[int] = Query(None, include_in_schema=False),
    search: Optional[str] = None,
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
    if search:
        like = f"%{search}%"
        query = query.outerjoin(Party, SalesOrder.party_id == Party.id).filter(
            or_(
                SalesOrder.customer.ilike(like),
                SalesOrder.customer_name.ilike(like),
                SalesOrder.erpnext_id.ilike(like),
                Party.name.ilike(like),
                Party.legal_name.ilike(like),
                Party.trading_name.ilike(like),
                Party.primary_email.ilike(like),
            )
        )
    if customer_account_id:
        query = query.filter(SalesOrder.customer_account_id == customer_account_id)
    if customer_id or party_id:
        query = query.filter(SalesOrder.party_id == (customer_id or party_id))

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
    search: Optional[str] = None,
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
    if search:
        like = f"%{search}%"
        query = query.outerjoin(Party, Quotation.party_id == Party.id).filter(
            or_(
                Quotation.party_name.ilike(like),
                Quotation.customer_name.ilike(like),
                Quotation.erpnext_id.ilike(like),
                Party.name.ilike(like),
                Party.legal_name.ilike(like),
                Party.trading_name.ilike(like),
                Party.primary_email.ilike(like),
            )
        )
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
    quote = None
    if payload.quotation_id:
        quote = db.query(Quotation).filter(Quotation.id == payload.quotation_id, Quotation.is_deleted == False).first()
        if not quote:
            raise HTTPException(status_code=404, detail="Linked quotation not found")

    if payload.customer_account_id:
        if not db.query(CustomerAccount.id).filter(CustomerAccount.id == payload.customer_account_id).first():
            raise HTTPException(
                status_code=400,
                detail=f"Customer account {payload.customer_account_id} not found",
            )

    party_id = None
    if payload.customer_account_id:
        party_id = (
            db.query(CustomerAccount.party_id)
            .filter(CustomerAccount.id == payload.customer_account_id)
            .scalar()
        )
    elif quote and quote.party_id:
        party_id = quote.party_id

    billing_address_line1 = payload.billing_address_line1 or (quote.billing_address_line1 if quote else None)
    billing_address_line2 = payload.billing_address_line2 or (quote.billing_address_line2 if quote else None)
    billing_city = payload.billing_city or (quote.billing_city if quote else None)
    billing_state = payload.billing_state or (quote.billing_state if quote else None)
    billing_postal_code = payload.billing_postal_code or (quote.billing_postal_code if quote else None)
    billing_country = payload.billing_country or (quote.billing_country if quote else None)
    billing_gps_lat = payload.billing_gps_lat if payload.billing_gps_lat is not None else (
        quote.billing_gps_lat if quote else None
    )
    billing_gps_lng = payload.billing_gps_lng if payload.billing_gps_lng is not None else (
        quote.billing_gps_lng if quote else None
    )
    shipping_address_line1 = payload.shipping_address_line1 or (quote.shipping_address_line1 if quote else None)
    shipping_address_line2 = payload.shipping_address_line2 or (quote.shipping_address_line2 if quote else None)
    shipping_city = payload.shipping_city or (quote.shipping_city if quote else None)
    shipping_state = payload.shipping_state or (quote.shipping_state if quote else None)
    shipping_postal_code = payload.shipping_postal_code or (quote.shipping_postal_code if quote else None)
    shipping_country = payload.shipping_country or (quote.shipping_country if quote else None)
    shipping_gps_lat = payload.shipping_gps_lat if payload.shipping_gps_lat is not None else (
        quote.shipping_gps_lat if quote else None
    )
    shipping_gps_lng = payload.shipping_gps_lng if payload.shipping_gps_lng is not None else (
        quote.shipping_gps_lng if quote else None
    )
    billing_address = payload.billing_address or (quote.billing_address if quote else None)
    shipping_address = payload.shipping_address or (quote.shipping_address if quote else None)

    if payload.customer_account_id and party_id:
        party = db.query(Party).filter(Party.id == party_id).first()
        if party and party.addresses:
            addr = _extract_party_address(party.addresses)
            if not billing_address_line1:
                billing_address_line1 = addr.get("address_line1") or addr.get("address")
            if not billing_address_line2:
                billing_address_line2 = addr.get("address_line2")
            if not billing_city:
                billing_city = addr.get("city")
            if not billing_state:
                billing_state = addr.get("state")
            if not billing_postal_code:
                billing_postal_code = addr.get("postal_code")
            if not billing_country:
                billing_country = addr.get("country")
            if billing_gps_lat is None:
                billing_gps_lat = addr.get("gps_lat")
            if billing_gps_lng is None:
                billing_gps_lng = addr.get("gps_lng")
            if not shipping_address_line1:
                shipping_address_line1 = addr.get("address_line1") or addr.get("address")
            if not shipping_address_line2:
                shipping_address_line2 = addr.get("address_line2")
            if not shipping_city:
                shipping_city = addr.get("city")
            if not shipping_state:
                shipping_state = addr.get("state")
            if not shipping_postal_code:
                shipping_postal_code = addr.get("postal_code")
            if not shipping_country:
                shipping_country = addr.get("country")
            if shipping_gps_lat is None:
                shipping_gps_lat = addr.get("gps_lat")
            if shipping_gps_lng is None:
                shipping_gps_lng = addr.get("gps_lng")

    if not billing_address:
        billing_address = _compose_address(
            billing_address_line1,
            billing_address_line2,
            billing_city,
            billing_state,
            billing_postal_code,
            billing_country,
        )
    if not shipping_address:
        shipping_address = _compose_address(
            shipping_address_line1,
            shipping_address_line2,
            shipping_city,
            shipping_state,
            shipping_postal_code,
            shipping_country,
        )

    contact_phone = payload.contact_phone or (quote.contact_phone if quote else None)
    if contact_phone:
        phone_country = billing_country or shipping_country
        contact_phone = _normalize_contact_phone(contact_phone, phone_country)

    order = SalesOrder(
        erpnext_id=None,
        customer_account_id=payload.customer_account_id or (quote.customer_account_id if quote else None),
        party_id=party_id,
        quotation_id=payload.quotation_id,
        customer_name=payload.customer_name or (quote.customer_name if quote else None),
        contact_name=payload.contact_name or (quote.contact_name if quote else None),
        contact_email=payload.contact_email or (quote.contact_email if quote else None),
        contact_phone=contact_phone,
        billing_address=billing_address,
        billing_address_line1=billing_address_line1,
        billing_address_line2=billing_address_line2,
        billing_city=billing_city,
        billing_state=billing_state,
        billing_postal_code=billing_postal_code,
        billing_country=billing_country,
        billing_gps_lat=billing_gps_lat,
        billing_gps_lng=billing_gps_lng,
        shipping_address=shipping_address,
        shipping_address_line1=shipping_address_line1,
        shipping_address_line2=shipping_address_line2,
        shipping_city=shipping_city,
        shipping_state=shipping_state,
        shipping_postal_code=shipping_postal_code,
        shipping_country=shipping_country,
        shipping_gps_lat=shipping_gps_lat,
        shipping_gps_lng=shipping_gps_lng,
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
        sales_partner_id=payload.sales_partner_id,
        territory=payload.territory,
        source=payload.source or "local",
        campaign=payload.campaign,
    )
    db.add(order)
    db.flush()

    if payload.items:
        totals = _build_sales_order_items(db, order.id, payload.items)
        order.total_qty = totals["total_qty"]
        order.total = totals["total"]
        order.net_total = totals["total"]
        order.total_taxes_and_charges = totals["tax_total"]
        order.grand_total = totals["total"] + totals["tax_total"]
        order.rounded_total = round(order.grand_total or 0, 0)
    elif quote and quote.items:
        totals = {
            "total_qty": Decimal("0"),
            "total": Decimal("0"),
            "tax_total": Decimal("0"),
        }
        for q_item in quote.items:
            so_item = SalesOrderItem(
                sales_order_id=order.id,
                item_code=q_item.item_code,
                item_name=q_item.item_name,
                description=q_item.description,
                qty=q_item.qty,
                rate=q_item.rate,
                discount_percentage=q_item.discount_percentage,
                discount_amount=q_item.discount_amount,
                amount=q_item.amount,
                net_amount=q_item.net_amount,
                uom=q_item.uom,
                warehouse=q_item.warehouse,
                tax_code_id=q_item.tax_code_id,
                tax_rate=q_item.tax_rate,
                tax_amount=q_item.tax_amount,
                is_tax_inclusive=q_item.is_tax_inclusive,
            )
            db.add(so_item)
            totals["total_qty"] += Decimal(str(q_item.qty or 0))
            totals["total"] += Decimal(str(q_item.amount or 0))
            totals["tax_total"] += Decimal(str(q_item.tax_amount or 0))
        order.total_qty = totals["total_qty"]
        order.total = totals["total"]
        order.net_total = totals["total"]
        order.total_taxes_and_charges = totals["tax_total"]
        order.grand_total = totals["total"] + totals["tax_total"]
        order.rounded_total = round(order.grand_total or 0, 0)

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
        if payload.customer_account_id:
            order.party_id = (
                db.query(CustomerAccount.party_id)
                .filter(CustomerAccount.id == payload.customer_account_id)
                .scalar()
            )
        else:
            order.party_id = None
    if payload.quotation_id is not None:
        order.quotation_id = payload.quotation_id
    if payload.customer_name is not None:
        order.customer_name = payload.customer_name
    if payload.contact_name is not None:
        order.contact_name = payload.contact_name
    if payload.contact_email is not None:
        order.contact_email = payload.contact_email
    if payload.billing_address is not None:
        order.billing_address = payload.billing_address
    if payload.billing_address_line1 is not None:
        order.billing_address_line1 = payload.billing_address_line1
    if payload.billing_address_line2 is not None:
        order.billing_address_line2 = payload.billing_address_line2
    if payload.billing_city is not None:
        order.billing_city = payload.billing_city
    if payload.billing_state is not None:
        order.billing_state = payload.billing_state
    if payload.billing_postal_code is not None:
        order.billing_postal_code = payload.billing_postal_code
    if payload.billing_country is not None:
        order.billing_country = payload.billing_country
    if payload.billing_gps_lat is not None:
        order.billing_gps_lat = payload.billing_gps_lat
    if payload.billing_gps_lng is not None:
        order.billing_gps_lng = payload.billing_gps_lng
    if payload.shipping_address is not None:
        order.shipping_address = payload.shipping_address
    if payload.shipping_address_line1 is not None:
        order.shipping_address_line1 = payload.shipping_address_line1
    if payload.shipping_address_line2 is not None:
        order.shipping_address_line2 = payload.shipping_address_line2
    if payload.shipping_city is not None:
        order.shipping_city = payload.shipping_city
    if payload.shipping_state is not None:
        order.shipping_state = payload.shipping_state
    if payload.shipping_postal_code is not None:
        order.shipping_postal_code = payload.shipping_postal_code
    if payload.shipping_country is not None:
        order.shipping_country = payload.shipping_country
    if payload.shipping_gps_lat is not None:
        order.shipping_gps_lat = payload.shipping_gps_lat
    if payload.shipping_gps_lng is not None:
        order.shipping_gps_lng = payload.shipping_gps_lng
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
    if payload.sales_partner_id is not None:
        order.sales_partner_id = payload.sales_partner_id
    if payload.territory is not None:
        order.territory = payload.territory
    if payload.source is not None:
        order.source = payload.source
    if payload.campaign is not None:
        order.campaign = payload.campaign

    if payload.contact_phone is not None:
        phone_country = order.billing_country or order.shipping_country
        order.contact_phone = _normalize_contact_phone(payload.contact_phone, phone_country)

    if payload.billing_address is None and (
        payload.billing_address_line1 is not None
        or payload.billing_address_line2 is not None
        or payload.billing_city is not None
        or payload.billing_state is not None
        or payload.billing_postal_code is not None
        or payload.billing_country is not None
    ):
        order.billing_address = _compose_address(
            order.billing_address_line1,
            order.billing_address_line2,
            order.billing_city,
            order.billing_state,
            order.billing_postal_code,
            order.billing_country,
        )

    if payload.shipping_address is None and (
        payload.shipping_address_line1 is not None
        or payload.shipping_address_line2 is not None
        or payload.shipping_city is not None
        or payload.shipping_state is not None
        or payload.shipping_postal_code is not None
        or payload.shipping_country is not None
    ):
        order.shipping_address = _compose_address(
            order.shipping_address_line1,
            order.shipping_address_line2,
            order.shipping_city,
            order.shipping_state,
            order.shipping_postal_code,
            order.shipping_country,
        )

    if payload.items is not None:
        db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == order.id).delete()
        totals = _build_sales_order_items(db, order.id, payload.items)
        order.total_qty = totals["total_qty"]
        order.total = totals["total"]
        order.net_total = totals["total"]
        order.total_taxes_and_charges = totals["tax_total"]
        order.grand_total = totals["total"] + totals["tax_total"]
        order.rounded_total = round(order.grand_total or 0, 0)

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
    party_name = payload.customer_name or payload.party_name
    customer_name = payload.customer_name or payload.party_name
    contact_name = payload.contact_name
    contact_email = payload.contact_email
    contact_phone = payload.contact_phone
    billing_address = payload.billing_address
    shipping_address = payload.shipping_address
    billing_address_line1 = payload.billing_address_line1
    billing_address_line2 = payload.billing_address_line2
    billing_city = payload.billing_city
    billing_state = payload.billing_state
    billing_postal_code = payload.billing_postal_code
    billing_country = payload.billing_country
    billing_gps_lat = payload.billing_gps_lat
    billing_gps_lng = payload.billing_gps_lng
    shipping_address_line1 = payload.shipping_address_line1
    shipping_address_line2 = payload.shipping_address_line2
    shipping_city = payload.shipping_city
    shipping_state = payload.shipping_state
    shipping_postal_code = payload.shipping_postal_code
    shipping_country = payload.shipping_country
    shipping_gps_lat = payload.shipping_gps_lat
    shipping_gps_lng = payload.shipping_gps_lng
    party_id = None

    if payload.customer_account_id:
        account = db.query(CustomerAccount).filter(CustomerAccount.id == payload.customer_account_id).first()
        if not account:
            raise HTTPException(status_code=400, detail="Customer account not found")
        if account.party:
            party = account.party
            party_name = party_name or party.name or party.legal_name or party.trading_name
            customer_name = customer_name or party_name
            contact_name = contact_name or party_name
            contact_email = contact_email or party.primary_email
            contact_phone = contact_phone or party.primary_phone
            party_id = party.id
            if party.addresses:
                addr = _extract_party_address(party.addresses)
                if not billing_address_line1:
                    billing_address_line1 = addr.get("address_line1") or addr.get("address")
                if not billing_address_line2:
                    billing_address_line2 = addr.get("address_line2")
                if not billing_city:
                    billing_city = addr.get("city")
                if not billing_state:
                    billing_state = addr.get("state")
                if not billing_postal_code:
                    billing_postal_code = addr.get("postal_code")
                if not billing_country:
                    billing_country = addr.get("country")
                if billing_gps_lat is None:
                    billing_gps_lat = addr.get("gps_lat")
                if billing_gps_lng is None:
                    billing_gps_lng = addr.get("gps_lng")
                if not shipping_address_line1:
                    shipping_address_line1 = addr.get("address_line1") or addr.get("address")
                if not shipping_address_line2:
                    shipping_address_line2 = addr.get("address_line2")
                if not shipping_city:
                    shipping_city = addr.get("city")
                if not shipping_state:
                    shipping_state = addr.get("state")
                if not shipping_postal_code:
                    shipping_postal_code = addr.get("postal_code")
                if not shipping_country:
                    shipping_country = addr.get("country")
                if shipping_gps_lat is None:
                    shipping_gps_lat = addr.get("gps_lat")
                if shipping_gps_lng is None:
                    shipping_gps_lng = addr.get("gps_lng")

    if payload.lead_id:
        lead = db.query(ERPNextLead).filter(ERPNextLead.id == payload.lead_id).first()
        if lead:
            party_name = party_name or lead.lead_name
            customer_name = customer_name or lead.lead_name
            contact_name = contact_name or lead.lead_name
            contact_email = contact_email or lead.email_id
            contact_phone = contact_phone or lead.phone or lead.mobile_no

    if not party_name:
        raise HTTPException(status_code=400, detail="Customer or lead name is required")

    if not billing_address:
        billing_address = _compose_address(
            billing_address_line1,
            billing_address_line2,
            billing_city,
            billing_state,
            billing_postal_code,
            billing_country,
        )
    if not shipping_address:
        shipping_address = _compose_address(
            shipping_address_line1,
            shipping_address_line2,
            shipping_city,
            shipping_state,
            shipping_postal_code,
            shipping_country,
        )
    if contact_phone:
        phone_country = billing_country or shipping_country
        contact_phone = _normalize_contact_phone(contact_phone, phone_country)

    quote = Quotation(
        erpnext_id=None,
        quotation_to=payload.quotation_to,
        party_name=party_name,
        customer_name=customer_name,
        customer_account_id=payload.customer_account_id,
        lead_id=payload.lead_id,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        billing_address=billing_address,
        billing_address_line1=billing_address_line1,
        billing_address_line2=billing_address_line2,
        billing_city=billing_city,
        billing_state=billing_state,
        billing_postal_code=billing_postal_code,
        billing_country=billing_country,
        billing_gps_lat=billing_gps_lat,
        billing_gps_lng=billing_gps_lng,
        shipping_address=shipping_address,
        shipping_address_line1=shipping_address_line1,
        shipping_address_line2=shipping_address_line2,
        shipping_city=shipping_city,
        shipping_state=shipping_state,
        shipping_postal_code=shipping_postal_code,
        shipping_country=shipping_country,
        shipping_gps_lat=shipping_gps_lat,
        shipping_gps_lng=shipping_gps_lng,
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
        party_id=party_id,
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(quote)
    db.flush()
    if payload.items:
        totals = _build_quotation_items(db, quote.id, payload.items)
        quote.total_qty = totals["total_qty"]
        quote.total = totals["total"]
        quote.net_total = totals["total"]
        quote.total_taxes_and_charges = totals["tax_total"]
        quote.grand_total = totals["total"] + totals["tax_total"]
        quote.rounded_total = round(quote.grand_total or 0, 0)
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
        if payload.customer_name is None:
            quote.customer_name = payload.party_name
    if payload.customer_name is not None:
        quote.customer_name = payload.customer_name
        if payload.party_name is None:
            quote.party_name = payload.customer_name
    if payload.customer_account_id is not None:
        quote.customer_account_id = payload.customer_account_id
    if payload.lead_id is not None:
        quote.lead_id = payload.lead_id
    if payload.contact_name is not None:
        quote.contact_name = payload.contact_name
    if payload.contact_email is not None:
        quote.contact_email = payload.contact_email
    if payload.billing_address is not None:
        quote.billing_address = payload.billing_address
    if payload.billing_address_line1 is not None:
        quote.billing_address_line1 = payload.billing_address_line1
    if payload.billing_address_line2 is not None:
        quote.billing_address_line2 = payload.billing_address_line2
    if payload.billing_city is not None:
        quote.billing_city = payload.billing_city
    if payload.billing_state is not None:
        quote.billing_state = payload.billing_state
    if payload.billing_postal_code is not None:
        quote.billing_postal_code = payload.billing_postal_code
    if payload.billing_country is not None:
        quote.billing_country = payload.billing_country
    if payload.billing_gps_lat is not None:
        quote.billing_gps_lat = payload.billing_gps_lat
    if payload.billing_gps_lng is not None:
        quote.billing_gps_lng = payload.billing_gps_lng
    if payload.shipping_address is not None:
        quote.shipping_address = payload.shipping_address
    if payload.shipping_address_line1 is not None:
        quote.shipping_address_line1 = payload.shipping_address_line1
    if payload.shipping_address_line2 is not None:
        quote.shipping_address_line2 = payload.shipping_address_line2
    if payload.shipping_city is not None:
        quote.shipping_city = payload.shipping_city
    if payload.shipping_state is not None:
        quote.shipping_state = payload.shipping_state
    if payload.shipping_postal_code is not None:
        quote.shipping_postal_code = payload.shipping_postal_code
    if payload.shipping_country is not None:
        quote.shipping_country = payload.shipping_country
    if payload.shipping_gps_lat is not None:
        quote.shipping_gps_lat = payload.shipping_gps_lat
    if payload.shipping_gps_lng is not None:
        quote.shipping_gps_lng = payload.shipping_gps_lng
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
    if payload.sales_partner_id is not None:
        quote.sales_partner_id = payload.sales_partner_id
    if payload.territory is not None:
        quote.territory = payload.territory
    if payload.source is not None:
        quote.source = payload.source
    if payload.campaign is not None:
        quote.campaign = payload.campaign
    if payload.order_lost_reason is not None:
        quote.order_lost_reason = payload.order_lost_reason

    if payload.contact_phone is not None:
        phone_country = quote.billing_country or quote.shipping_country
        quote.contact_phone = _normalize_contact_phone(payload.contact_phone, phone_country)

    if payload.billing_address is None and (
        payload.billing_address_line1 is not None
        or payload.billing_address_line2 is not None
        or payload.billing_city is not None
        or payload.billing_state is not None
        or payload.billing_postal_code is not None
        or payload.billing_country is not None
    ):
        quote.billing_address = _compose_address(
            quote.billing_address_line1,
            quote.billing_address_line2,
            quote.billing_city,
            quote.billing_state,
            quote.billing_postal_code,
            quote.billing_country,
        )

    if payload.shipping_address is None and (
        payload.shipping_address_line1 is not None
        or payload.shipping_address_line2 is not None
        or payload.shipping_city is not None
        or payload.shipping_state is not None
        or payload.shipping_postal_code is not None
        or payload.shipping_country is not None
    ):
        quote.shipping_address = _compose_address(
            quote.shipping_address_line1,
            quote.shipping_address_line2,
            quote.shipping_city,
            quote.shipping_state,
            quote.shipping_postal_code,
            quote.shipping_country,
        )

    if payload.items is not None:
        db.query(QuotationItem).filter(QuotationItem.quotation_id == quote.id).delete()
        totals = _build_quotation_items(db, quote.id, payload.items)
        quote.total_qty = totals["total_qty"]
        quote.total = totals["total"]
        quote.net_total = totals["total"]
        quote.total_taxes_and_charges = totals["tax_total"]
        quote.grand_total = totals["total"] + totals["tax_total"]
        quote.rounded_total = round(quote.grand_total or 0, 0)

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
