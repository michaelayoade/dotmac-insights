"""Type definitions for Sales analytics service.

These dataclasses define the contract for Sales analytics operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


__all__ = [
    "SalesAnalyticsFilters",
    "QuoteAnalytics",
    "OrderAnalytics",
    "FulfillmentMetrics",
    "ItemSalesData",
    "CustomerSalesData",
    "SalesTrendPoint",
    "ProductMixItem",
    "SalesAgingAnalysis",
    "MonthlyComparison",
    "RevenueByPeriod",
]


@dataclass
class SalesAnalyticsFilters:
    """Filters for Sales analytics queries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    party_id: Optional[int] = None
    party_ids: List[int] = field(default_factory=list)
    sales_person_id: Optional[int] = None
    item_id: Optional[int] = None
    item_group: Optional[str] = None
    currency: Optional[str] = None


@dataclass
class QuoteAnalytics:
    """Quotation analytics summary."""

    total_quotes: int
    open_quotes: int
    converted_quotes: int
    lost_quotes: int
    expired_quotes: int
    total_value: Decimal
    converted_value: Decimal
    conversion_rate: float  # percentage
    avg_quote_value: Decimal
    avg_time_to_convert_days: Optional[float]
    by_status: Dict[str, int]  # status → count


@dataclass
class OrderAnalytics:
    """Sales order analytics summary."""

    total_orders: int
    pending_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_value: Decimal
    delivered_value: Decimal
    avg_order_value: Decimal
    fulfillment_rate: float  # percentage
    avg_fulfillment_days: Optional[float]
    by_status: Dict[str, int]  # status → count


@dataclass
class FulfillmentMetrics:
    """Order fulfillment metrics."""

    total_orders: int
    fully_delivered: int
    partially_delivered: int
    not_delivered: int
    fully_billed: int
    partially_billed: int
    not_billed: int
    avg_delivery_percent: float
    avg_billing_percent: float
    on_time_delivery_rate: float  # Orders delivered by expected date


@dataclass
class ItemSalesData:
    """Sales data for a single item."""

    item_id: int
    item_code: str
    item_name: str
    item_group: Optional[str]
    quantity_sold: Decimal
    total_revenue: Decimal
    order_count: int
    avg_selling_price: Decimal
    rank: Optional[int] = None


@dataclass
class CustomerSalesData:
    """Sales data for a single customer (party)."""

    party_id: int
    party_name: str
    order_count: int
    total_revenue: Decimal
    avg_order_value: Decimal
    first_order_date: Optional[date]
    last_order_date: Optional[date]
    rank: Optional[int] = None


@dataclass
class SalesTrendPoint:
    """Single point in a sales trend series."""

    period: str  # e.g., "2024-01", "2024-W05"
    period_type: str  # "daily", "weekly", "monthly"
    order_count: int
    order_value: Decimal
    item_quantity: Decimal
    comparison_value: Optional[Decimal] = None
    change_percent: Optional[float] = None


@dataclass
class ProductMixItem:
    """Product mix breakdown item."""

    item_group: str
    revenue: Decimal
    quantity: Decimal
    order_count: int
    percentage_of_total: float


@dataclass
class SalesAgingAnalysis:
    """Aging analysis for quotations or orders."""

    entity_type: str  # "quotation", "order"
    total_count: int
    total_value: Decimal
    buckets: List[Dict[str, Any]]  # [{label, min_days, max_days, count, value}]
    overdue_count: int
    overdue_value: Decimal


@dataclass
class MonthlyComparison:
    """Month-over-month comparison."""

    current_month: str
    current_value: Decimal
    current_count: int
    previous_month: str
    previous_value: Decimal
    previous_count: int
    value_change: Decimal
    value_change_percent: float
    count_change: int
    count_change_percent: float


@dataclass
class RevenueByPeriod:
    """Revenue breakdown by time period."""

    period_type: str  # "daily", "weekly", "monthly", "quarterly"
    periods: List[SalesTrendPoint]
    total_revenue: Decimal
    avg_revenue: Decimal
    best_period: Optional[str]
    best_period_value: Decimal
