"""
Sales (Accounts Receivable) Domain Router

Exposes AR-facing endpoints under /api/v1/sales:
- /invoices, /payments, /credit-notes (core documents)
- /aging (AR aging report)
- /analytics/* and /insights/* (finance analytics)
- /dashboard (AR KPIs)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_, or_, distinct
from typing import Dict, Any, Optional, List, Iterable
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from pydantic import BaseModel, validator
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.sales import (
    SalesOrder,
    SalesOrderStatus,
    Quotation,
    QuotationStatus,
)
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models.notification import NotificationEventType
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/sales", tags=["sales"])


def _parse_iso_utc(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse an ISO8601 string into an aware UTC datetime."""
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} date: {value}")


def _resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, raise 400."""
    if requested:
        return requested
    currencies = [row[0] for row in db.query(distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    if len(set(currencies)) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple currencies detected; please provide the 'currency' query parameter to avoid mixed-currency aggregates.",
        )
    return currencies[0]


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetimes to UTC for storage."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_invoice_status(status: Optional[str]) -> Optional[InvoiceStatus]:
    """Convert a status string to InvoiceStatus, raising 400 on invalid values."""
    if status is None:
        return None
    normalized = status.lower()
    try:
        return InvoiceStatus(normalized)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid invoice status: {status}. Allowed: {', '.join(s.value for s in InvoiceStatus)}",
        )


def _parse_payment_status(status: Optional[str]) -> Optional[PaymentStatus]:
    if status is None:
        return None
    try:
        return PaymentStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment status: {status}. Allowed: {', '.join(s.value for s in PaymentStatus)}",
        )


def _parse_payment_method(method: Optional[str]) -> Optional[PaymentMethod]:
    if method is None:
        return None
    try:
        return PaymentMethod(method.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment method: {method}. Allowed: {', '.join(m.value for m in PaymentMethod)}",
        )


def _parse_sales_order_status(status: Optional[str]) -> Optional[SalesOrderStatus]:
    if status is None:
        return None
    try:
        return SalesOrderStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sales order status: {status}. Allowed: {', '.join(s.value for s in SalesOrderStatus)}",
        )


def _parse_quotation_status(status: Optional[str]) -> Optional[QuotationStatus]:
    if status is None:
        return None
    try:
        return QuotationStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quotation status: {status}. Allowed: {', '.join(s.value for s in QuotationStatus)}",
        )


def _parse_credit_note_status(status: Optional[str]) -> Optional[CreditNoteStatus]:
    if status is None:
        return None
    try:
        return CreditNoteStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credit note status: {status}. Allowed: {', '.join(s.value for s in CreditNoteStatus)}",
        )


def _parse_customer_status(status: Optional[str]) -> Optional[CustomerStatus]:
    if status is None:
        return None
    try:
        return CustomerStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid customer status: {status}. Allowed: {', '.join(s.value for s in CustomerStatus)}",
        )


def _parse_customer_type(value: Optional[str]) -> Optional[CustomerType]:
    if value is None:
        return None
    try:
        return CustomerType(value.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid customer type: {value}. Allowed: {', '.join(s.value for s in CustomerType)}",
        )


def _parse_billing_type(value: Optional[str]) -> Optional[BillingType]:
    if value is None:
        return None
    try:
        return BillingType(value.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid billing type: {value}. Allowed: {', '.join(s.value for s in BillingType)}",
        )


def _parse_date_only(value: Optional[date]) -> Optional[date]:
    return value


def _generate_local_external_id() -> int:
    """Generate a synthetic external integer ID for locally created records."""
    return -1 * int(datetime.utcnow().timestamp() * 1000)



class InvoiceBaseRequest(BaseModel):
    invoice_number: Optional[str] = None
    customer_id: Optional[int] = None
    description: Optional[str] = None
    amount: Decimal
    tax_amount: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    currency: str = "NGN"
    status: Optional[str] = "pending"
    invoice_date: datetime
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    category: Optional[str] = None

    @validator("amount", "tax_amount", "amount_paid", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class InvoiceCreateRequest(InvoiceBaseRequest):
    """Required fields for creating an invoice."""
    pass


class InvoiceUpdateRequest(BaseModel):
    invoice_number: Optional[str] = None
    customer_id: Optional[int] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    category: Optional[str] = None

    @validator("amount", "tax_amount", "amount_paid", "total_amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class PaymentRequest(BaseModel):
    receipt_number: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: Decimal
    currency: str = "NGN"
    payment_method: Optional[str] = PaymentMethod.BANK_TRANSFER.value
    status: Optional[str] = PaymentStatus.COMPLETED.value
    payment_date: datetime
    transaction_reference: Optional[str] = None
    gateway_reference: Optional[str] = None
    notes: Optional[str] = None

    @validator("amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value))

    @validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class PaymentUpdateRequest(BaseModel):
    receipt_number: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None
    payment_date: Optional[datetime] = None
    transaction_reference: Optional[str] = None
    gateway_reference: Optional[str] = None
    notes: Optional[str] = None

    @validator("amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class SalesOrderRequest(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    order_type: Optional[str] = None
    company: Optional[str] = None
    currency: str = "NGN"
    transaction_date: Optional[date] = None
    delivery_date: Optional[date] = None
    total_qty: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    net_total: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    rounded_total: Decimal = Decimal("0")
    total_taxes_and_charges: Decimal = Decimal("0")
    per_delivered: Decimal = Decimal("0")
    per_billed: Decimal = Decimal("0")
    billing_status: Optional[str] = None
    delivery_status: Optional[str] = None
    status: Optional[str] = SalesOrderStatus.DRAFT.value
    sales_partner: Optional[str] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None

    @validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        "per_delivered",
        "per_billed",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class SalesOrderUpdateRequest(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    order_type: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    transaction_date: Optional[date] = None
    delivery_date: Optional[date] = None
    total_qty: Optional[Decimal] = None
    total: Optional[Decimal] = None
    net_total: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None
    rounded_total: Optional[Decimal] = None
    total_taxes_and_charges: Optional[Decimal] = None
    per_delivered: Optional[Decimal] = None
    per_billed: Optional[Decimal] = None
    billing_status: Optional[str] = None
    delivery_status: Optional[str] = None
    status: Optional[str] = None
    sales_partner: Optional[str] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None

    @validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        "per_delivered",
        "per_billed",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class QuotationRequest(BaseModel):
    quotation_to: Optional[str] = None
    party_name: Optional[str] = None
    customer_name: Optional[str] = None
    order_type: Optional[str] = None
    company: Optional[str] = None
    currency: str = "NGN"
    transaction_date: Optional[date] = None
    valid_till: Optional[date] = None
    total_qty: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    net_total: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    rounded_total: Decimal = Decimal("0")
    total_taxes_and_charges: Decimal = Decimal("0")
    status: Optional[str] = QuotationStatus.DRAFT.value
    sales_partner: Optional[str] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    order_lost_reason: Optional[str] = None

    @validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class QuotationUpdateRequest(BaseModel):
    quotation_to: Optional[str] = None
    party_name: Optional[str] = None
    customer_name: Optional[str] = None
    order_type: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    transaction_date: Optional[date] = None
    valid_till: Optional[date] = None
    total_qty: Optional[Decimal] = None
    total: Optional[Decimal] = None
    net_total: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None
    rounded_total: Optional[Decimal] = None
    total_taxes_and_charges: Optional[Decimal] = None
    status: Optional[str] = None
    sales_partner: Optional[str] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    order_lost_reason: Optional[str] = None

    @validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class CreditNoteRequest(BaseModel):
    credit_number: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    description: Optional[str] = None
    amount: Decimal
    currency: str = "NGN"
    status: Optional[str] = CreditNoteStatus.ISSUED.value
    issue_date: Optional[datetime] = None
    applied_date: Optional[datetime] = None

    @validator("amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value))

    @validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class CreditNoteUpdateRequest(BaseModel):
    credit_number: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    issue_date: Optional[datetime] = None
    applied_date: Optional[datetime] = None

    @validator("amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class CustomerRequest(BaseModel):
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
    customer_type: Optional[str] = CustomerType.RESIDENTIAL.value
    status: Optional[str] = CustomerStatus.ACTIVE.value
    billing_type: Optional[str] = None
    gps: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerUpdateRequest(BaseModel):
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
    customer_type: Optional[str] = None
    status: Optional[str] = None
    billing_type: Optional[str] = None
    gps: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


def _serialize_invoice(invoice: Invoice, db: Session) -> Dict[str, Any]:
    """Serialize an invoice with customer and payments for API responses."""
    payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).all()

    customer = None
    if invoice.customer_id:
        cust = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "description": invoice.description,
        "amount": float(invoice.amount),
        "tax_amount": float(invoice.tax_amount or 0),
        "total_amount": float(invoice.total_amount),
        "amount_paid": float(invoice.amount_paid or 0),
        "balance": float(invoice.total_amount - (invoice.amount_paid or 0)),
        "currency": invoice.currency,
        "status": invoice.status.value if invoice.status else None,
        "write_back_status": getattr(invoice, "write_back_status", None),
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "paid_date": invoice.paid_date.isoformat() if invoice.paid_date else None,
        "days_overdue": invoice.days_overdue,
        "category": invoice.category,
        "source": invoice.source.value if invoice.source else None,
        "external_ids": {
            "splynx_id": invoice.splynx_id,
            "erpnext_id": invoice.erpnext_id,
        },
        "customer": customer,
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
            }
            for p in payments
        ],
        "items": [
            {
                "id": it.id,
                "item_code": it.item_code,
                "item_name": it.item_name,
                "description": it.description,
                "qty": float(it.qty or 0),
                "stock_qty": float(it.stock_qty or 0),
                "uom": it.uom,
                "stock_uom": it.stock_uom,
                "rate": float(it.rate or 0),
                "price_list_rate": float(it.price_list_rate or 0),
                "discount_percentage": float(it.discount_percentage or 0),
                "discount_amount": float(it.discount_amount or 0),
                "amount": float(it.amount or 0),
                "net_amount": float(it.net_amount or 0),
                "warehouse": it.warehouse,
                "income_account": it.income_account,
                "expense_account": it.expense_account,
                "cost_center": it.cost_center,
                "sales_order": it.sales_order,
                "delivery_note": it.delivery_note,
                "idx": it.idx,
            }
            for it in items
        ],
    }


def _serialize_payment(payment: Payment) -> Dict[str, Any]:
    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "customer_id": payment.customer_id,
        "invoice_id": payment.invoice_id,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "payment_method": payment.payment_method.value if payment.payment_method else None,
        "status": payment.status.value if payment.status else None,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "transaction_reference": payment.transaction_reference,
        "gateway_reference": payment.gateway_reference,
        "notes": payment.notes,
        "source": payment.source.value if payment.source else None,
        "write_back_status": getattr(payment, "write_back_status", None),
    }


def _serialize_sales_order(order: SalesOrder) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if hasattr(order, "items"):
        items = [
            {
                "id": it.id,
                "item_code": it.item_code,
                "item_name": it.item_name,
                "description": it.description,
                "qty": float(it.qty or 0),
                "stock_qty": float(it.stock_qty or 0),
                "uom": it.uom,
                "stock_uom": it.stock_uom,
                "conversion_factor": float(it.conversion_factor or 0),
                "rate": float(it.rate or 0),
                "price_list_rate": float(it.price_list_rate or 0),
                "discount_percentage": float(it.discount_percentage or 0),
                "discount_amount": float(it.discount_amount or 0),
                "amount": float(it.amount or 0),
                "net_amount": float(it.net_amount or 0),
                "delivered_qty": float(it.delivered_qty or 0),
                "billed_amt": float(it.billed_amt or 0),
                "warehouse": it.warehouse,
                "delivery_date": it.delivery_date.isoformat() if it.delivery_date else None,
                "idx": it.idx,
            }
            for it in order.items
        ]

    return {
        "id": order.id,
        "erpnext_id": order.erpnext_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "order_type": order.order_type,
        "company": order.company,
        "currency": order.currency,
        "transaction_date": order.transaction_date.isoformat() if order.transaction_date else None,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "total_qty": float(order.total_qty or 0),
        "total": float(order.total or 0),
        "net_total": float(order.net_total or 0),
        "grand_total": float(order.grand_total or 0),
        "rounded_total": float(order.rounded_total or 0),
        "total_taxes_and_charges": float(order.total_taxes_and_charges or 0),
        "per_delivered": float(order.per_delivered or 0),
        "per_billed": float(order.per_billed or 0),
        "billing_status": order.billing_status,
        "delivery_status": order.delivery_status,
        "status": order.status.value if order.status else None,
        "sales_partner": order.sales_partner,
        "territory": order.territory,
        "source": order.source,
        "campaign": order.campaign,
        "write_back_status": getattr(order, "write_back_status", None),
        "items": items,
    }


def _serialize_quotation(quote: Quotation) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if hasattr(quote, "items"):
        items = [
            {
                "id": it.id,
                "item_code": it.item_code,
                "item_name": it.item_name,
                "description": it.description,
                "qty": float(it.qty or 0),
                "stock_qty": float(it.stock_qty or 0),
                "uom": it.uom,
                "stock_uom": it.stock_uom,
                "conversion_factor": float(it.conversion_factor or 0),
                "rate": float(it.rate or 0),
                "price_list_rate": float(it.price_list_rate or 0),
                "discount_percentage": float(it.discount_percentage or 0),
                "discount_amount": float(it.discount_amount or 0),
                "amount": float(it.amount or 0),
                "net_amount": float(it.net_amount or 0),
                "idx": it.idx,
            }
            for it in quote.items
        ]

    return {
        "id": quote.id,
        "erpnext_id": quote.erpnext_id,
        "quotation_to": quote.quotation_to,
        "party_name": quote.party_name,
        "customer_name": quote.customer_name,
        "order_type": quote.order_type,
        "company": quote.company,
        "currency": quote.currency,
        "transaction_date": quote.transaction_date.isoformat() if quote.transaction_date else None,
        "valid_till": quote.valid_till.isoformat() if quote.valid_till else None,
        "total_qty": float(quote.total_qty or 0),
        "total": float(quote.total or 0),
        "net_total": float(quote.net_total or 0),
        "grand_total": float(quote.grand_total or 0),
        "rounded_total": float(quote.rounded_total or 0),
        "total_taxes_and_charges": float(quote.total_taxes_and_charges or 0),
        "status": quote.status.value if quote.status else None,
        "sales_partner": quote.sales_partner,
        "territory": quote.territory,
        "source": quote.source,
        "campaign": quote.campaign,
        "order_lost_reason": quote.order_lost_reason,
        "write_back_status": getattr(quote, "write_back_status", None),
        "items": items,
    }


def _serialize_credit_note(note: CreditNote) -> Dict[str, Any]:
    return {
        "id": note.id,
        "splynx_id": note.splynx_id,
        "credit_number": note.credit_number,
        "customer_id": note.customer_id,
        "invoice_id": note.invoice_id,
        "description": note.description,
        "amount": float(note.amount),
        "currency": note.currency,
        "status": note.status.value if note.status else None,
        "issue_date": note.issue_date.isoformat() if note.issue_date else None,
        "applied_date": note.applied_date.isoformat() if note.applied_date else None,
        "write_back_status": getattr(note, "write_back_status", None),
    }


def _serialize_customer(customer: Customer) -> Dict[str, Any]:
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
        "customer_type": customer.customer_type.value if customer.customer_type else None,
        "status": customer.status.value if customer.status else None,
        "billing_type": customer.billing_type.value if customer.billing_type else None,
        "gps": customer.gps,
        "latitude": customer.latitude,
        "longitude": customer.longitude,
        "splynx_id": customer.splynx_id,
        "erpnext_id": customer.erpnext_id,
    }


# =============================================================================
# DASHBOARD
# =============================================================================

class RevenueTrendPoint(BaseModel):
    year: int
    month: int
    period: str
    revenue: float
    payment_count: int

@router.get(
    "/dashboard",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Finance dashboard (single-currency)",
    description="Returns revenue KPIs (MRR/ARR), collections, outstanding, DSO, and invoice status counts. "
                "Requires a single currency; if data contains multiple currencies, pass ?currency=.",
)
@cached("finance-dashboard", ttl=CACHE_TTL["short"])
async def get_finance_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code (required if multiple currencies exist)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Finance dashboard with key revenue and collection metrics.
    Enforces a single currency to avoid mixing figures.
    """
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency)
    # MRR calculation from active subscriptions
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    mrr_query = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if currency:
        mrr_query = mrr_query.filter(Subscription.currency == currency)

    mrr = float(mrr_query.scalar() or 0)
    arr = mrr * 12

    active_subscriptions = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *( [Subscription.currency == currency] if currency else [] ),
    ).scalar() or 0

    # Invoice summary
    invoice_summary_query = db.query(
        Invoice.status,
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount).label("total")
    )
    if currency:
        invoice_summary_query = invoice_summary_query.filter(Invoice.currency == currency)
    invoice_summary = invoice_summary_query.group_by(Invoice.status).all()

    invoice_by_status = {
        row.status.value: {"count": row.count, "total": float(row.total or 0)}
        for row in invoice_summary
    }

    # Outstanding balance
    outstanding_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    overdue_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    if currency:
        outstanding_query = outstanding_query.filter(Invoice.currency == currency)
        overdue_query = overdue_query.filter(Invoice.currency == currency)

    outstanding = outstanding_query.scalar() or 0
    overdue_amount = overdue_query.scalar() or 0

    # Collections last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    collections_30d_query = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= thirty_days_ago
    )
    invoiced_30d_query = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= thirty_days_ago
    )
    if currency:
        collections_30d_query = collections_30d_query.filter(Payment.currency == currency)
        invoiced_30d_query = invoiced_30d_query.filter(Invoice.currency == currency)

    collections_30d = collections_30d_query.scalar() or 0
    invoiced_30d = invoiced_30d_query.scalar() or 0

    collection_rate = round(float(collections_30d) / float(invoiced_30d) * 100, 1) if invoiced_30d else 0

    # DSO (Days Sales Outstanding) - simplified calculation
    avg_daily_revenue = float(collections_30d) / 30 if collections_30d else 0
    dso = round(float(outstanding) / avg_daily_revenue, 1) if avg_daily_revenue > 0 else 0

    return {
        "revenue": {
            "mrr": mrr,
            "arr": arr,
            "active_subscriptions": active_subscriptions,
        },
        "collections": {
            "last_30_days": float(collections_30d),
            "invoiced_30_days": float(invoiced_30d),
            "collection_rate": collection_rate,
        },
        "outstanding": {
            "total": float(outstanding),
            "overdue": float(overdue_amount),
        },
        "metrics": {
            "dso": dso,
        },
        "invoices_by_status": invoice_by_status,
    }


# =============================================================================
# DATA ENDPOINTS
# =============================================================================

@router.get("/invoices", dependencies=[Depends(Require("explorer:read"))])
async def list_invoices(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    overdue_only: bool = False,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="invoice_date,due_date,total_amount,amount_paid,customer_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List invoices with filtering, search, sort, and pagination (single-currency only)."""
    query = db.query(Invoice).filter(Invoice.is_deleted == False)

    if status:
        try:
            status_enum = InvoiceStatus(status)
            query = query.filter(Invoice.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Invoice.invoice_date >= start_dt)

    if end_dt:
        query = query.filter(Invoice.invoice_date <= end_dt)

    if min_amount:
        query = query.filter(Invoice.total_amount >= min_amount)

    if max_amount:
        query = query.filter(Invoice.total_amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    if currency:
        query = query.filter(Invoice.currency == currency)

    if overdue_only:
        query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Invoice.invoice_number.ilike(like), Invoice.description.ilike(like)))

    sort_map = {
        "invoice_date": Invoice.invoice_date,
        "due_date": Invoice.due_date,
        "total_amount": Invoice.total_amount,
        "amount_paid": Invoice.amount_paid,
        "customer_id": Invoice.customer_id,
        "status": Invoice.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "invoice_date")
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    invoice_rows = (
        query.outerjoin(Customer, Invoice.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, Invoice.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "customer_name": customer_name,
                "total_amount": float(inv.total_amount),
                "amount_paid": float(inv.amount_paid or 0),
                "balance": float(inv.total_amount - (inv.amount_paid or 0)),
                "currency": inv.currency,
                "status": inv.status.value if inv.status else None,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
                "source": inv.source.value if inv.source else None,
            }
            for inv, customer_name in invoice_rows
        ],
    }


@router.get("/invoices/{invoice_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed invoice information."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _serialize_invoice(invoice, db)


@router.post("/invoices", dependencies=[Depends(Require("sales:write"))])
async def create_invoice(
    payload: InvoiceCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new invoice stored locally (not pushed upstream)."""
    if payload.customer_id:
        customer_exists = db.query(Customer.id).filter(Customer.id == payload.customer_id).first()
        if not customer_exists:
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")

    status = _parse_invoice_status(payload.status) or InvoiceStatus.PENDING
    total_amount = payload.amount + payload.tax_amount
    balance = total_amount - (payload.amount_paid or Decimal("0"))

    invoice = Invoice(
        source=InvoiceSource.ERPNEXT,
        customer_id=payload.customer_id,
        invoice_number=payload.invoice_number,
        description=payload.description,
        amount=payload.amount,
        tax_amount=payload.tax_amount,
        total_amount=total_amount,
        amount_paid=payload.amount_paid,
        balance=balance,
        currency=payload.currency,
        status=status,
        invoice_date=_ensure_utc(payload.invoice_date),
        due_date=_ensure_utc(payload.due_date),
        paid_date=_ensure_utc(payload.paid_date),
        category=payload.category,
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return _serialize_invoice(invoice, db)


@router.patch("/invoices/{invoice_id}", dependencies=[Depends(Require("sales:write"))])
async def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing invoice stored locally."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if payload.customer_id is not None:
        customer_exists = db.query(Customer.id).filter(Customer.id == payload.customer_id).first()
        if not customer_exists:
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        invoice.customer_id = payload.customer_id

    if payload.invoice_number is not None:
        invoice.invoice_number = payload.invoice_number
    if payload.description is not None:
        invoice.description = payload.description
    if payload.amount is not None:
        invoice.amount = payload.amount
    if payload.tax_amount is not None:
        invoice.tax_amount = payload.tax_amount
    if payload.amount_paid is not None:
        invoice.amount_paid = payload.amount_paid
    if payload.currency is not None:
        invoice.currency = payload.currency
    if payload.status is not None:
        invoice.status = _parse_invoice_status(payload.status) or invoice.status
    if payload.invoice_date is not None:
        invoice.invoice_date = _ensure_utc(payload.invoice_date)
    if payload.due_date is not None:
        invoice.due_date = _ensure_utc(payload.due_date)
    if payload.paid_date is not None:
        invoice.paid_date = _ensure_utc(payload.paid_date)
    if payload.category is not None:
        invoice.category = payload.category

    # Recalculate totals if any amount fields changed
    if any(field is not None for field in [payload.amount, payload.tax_amount, payload.total_amount]):
        invoice.total_amount = payload.total_amount if payload.total_amount is not None else invoice.amount + (invoice.tax_amount or Decimal("0"))

    invoice.balance = invoice.total_amount - (invoice.amount_paid or Decimal("0"))

    db.commit()
    db.refresh(invoice)

    return _serialize_invoice(invoice, db)


@router.post("/payments", dependencies=[Depends(Require("sales:write"))])
async def create_payment(
    payload: PaymentRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a payment in the local database."""
    if payload.customer_id:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
    if payload.invoice_id:
        if not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")

    payment = Payment(
        source=PaymentSource.ERPNEXT,
        receipt_number=payload.receipt_number,
        customer_id=payload.customer_id,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=_parse_payment_method(payload.payment_method) or PaymentMethod.BANK_TRANSFER,
        status=_parse_payment_status(payload.status) or PaymentStatus.COMPLETED,
        payment_date=_ensure_utc(payload.payment_date),
        transaction_reference=payload.transaction_reference,
        gateway_reference=payload.gateway_reference,
        notes=payload.notes,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    # Emit payment received notification
    if payment.status == PaymentStatus.COMPLETED:
        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first() if payment.customer_id else None
        invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first() if payment.invoice_id else None
        NotificationService(db).emit_event(
            event_type=NotificationEventType.PAYMENT_RECEIVED,
            payload={
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "amount": float(payment.amount) if payment.amount else 0,
                "currency": payment.currency,
                "customer_id": payment.customer_id,
                "customer_name": customer.name if customer else None,
                "invoice_id": payment.invoice_id,
                "invoice_number": invoice.invoice_number if invoice else None,
            },
            entity_type="payment",
            entity_id=payment.id,
        )

    return _serialize_payment(payment)


@router.patch("/payments/{payment_id}", dependencies=[Depends(Require("sales:write"))])
async def update_payment(
    payment_id: int,
    payload: PaymentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payment in the local database."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payload.customer_id is not None:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        payment.customer_id = payload.customer_id
    if payload.invoice_id is not None:
        if payload.invoice_id and not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")
        payment.invoice_id = payload.invoice_id
    if payload.receipt_number is not None:
        payment.receipt_number = payload.receipt_number
    if payload.amount is not None:
        payment.amount = payload.amount
    if payload.currency is not None:
        payment.currency = payload.currency
    if payload.payment_method is not None:
        payment.payment_method = _parse_payment_method(payload.payment_method) or payment.payment_method
    if payload.status is not None:
        payment.status = _parse_payment_status(payload.status) or payment.status
    if payload.payment_date is not None:
        payment.payment_date = _ensure_utc(payload.payment_date)
    if payload.transaction_reference is not None:
        payment.transaction_reference = payload.transaction_reference
    if payload.gateway_reference is not None:
        payment.gateway_reference = payload.gateway_reference
    if payload.notes is not None:
        payment.notes = payload.notes

    db.commit()
    db.refresh(payment)
    return _serialize_payment(payment)


@router.post("/orders", dependencies=[Depends(Require("sales:write"))])
async def create_sales_order(
    payload: SalesOrderRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a sales order locally."""
    if payload.customer_id:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")

    order = SalesOrder(
        erpnext_id=None,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        order_type=payload.order_type,
        company=payload.company,
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


@router.delete("/quotations/{quotation_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_quotation(
    quotation_id: int,
    soft: bool = Query(default=True, description="Soft delete by marking is_deleted"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete or soft-delete a quotation."""
    quote = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    if soft or quote.erpnext_id:
        quote.is_deleted = True
        quote.deleted_at = datetime.utcnow()
        quote.deleted_by_id = principal.id
        quote.write_back_status = "pending"
        db.commit()
        return {"status": "disabled", "quotation_id": quotation_id}

    db.delete(quote)
    db.commit()
    return {"status": "deleted", "quotation_id": quotation_id}


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

    if payload.customer_id is not None:
        if payload.customer_id and not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        order.customer_id = payload.customer_id
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
        company=payload.company,
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

    quote.updated_by_id = principal.id
    quote.write_back_status = "pending"
    db.commit()
    db.refresh(quote)
    return _serialize_quotation(quote)


@router.post("/credit-notes", dependencies=[Depends(Require("sales:write"))])
async def create_credit_note(
    payload: CreditNoteRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a credit note locally."""
    if payload.customer_id:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
    if payload.invoice_id:
        if not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")

    note = CreditNote(
        splynx_id=_generate_local_external_id(),
        credit_number=payload.credit_number,
        customer_id=payload.customer_id,
        invoice_id=payload.invoice_id,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        status=_parse_credit_note_status(payload.status) or CreditNoteStatus.ISSUED,
        issue_date=_ensure_utc(payload.issue_date),
        applied_date=_ensure_utc(payload.applied_date),
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize_credit_note(note)


@router.patch("/credit-notes/{credit_note_id}", dependencies=[Depends(Require("sales:write"))])
async def update_credit_note(
    credit_note_id: int,
    payload: CreditNoteUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a credit note locally."""
    note = db.query(CreditNote).filter(CreditNote.id == credit_note_id, CreditNote.is_deleted == False).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if payload.customer_id is not None:
        if payload.customer_id and not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        note.customer_id = payload.customer_id
    if payload.invoice_id is not None:
        if payload.invoice_id and not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")
        note.invoice_id = payload.invoice_id
    if payload.credit_number is not None:
        note.credit_number = payload.credit_number
    if payload.description is not None:
        note.description = payload.description
    if payload.amount is not None:
        note.amount = payload.amount
    if payload.currency is not None:
        note.currency = payload.currency
    if payload.status is not None:
        note.status = _parse_credit_note_status(payload.status) or note.status
    if payload.issue_date is not None:
        note.issue_date = _ensure_utc(payload.issue_date)
    if payload.applied_date is not None:
        note.applied_date = _ensure_utc(payload.applied_date)

    note.updated_by_id = principal.id
    note.write_back_status = "pending"
    db.commit()
    db.refresh(note)
    return _serialize_credit_note(note)


@router.delete("/credit-notes/{credit_note_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_credit_note(
    credit_note_id: int,
    soft: bool = Query(default=True, description="Soft delete by marking is_deleted"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete or soft-delete a credit note."""
    note = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if soft or note.erpnext_id or note.splynx_id:
        note.is_deleted = True
        note.deleted_at = datetime.utcnow()
        note.deleted_by_id = principal.id
        note.write_back_status = "pending"
        db.commit()
        return {"status": "disabled", "credit_note_id": credit_note_id}

    db.delete(note)
    db.commit()
    return {"status": "deleted", "credit_note_id": credit_note_id}


@router.post("/customers", dependencies=[Depends(Require("sales:write"))])
async def create_sales_customer(
    payload: CustomerRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a customer locally (sales context)."""
    customer = Customer(
        name=payload.name,
        email=payload.email,
        billing_email=payload.billing_email,
        phone=payload.phone,
        phone_secondary=payload.phone_secondary,
        address=payload.address,
        address_2=payload.address_2,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        country=payload.country,
        customer_type=_parse_customer_type(payload.customer_type) or CustomerType.RESIDENTIAL,
        status=_parse_customer_status(payload.status) or CustomerStatus.ACTIVE,
        billing_type=_parse_billing_type(payload.billing_type) if payload.billing_type else None,
        gps=payload.gps,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _serialize_customer(customer)


@router.patch("/customers/{customer_id}", dependencies=[Depends(Require("sales:write"))])
async def update_sales_customer(
    customer_id: int,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a customer locally (sales context)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "customer_type" and value is not None:
            customer.customer_type = _parse_customer_type(value) or customer.customer_type
        elif field == "status" and value is not None:
            customer.status = _parse_customer_status(value) or customer.status
        elif field == "billing_type" and value is not None:
            customer.billing_type = _parse_billing_type(value)
        else:
            setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return _serialize_customer(customer)


@router.get("/payments", dependencies=[Depends(Require("explorer:read"))])
async def list_payments(
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="payment_date,amount,customer_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payments with filtering, search, sort, and pagination (single-currency only)."""
    query = db.query(Payment).filter(Payment.is_deleted == False)

    if status:
        try:
            status_enum = PaymentStatus(status)
            query = query.filter(Payment.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if payment_method:
        try:
            method_enum = PaymentMethod(payment_method)
            query = query.filter(Payment.payment_method == method_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment_method: {payment_method}")

    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)

    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Payment.payment_date >= start_dt)

    if end_dt:
        query = query.filter(Payment.payment_date <= end_dt)

    if min_amount:
        query = query.filter(Payment.amount >= min_amount)

    if max_amount:
        query = query.filter(Payment.amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    if currency:
        query = query.filter(Payment.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Payment.receipt_number.ilike(like),
                Payment.transaction_reference.ilike(like),
                Payment.gateway_reference.ilike(like),
                Payment.notes.ilike(like),
            )
        )

    sort_map = {
        "payment_date": Payment.payment_date,
        "amount": Payment.amount,
        "customer_id": Payment.customer_id,
        "invoice_id": Payment.invoice_id,
        "status": Payment.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "payment_date")
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    payment_rows = (
        query.outerjoin(Customer, Payment.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, Payment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "customer_id": p.customer_id,
                "customer_name": customer_name,
                "invoice_id": p.invoice_id,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "transaction_reference": p.transaction_reference,
                "gateway_reference": p.gateway_reference,
                "notes": p.notes,
                "source": p.source.value if p.source else None,
                "write_back_status": getattr(p, "write_back_status", None),
            }
            for p, customer_name in payment_rows
        ],
    }


@router.get("/payments/{payment_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed payment information."""
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    customer = None
    if payment.customer_id:
        cust = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    invoice = None
    if payment.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if inv:
            invoice = {"id": inv.id, "invoice_number": inv.invoice_number, "total_amount": float(inv.total_amount)}

    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "payment_method": payment.payment_method.value if payment.payment_method else None,
        "status": payment.status.value if payment.status else None,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "transaction_reference": payment.transaction_reference,
        "gateway_reference": payment.gateway_reference,
        "notes": payment.notes,
        "source": payment.source.value if payment.source else None,
        "external_ids": {
            "splynx_id": payment.splynx_id,
            "erpnext_id": payment.erpnext_id,
        },
        "customer": customer,
        "invoice": invoice,
        "references": [
            {
                "id": ref.id,
                "reference_doctype": ref.reference_doctype,
                "reference_name": ref.reference_name,
                "total_amount": float(ref.total_amount or 0),
                "outstanding_amount": float(ref.outstanding_amount or 0),
                "allocated_amount": float(ref.allocated_amount or 0),
                "exchange_rate": float(ref.exchange_rate or 1),
                "exchange_gain_loss": float(ref.exchange_gain_loss or 0),
                "due_date": ref.due_date.isoformat() if ref.due_date else None,
                "idx": ref.idx,
            }
            for ref in payment.references
        ],
    }


@router.get("/credit-notes", dependencies=[Depends(Require("explorer:read"))])
async def list_credit_notes(
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="issue_date,amount,customer_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List credit notes with filtering, search, sort, and pagination (single-currency only)."""
    currency = _resolve_currency_or_raise(db, CreditNote.currency, currency)
    query = db.query(CreditNote).filter(CreditNote.is_deleted == False)

    if customer_id:
        query = query.filter(CreditNote.customer_id == customer_id)

    if invoice_id:
        query = query.filter(CreditNote.invoice_id == invoice_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(CreditNote.issue_date >= start_dt)

    if end_dt:
        query = query.filter(CreditNote.issue_date <= end_dt)

    if currency:
        query = query.filter(CreditNote.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(CreditNote.credit_number.ilike(like), CreditNote.description.ilike(like)))

    sort_map = {
        "issue_date": CreditNote.issue_date,
        "amount": CreditNote.amount,
        "customer_id": CreditNote.customer_id,
        "invoice_id": CreditNote.invoice_id,
        "status": CreditNote.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map.get(sort_by or "issue_date")
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    credit_note_rows = (
        query.outerjoin(Customer, CreditNote.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, CreditNote.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": cn.id,
                "credit_note_number": cn.credit_number,
                "customer_id": cn.customer_id,
                "customer_name": customer_name,
                "invoice_id": cn.invoice_id,
                "amount": float(cn.amount) if cn.amount else 0,
                "currency": cn.currency,
                "date": cn.issue_date.isoformat() if cn.issue_date else None,
                "reason": cn.description,
                "status": cn.status.value if cn.status else None,
                "source": "splynx",
                "external_ids": {
                    "splynx_id": cn.splynx_id,
                },
            }
            for cn, customer_name in credit_note_rows
        ],
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get(
    "/analytics/revenue-trend",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Revenue trend (month/week) - single currency",
)
async def get_revenue_trend(
    months: int = Query(default=12, le=36, description="Fallback window if start/end not provided"),
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    interval: str = Query(default="month", description="Aggregation interval: month or week"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue trend from completed payments (single-currency)."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    end_dt = _parse_iso_utc(end_date, "end_date") or datetime.now(timezone.utc)
    start_dt = _parse_iso_utc(start_date, "start_date") or end_dt - timedelta(days=months * 30)

    if interval not in ("month", "week"):
        raise HTTPException(status_code=400, detail="interval must be 'month' or 'week'")

    trunc = func.date_trunc(interval, Payment.payment_date)
    query = db.query(
        func.extract("year", trunc).label("year"),
        func.extract("month", trunc).label("month"),
        func.to_char(trunc, "YYYY-MM" if interval == "month" else "IYYY-IW").label("period"),
        func.sum(Payment.amount).label("revenue"),
        func.count(Payment.id).label("payment_count"),
        func.min(Payment.payment_date).label("period_start"),
        func.max(Payment.payment_date).label("period_end"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        query = query.filter(Payment.currency == currency)

    revenue = (
        query
        .group_by(trunc)
        .order_by(trunc)
        .all()
    )

    return {
        "meta": {
            "interval": interval,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "currency": currency,
        },
        "data": [
            {
                "year": int(r.year),
                "month": int(r.month) if r.month is not None else None,
                "period": r.period,
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
                "revenue": float(r.revenue or 0),
                "payment_count": int(r.payment_count or 0),
            }
            for r in revenue
        ],
    }


@router.get("/analytics/collections", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-collections", ttl=CACHE_TTL["medium"])
async def get_collections_analytics(
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get collection analytics including payment methods, timing, and daily totals (single-currency)."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    end_dt = _parse_iso_utc(end_date, "end_date") or datetime.now(timezone.utc)
    start_dt = _parse_iso_utc(start_date, "start_date") or end_dt - timedelta(days=30)

    # Payment method distribution
    by_method = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        by_method = by_method.filter(Payment.currency == currency)

    by_method = by_method.group_by(Payment.payment_method).all()

    # Payment timing analysis (early/on-time/late)
    days_diff = func.date_part("day", Invoice.due_date - Payment.payment_date)

    timing_query = db.query(
        func.sum(case(
            (and_(Payment.payment_date <= Invoice.due_date, days_diff > 3), 1),
            else_=0
        )).label("early"),
        func.sum(case(
            (and_(Payment.payment_date <= Invoice.due_date, days_diff <= 3), 1),
            else_=0
        )).label("on_time"),
        func.sum(case(
            (Payment.payment_date > Invoice.due_date, 1),
            else_=0
        )).label("late"),
        func.count(Payment.id).label("total"),
    ).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Invoice.due_date.isnot(None),
        Payment.payment_date.isnot(None),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )
    if currency:
        timing_query = timing_query.filter(Payment.currency == currency, Invoice.currency == currency)

    timing = timing_query.one_or_none()

    # Daily totals for charting
    daily = db.query(
        func.date(Payment.payment_date).label("date"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )
    if currency:
        daily = daily.filter(Payment.currency == currency)
    daily_totals = [
        {"date": row.date.isoformat(), "total": float(row.total or 0)}
        for row in daily.group_by(func.date(Payment.payment_date)).order_by(func.date(Payment.payment_date)).all()
    ]

    return {
        "meta": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "currency": currency,
        },
        "by_method": [
            {
                "method": row.payment_method.value if row.payment_method else "unknown",
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in by_method
        ],
        "payment_timing": {
            "early": int(timing.early or 0) if timing else 0,
            "on_time": int(timing.on_time or 0) if timing else 0,
            "late": int(timing.late or 0) if timing else 0,
            "total": int(timing.total or 0) if timing else 0,
        },
        "daily_totals": daily_totals,
    }


@router.get("/aging", dependencies=[Depends(Require("analytics:read"))])
@router.get("/analytics/aging", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-aging", ttl=CACHE_TTL["short"])
async def get_invoice_aging(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoice aging analysis by bucket."""
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    days_overdue = func.date_part("day", func.current_date() - Invoice.due_date)

    aging_bucket = case(
        (Invoice.due_date >= func.current_date(), 'current'),
        (days_overdue <= 30, '1-30 days'),
        (days_overdue <= 60, '31-60 days'),
        (days_overdue <= 90, '61-90 days'),
        else_='over 90 days'
    )

    aging_query = db.query(
        aging_bucket.label("bucket"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.due_date.isnot(None),
    )

    if currency:
        aging_query = aging_query.filter(Invoice.currency == currency)

    aging = aging_query.group_by(aging_bucket).all()

    bucket_order = ["current", "1-30 days", "31-60 days", "61-90 days", "over 90 days"]
    aging_map = {row.bucket: {"count": row.count, "outstanding": float(row.outstanding or 0)} for row in aging}

    buckets = [
        {
            "bucket": b,
            "count": aging_map.get(b, {}).get("count", 0),
            "outstanding": aging_map.get(b, {}).get("outstanding", 0),
        }
        for b in bucket_order
    ]

    total_outstanding = sum(b["outstanding"] for b in buckets)
    at_risk = sum(b["outstanding"] for b in buckets if b["bucket"] != "current")

    total_invoices = sum(b["count"] for b in buckets)

    return {
        "buckets": buckets,
        "summary": {
            "total_outstanding": total_outstanding,
            "at_risk": at_risk,
            "at_risk_percent": round(at_risk / total_outstanding * 100, 1) if total_outstanding > 0 else 0,
            "total_invoices": total_invoices,
        },
    }


@router.get("/analytics/by-currency", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_by_currency(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue breakdown by currency."""
    # MRR by currency
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    by_currency = db.query(
        Subscription.currency,
        func.sum(mrr_case).label("mrr"),
        func.count(Subscription.id).label("subscription_count"),
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Subscription.currency).all()

    # Outstanding by currency
    outstanding = db.query(
        Invoice.currency,
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    ).group_by(Invoice.currency).all()

    outstanding_map = {row.currency: float(row.outstanding or 0) for row in outstanding}

    return {
        "by_currency": [
            {
                "currency": row.currency,
                "mrr": float(row.mrr or 0),
                "arr": float(row.mrr or 0) * 12,
                "subscription_count": row.subscription_count,
                "outstanding": outstanding_map.get(row.currency, 0),
            }
            for row in by_currency
        ],
    }


# =============================================================================
# INSIGHTS
# =============================================================================

@router.get("/insights/payment-behavior", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-payment-behavior", ttl=CACHE_TTL["medium"])
async def get_payment_behavior_insights(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze customer payment behavior patterns."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    # Get customers with payment history
    customer_payments = db.query(
        Payment.customer_id,
        func.count(Payment.id).label("total_payments"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.customer_id.isnot(None),
    )
    if currency:
        customer_payments = customer_payments.filter(Payment.currency == currency)
    customer_payments = customer_payments.group_by(Payment.customer_id).subquery()

    # Count customers by payment frequency
    customers_with_payments = db.query(func.count(customer_payments.c.customer_id)).scalar() or 0

    # Customers with overdue invoices
    customers_overdue_query = db.query(func.count(distinct(Invoice.customer_id))).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    if currency:
        customers_overdue_query = customers_overdue_query.filter(Invoice.currency == currency)
    customers_overdue = customers_overdue_query.scalar() or 0

    # Average payment delay for late payments
    late_payments_query = db.query(
        func.avg(func.date_part("day", Payment.payment_date - Invoice.due_date)).label("avg_delay")
    ).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date > Invoice.due_date,
    )
    if currency:
        late_payments_query = late_payments_query.filter(Payment.currency == currency, Invoice.currency == currency)
    late_payments = late_payments_query.scalar() or 0

    # Late payments percentage
    late_count_query = db.query(func.count(Payment.id)).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date > Invoice.due_date,
    )
    total_payments_query = db.query(func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date.isnot(None),
    )
    if currency:
        late_count_query = late_count_query.filter(Payment.currency == currency, Invoice.currency == currency)
        total_payments_query = total_payments_query.filter(Payment.currency == currency)

    late_count = late_count_query.scalar() or 0
    total_payments = total_payments_query.scalar() or 0
    late_percent = round(late_count / total_payments * 100, 1) if total_payments else 0

    return {
        "summary": {
            "customers_with_payments": customers_with_payments,
            "customers_with_overdue": customers_overdue,
            "avg_late_payment_delay_days": round(float(late_payments), 1),
            "late_payments_percent": late_percent,
        },
        "recommendations": [
            {
                "priority": "high" if customers_overdue > customers_with_payments * 0.1 else "medium",
                "issue": f"{customers_overdue} customers have overdue invoices",
                "action": "Send payment reminders and review collection process",
            }
        ] if customers_overdue > 0 else [],
    }


@router.get("/insights/forecasts", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-forecasts", ttl=CACHE_TTL["medium"])
async def get_revenue_forecasts(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simple revenue projections based on current MRR and trends."""
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency)
    # Current MRR
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    mrr_query = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if currency:
        mrr_query = mrr_query.filter(Subscription.currency == currency)
    current_mrr = mrr_query.scalar() or 0

    # Calculate growth (compare to 30 days ago - simplified)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    new_subs_query = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.start_date >= thirty_days_ago,
    )
    if currency:
        new_subs_query = new_subs_query.filter(Subscription.currency == currency)
    new_subs_30d = new_subs_query.scalar() or 0

    # Simple projection: assume current MRR continues
    mrr_float = float(current_mrr)

    return {
        "currency": currency,
        "current": {
            "mrr": mrr_float,
            "arr": mrr_float * 12,
        },
        "activity_30d": {
            "new_subscriptions": new_subs_30d,
        },
        "projections": {
            "month_1": mrr_float,
            "month_2": mrr_float,
            "month_3": mrr_float,
            "quarter_total": mrr_float * 3,
        },
        "assumptions": [
            "Current MRR remains stable (no churn/upgrade modeled)",
            "Same currency across all subscriptions",
        ],
        "notes": "Projections assume current MRR remains stable. Adjust for expected growth/churn.",
    }
