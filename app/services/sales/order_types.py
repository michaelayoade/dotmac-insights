"""Type definitions for sales order service.

These dataclasses define the contract for sales order operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


__all__ = [
    "SalesOrderFilters",
    "SalesOrderCreateData",
    "SalesOrderUpdateData",
    "SalesOrderLineItemData",
    "SalesOrderLineItemUpdateData",
    "SalesOrderSummary",
    "FulfillmentStatus",
]


@dataclass
class SalesOrderFilters:
    """Filters for listing sales orders."""

    search: Optional[str] = None
    status: Optional[str] = None  # draft, to_deliver_and_bill, to_bill, to_deliver, completed, cancelled, closed, on_hold
    customer: Optional[str] = None
    customer_account_id: Optional[int] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    delivery_date_from: Optional[date] = None
    delivery_date_to: Optional[date] = None
    billing_status: Optional[str] = None
    delivery_status: Optional[str] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    company: Optional[str] = None


@dataclass
class SalesOrderLineItemData:
    """Data for a sales order line item."""

    item_code: str
    item_name: str
    qty: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    description: Optional[str] = None
    uom: Optional[str] = None
    warehouse: Optional[str] = None
    delivery_date: Optional[date] = None


@dataclass
class SalesOrderCreateData:
    """Data for creating a sales order."""

    customer: str
    customer_name: Optional[str] = None
    customer_account_id: Optional[int] = None
    company: Optional[str] = None
    currency: str = "NGN"
    transaction_date: Optional[date] = None
    delivery_date: Optional[date] = None
    order_type: Optional[str] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    items: List[SalesOrderLineItemData] = field(default_factory=list)
    quotation_id: Optional[int] = None  # Source quotation if converted


@dataclass
class SalesOrderUpdateData:
    """Data for updating a sales order (all fields optional)."""

    customer_name: Optional[str] = None
    delivery_date: Optional[date] = None
    order_type: Optional[str] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None


@dataclass
class SalesOrderLineItemUpdateData:
    """Data for updating a sales order line item."""

    qty: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    description: Optional[str] = None
    delivery_date: Optional[date] = None


@dataclass
class FulfillmentStatus:
    """Delivery and billing fulfillment status."""

    order_id: int
    per_delivered: Decimal
    per_billed: Decimal
    is_fully_delivered: bool
    is_fully_billed: bool
    pending_delivery_qty: Decimal
    pending_billing_amount: Decimal


@dataclass
class SalesOrderSummary:
    """Summary statistics for sales orders."""

    total_count: int
    total_value: Decimal
    draft_count: int
    draft_value: Decimal
    pending_delivery_count: int
    pending_delivery_value: Decimal
    pending_billing_count: int
    pending_billing_value: Decimal
    completed_count: int
    completed_value: Decimal
    on_hold_count: int
    on_hold_value: Decimal
    fulfillment_rate: float
    avg_order_value: Decimal
