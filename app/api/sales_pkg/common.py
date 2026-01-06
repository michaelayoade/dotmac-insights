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
from typing import Dict, Any, Optional, List, Iterable, cast
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.party import CustomerAccount, PartyRole
from app.models.sales import (
    SalesOrder,
    SalesOrderStatus,
    Quotation,
    QuotationStatus,
    CustomerGroup,
    Territory,
    SalesPerson,
)
from app.models.document_lines import InvoiceLine
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models.notification import NotificationEventType
from app.services.notification_service import NotificationService
from app.utils.company_context import ensure_company, get_company_context

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
    return cast(str, currencies[0])


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


def _parse_customer_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    normalized = status.lower()
    allowed = {"active", "suspended", "cancelled", "pending"}
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid customer status: {status}. Allowed: {', '.join(sorted(allowed))}",
        )
    return normalized


def _parse_customer_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.lower()


def _parse_billing_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.lower()


def _parse_date_only(value: Optional[date]) -> Optional[date]:
    return value


def _generate_local_external_id() -> int:
    """Generate a synthetic external integer ID for locally created records."""
    return -1 * int(datetime.now(timezone.utc).timestamp() * 1000)



class InvoiceBaseRequest(BaseModel):
    invoice_number: Optional[str] = None
    customer_account_id: Optional[int] = None
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

    @field_validator("amount", "tax_amount", "amount_paid", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @field_validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class InvoiceCreateRequest(InvoiceBaseRequest):
    """Required fields for creating an invoice."""
    pass


class InvoiceUpdateRequest(BaseModel):
    invoice_number: Optional[str] = None
    customer_account_id: Optional[int] = None
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

    @field_validator("amount", "tax_amount", "amount_paid", "total_amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @field_validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class PaymentRequest(BaseModel):
    receipt_number: Optional[str] = None
    customer_account_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: Decimal
    currency: str = "NGN"
    payment_method: Optional[str] = PaymentMethod.BANK_TRANSFER.value
    status: Optional[str] = PaymentStatus.COMPLETED.value
    payment_date: datetime
    transaction_reference: Optional[str] = None
    gateway_reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value))

    @field_validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class PaymentUpdateRequest(BaseModel):
    receipt_number: Optional[str] = None
    customer_account_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None
    payment_date: Optional[datetime] = None
    transaction_reference: Optional[str] = None
    gateway_reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @field_validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class SalesOrderLineItemRequest(BaseModel):
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    qty: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    uom: Optional[str] = None
    warehouse: Optional[str] = None
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    is_tax_inclusive: bool = False

    @field_validator(
        "qty",
        "rate",
        "discount_percentage",
        "discount_amount",
        "tax_rate",
        "tax_amount",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class QuotationLineItemRequest(BaseModel):
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    qty: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    uom: Optional[str] = None
    warehouse: Optional[str] = None
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    is_tax_inclusive: bool = False

    @field_validator(
        "qty",
        "rate",
        "discount_percentage",
        "discount_amount",
        "tax_rate",
        "tax_amount",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class SalesOrderRequest(BaseModel):
    customer_account_id: Optional[int] = None
    quotation_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    billing_gps_lat: Optional[Decimal] = None
    billing_gps_lng: Optional[Decimal] = None
    shipping_address: Optional[str] = None
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_gps_lat: Optional[Decimal] = None
    shipping_gps_lng: Optional[Decimal] = None
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
    sales_partner_id: Optional[int] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    items: Optional[List["SalesOrderLineItemRequest"]] = None

    @field_validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        "per_delivered",
        "per_billed",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @field_validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class SalesOrderUpdateRequest(BaseModel):
    customer_account_id: Optional[int] = None
    quotation_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    billing_gps_lat: Optional[Decimal] = None
    billing_gps_lng: Optional[Decimal] = None
    shipping_address: Optional[str] = None
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_gps_lat: Optional[Decimal] = None
    shipping_gps_lng: Optional[Decimal] = None
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
    sales_partner_id: Optional[int] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    items: Optional[List["SalesOrderLineItemRequest"]] = None

    @field_validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        "per_delivered",
        "per_billed",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @field_validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class QuotationRequest(BaseModel):
    quotation_to: Optional[str] = None
    party_name: Optional[str] = Field(default=None, json_schema_extra={"deprecated": True})
    customer_name: Optional[str] = None
    customer_account_id: Optional[int] = None
    lead_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    billing_gps_lat: Optional[Decimal] = None
    billing_gps_lng: Optional[Decimal] = None
    shipping_address: Optional[str] = None
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_gps_lat: Optional[Decimal] = None
    shipping_gps_lng: Optional[Decimal] = None
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
    sales_partner_id: Optional[int] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    order_lost_reason: Optional[str] = None
    items: Optional[List["QuotationLineItemRequest"]] = None

    @field_validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")

    @field_validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _sync_customer_name(self):
        if not self.customer_name and self.party_name:
            self.customer_name = self.party_name
        if not self.party_name and self.customer_name:
            self.party_name = self.customer_name
        return self


class QuotationUpdateRequest(BaseModel):
    quotation_to: Optional[str] = None
    party_name: Optional[str] = Field(default=None, json_schema_extra={"deprecated": True})
    customer_name: Optional[str] = None
    customer_account_id: Optional[int] = None
    lead_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    billing_gps_lat: Optional[Decimal] = None
    billing_gps_lng: Optional[Decimal] = None
    shipping_address: Optional[str] = None
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_gps_lat: Optional[Decimal] = None
    shipping_gps_lng: Optional[Decimal] = None
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
    sales_partner_id: Optional[int] = None
    territory: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    order_lost_reason: Optional[str] = None
    items: Optional[List["QuotationLineItemRequest"]] = None

    @field_validator(
        "total_qty",
        "total",
        "net_total",
        "grand_total",
        "rounded_total",
        "total_taxes_and_charges",
        mode="before",
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @field_validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value

    @model_validator(mode="after")
    def _sync_customer_name(self):
        if not self.customer_name and self.party_name:
            self.customer_name = self.party_name
        if not self.party_name and self.customer_name:
            self.party_name = self.customer_name
        return self


class CustomerGroupRequest(BaseModel):
    customer_group_name: str
    parent_customer_group: Optional[str] = None
    is_group: bool = False
    default_price_list: Optional[str] = None
    default_payment_terms_template: Optional[str] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


class CustomerGroupUpdateRequest(BaseModel):
    customer_group_name: Optional[str] = None
    parent_customer_group: Optional[str] = None
    is_group: Optional[bool] = None
    default_price_list: Optional[str] = None
    default_payment_terms_template: Optional[str] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


class TerritoryRequest(BaseModel):
    territory_name: str
    parent_territory: Optional[str] = None
    is_group: bool = False
    territory_manager: Optional[str] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


class TerritoryUpdateRequest(BaseModel):
    territory_name: Optional[str] = None
    parent_territory: Optional[str] = None
    is_group: Optional[bool] = None
    territory_manager: Optional[str] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


class SalesPersonRequest(BaseModel):
    sales_person_name: str
    parent_sales_person: Optional[str] = None
    is_group: bool = False
    employee: Optional[str] = None
    department: Optional[str] = None
    employee_id: Optional[int] = None
    enabled: bool = True
    commission_rate: Optional[Decimal] = Decimal("0")
    lft: Optional[int] = None
    rgt: Optional[int] = None

    @field_validator("commission_rate", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class SalesPersonUpdateRequest(BaseModel):
    sales_person_name: Optional[str] = None
    parent_sales_person: Optional[str] = None
    is_group: Optional[bool] = None
    employee: Optional[str] = None
    department: Optional[str] = None
    employee_id: Optional[int] = None
    enabled: Optional[bool] = None
    commission_rate: Optional[Decimal] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None

    @field_validator("commission_rate", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


class CreditNoteRequest(BaseModel):
    credit_number: Optional[str] = None
    customer_account_id: Optional[int] = None
    invoice_id: Optional[int] = None
    description: Optional[str] = None
    amount: Decimal
    currency: str = "NGN"
    status: Optional[str] = CreditNoteStatus.ISSUED.value
    issue_date: Optional[datetime] = None
    applied_date: Optional[datetime] = None

    @field_validator("amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value))

    @field_validator("currency")
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class CreditNoteUpdateRequest(BaseModel):
    credit_number: Optional[str] = None
    customer_account_id: Optional[int] = None
    invoice_id: Optional[int] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    issue_date: Optional[datetime] = None
    applied_date: Optional[datetime] = None

    @field_validator("amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None

    @field_validator("currency")
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class CustomerAccountRequest(BaseModel):
    """Customer account request payload."""
    account_number: Optional[str] = None
    billing_email: Optional[str] = None
    billing_type: Optional[str] = None
    billing_cycle: Optional[str] = None
    currency: Optional[str] = "NGN"
    status: Optional[str] = "active"
    tier: Optional[str] = "standard"
    customer_id: Optional[int] = None
    party_id: Optional[int] = Field(default=None, json_schema_extra={"deprecated": True})
    customer_type: Optional[str] = None

    @model_validator(mode="after")
    def _sync_customer_id(self):
        if self.customer_id is None and self.party_id is not None:
            self.customer_id = self.party_id
        if self.party_id is None and self.customer_id is not None:
            self.party_id = self.customer_id
        return self


class CustomerAccountUpdateRequest(BaseModel):
    account_number: Optional[str] = None
    billing_email: Optional[str] = None
    billing_type: Optional[str] = None
    billing_cycle: Optional[str] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    tier: Optional[str] = None
    customer_id: Optional[int] = None
    party_id: Optional[int] = Field(default=None, json_schema_extra={"deprecated": True})
    customer_type: Optional[str] = None

    @model_validator(mode="after")
    def _sync_customer_id(self):
        if self.customer_id is None and self.party_id is not None:
            self.customer_id = self.party_id
        if self.party_id is None and self.customer_id is not None:
            self.party_id = self.customer_id
        return self


def _serialize_invoice(invoice: Invoice, db: Session) -> Dict[str, Any]:
    """Serialize an invoice with customer and payments for API responses."""
    payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
    items = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()

    customer_account = None
    customer_id = None
    customer_name = None
    if invoice.customer_account and invoice.customer_account.party:
        party = invoice.customer_account.party
        customer_id = party.id
        customer_name = party.name
        if not customer_name:
            customer_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not customer_name:
            customer_name = party.legal_name or party.trading_name
        customer_account = {
            "id": invoice.customer_account.id,
            "customer_id": party.id,
            "customer_name": customer_name,
        }

    return {
        "id": invoice.id,
        "customer_account_id": invoice.customer_account_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
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
        "customer_account": customer_account,
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
                "qty": float(it.quantity or 0),
                "stock_qty": None,
                "uom": it.uom,
                "stock_uom": None,
                "rate": float(it.rate or 0),
                "price_list_rate": None,
                "discount_percentage": float(it.discount_percentage or 0),
                "discount_amount": float(it.discount_amount or 0),
                "amount": float(it.amount or 0),
                "net_amount": float(it.net_amount or 0),
                "warehouse": None,
                "income_account": it.account,
                "expense_account": None,
                "cost_center": it.cost_center,
                "sales_order": None,
                "delivery_note": None,
                "idx": it.idx,
            }
            for it in items
        ],
    }


def _serialize_payment(payment: Payment) -> Dict[str, Any]:
    customer_id = None
    customer_name = None
    if payment.customer_account and payment.customer_account.party:
        party = payment.customer_account.party
        customer_id = party.id
        customer_name = party.name
        if not customer_name:
            customer_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not customer_name:
            customer_name = party.legal_name or party.trading_name

    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "customer_account_id": payment.customer_account_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
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
                "qty": float(it.quantity or 0),
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
                "tax_code_id": it.tax_code_id,
                "tax_rate": float(it.tax_rate or 0),
                "tax_amount": float(it.tax_amount or 0),
                "is_tax_inclusive": bool(it.is_tax_inclusive),
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
        "customer_account_id": order.customer_account_id,
        "customer_id": order.party_id,
        "quotation_id": order.quotation_id,
        "customer_name": order.customer_name,
        "contact_name": order.contact_name,
        "contact_email": order.contact_email,
        "contact_phone": order.contact_phone,
        "billing_address": order.billing_address,
        "billing_address_line1": order.billing_address_line1,
        "billing_address_line2": order.billing_address_line2,
        "billing_city": order.billing_city,
        "billing_state": order.billing_state,
        "billing_postal_code": order.billing_postal_code,
        "billing_country": order.billing_country,
        "billing_gps_lat": float(order.billing_gps_lat) if order.billing_gps_lat is not None else None,
        "billing_gps_lng": float(order.billing_gps_lng) if order.billing_gps_lng is not None else None,
        "shipping_address": order.shipping_address,
        "shipping_address_line1": order.shipping_address_line1,
        "shipping_address_line2": order.shipping_address_line2,
        "shipping_city": order.shipping_city,
        "shipping_state": order.shipping_state,
        "shipping_postal_code": order.shipping_postal_code,
        "shipping_country": order.shipping_country,
        "shipping_gps_lat": float(order.shipping_gps_lat) if order.shipping_gps_lat is not None else None,
        "shipping_gps_lng": float(order.shipping_gps_lng) if order.shipping_gps_lng is not None else None,
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
        "sales_partner_id": order.sales_partner_id,
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
                "qty": float(it.quantity or 0),
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
                "tax_code_id": it.tax_code_id,
                "tax_rate": float(it.tax_rate or 0),
                "tax_amount": float(it.tax_amount or 0),
                "is_tax_inclusive": bool(it.is_tax_inclusive),
                "idx": it.idx,
            }
            for it in quote.items
        ]

    return {
        "id": quote.id,
        "erpnext_id": quote.erpnext_id,
        "quotation_to": quote.quotation_to,
        "customer_name": quote.customer_name or quote.party_name,
        "customer_account_id": quote.customer_account_id,
        "lead_id": quote.lead_id,
        "contact_name": quote.contact_name,
        "contact_email": quote.contact_email,
        "contact_phone": quote.contact_phone,
        "billing_address": quote.billing_address,
        "billing_address_line1": quote.billing_address_line1,
        "billing_address_line2": quote.billing_address_line2,
        "billing_city": quote.billing_city,
        "billing_state": quote.billing_state,
        "billing_postal_code": quote.billing_postal_code,
        "billing_country": quote.billing_country,
        "billing_gps_lat": float(quote.billing_gps_lat) if quote.billing_gps_lat is not None else None,
        "billing_gps_lng": float(quote.billing_gps_lng) if quote.billing_gps_lng is not None else None,
        "shipping_address": quote.shipping_address,
        "shipping_address_line1": quote.shipping_address_line1,
        "shipping_address_line2": quote.shipping_address_line2,
        "shipping_city": quote.shipping_city,
        "shipping_state": quote.shipping_state,
        "shipping_postal_code": quote.shipping_postal_code,
        "shipping_country": quote.shipping_country,
        "shipping_gps_lat": float(quote.shipping_gps_lat) if quote.shipping_gps_lat is not None else None,
        "shipping_gps_lng": float(quote.shipping_gps_lng) if quote.shipping_gps_lng is not None else None,
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
        "sales_partner_id": quote.sales_partner_id,
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
        "customer_account_id": note.customer_account_id,
        "invoice_id": note.invoice_id,
        "description": note.description,
        "amount": float(note.amount),
        "currency": note.currency,
        "status": note.status.value if note.status else None,
        "issue_date": note.issue_date.isoformat() if note.issue_date else None,
        "applied_date": note.applied_date.isoformat() if note.applied_date else None,
        "write_back_status": getattr(note, "write_back_status", None),
    }
