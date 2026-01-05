"""Type definitions for quotation service.

These dataclasses define the contract for quotation operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


__all__ = [
    "QuotationFilters",
    "QuotationCreateData",
    "QuotationUpdateData",
    "QuotationLineItemData",
    "QuotationLineItemUpdateData",
    "OrderConversionData",
    "QuotationSummary",
]


@dataclass
class QuotationFilters:
    """Filters for listing quotations."""

    search: Optional[str] = None
    status: Optional[str] = None  # draft, open, replied, ordered, lost, cancelled, expired
    party_id: Optional[int] = None
    party_name: Optional[str] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    valid_till_before: Optional[date] = None
    valid_till_after: Optional[date] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    company: Optional[str] = None


@dataclass
class QuotationLineItemData:
    """Data for a quotation line item."""

    item_code: str
    item_name: str
    qty: Decimal = Decimal("1")
    rate: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    description: Optional[str] = None
    uom: Optional[str] = None
    warehouse: Optional[str] = None


@dataclass
class QuotationCreateData:
    """Data for creating a quotation."""

    party_name: str
    quotation_to: str = "Customer"  # Customer or Lead
    customer_name: Optional[str] = None
    company: Optional[str] = None
    currency: str = "NGN"
    transaction_date: Optional[date] = None
    valid_till: Optional[date] = None
    order_type: Optional[str] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    items: List[QuotationLineItemData] = field(default_factory=list)


@dataclass
class QuotationUpdateData:
    """Data for updating a quotation (all fields optional)."""

    quotation_to: Optional[str] = None
    party_name: Optional[str] = None
    customer_name: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    transaction_date: Optional[date] = None
    valid_till: Optional[date] = None
    order_type: Optional[str] = None
    sales_partner_id: Optional[int] = None
    territory_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    order_lost_reason: Optional[str] = None


@dataclass
class QuotationLineItemUpdateData:
    """Data for updating a quotation line item."""

    qty: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    description: Optional[str] = None


@dataclass
class OrderConversionData:
    """Data for converting quotation to sales order."""

    delivery_date: Optional[date] = None
    payment_terms: Optional[str] = None
    order_type: Optional[str] = None


@dataclass
class QuotationSummary:
    """Summary statistics for quotations."""

    total_count: int
    total_value: Decimal
    draft_count: int
    draft_value: Decimal
    open_count: int
    open_value: Decimal
    ordered_count: int
    ordered_value: Decimal
    lost_count: int
    lost_value: Decimal
    conversion_rate: float
    avg_quote_value: Decimal
