"""Type definitions for Sales dashboard service.

These dataclasses define the contract for Sales dashboard operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


__all__ = [
    "SalesDashboardFilters",
    "SalesDashboardSummary",
    "SalesKPICard",
    "OrderMetrics",
    "QuoteSummary",
    "AgingChart",
    "FulfillmentStatus",
    "DeliveryTimeline",
    "ProductRevenue",
    "CustomerRevenue",
    "SalesMonthlyComparison",
    "QuoteConversionChart",
    "RevenueChart",
]


@dataclass
class SalesDashboardFilters:
    """Filters for Sales dashboard queries."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sales_person_id: Optional[int] = None
    territory_id: Optional[int] = None
    customer_id: Optional[int] = None
    period: str = "month"  # day, week, month, quarter, year


@dataclass
class SalesKPICard:
    """Single KPI card for sales dashboard."""

    key: str  # unique identifier
    title: str
    value: Any  # Can be int, Decimal, float, str
    formatted_value: str  # Pre-formatted display value
    trend: Optional[float]  # Percentage change
    trend_direction: Optional[str]  # "up", "down", "stable"
    comparison_period: Optional[str]  # e.g., "vs last month"
    icon: Optional[str] = None
    color: Optional[str] = None


@dataclass
class SalesDashboardSummary:
    """Complete Sales dashboard summary."""

    # Quote metrics
    total_quotes: int
    open_quotes: int
    open_quote_value: Decimal
    quote_conversion_rate: float

    # Order metrics
    total_orders: int
    pending_orders: int
    pending_order_value: Decimal
    completed_orders: int

    # Revenue metrics
    total_revenue_this_period: Decimal
    avg_order_value: Decimal
    items_sold: int

    # Fulfillment
    fulfillment_rate: float
    billing_rate: float

    # KPI cards
    kpi_cards: List[SalesKPICard]


@dataclass
class OrderMetrics:
    """Sales order metrics for dashboard."""

    total_orders: int
    by_status: Dict[str, int]  # status → count
    by_status_value: Dict[str, Decimal]  # status → total value
    orders_this_week: int
    orders_this_month: int
    avg_processing_days: Optional[float]
    on_time_rate: float  # Percentage delivered on time


@dataclass
class QuoteSummary:
    """Quotation summary for dashboard."""

    total_quotes: int
    open_quotes: int
    ordered_quotes: int
    lost_quotes: int
    expired_quotes: int
    open_value: Decimal
    ordered_value: Decimal
    conversion_rate: float
    avg_days_to_convert: Optional[float]
    expiring_soon: int  # Quotes expiring in next 7 days


@dataclass
class AgingChart:
    """Aging analysis chart data."""

    entity_type: str  # "quotation" or "order"
    buckets: List[Dict[str, Any]]  # [{label, min_days, max_days, count, value, color}]
    total_count: int
    total_value: Decimal
    avg_age_days: float


@dataclass
class FulfillmentStatus:
    """Order fulfillment status breakdown."""

    total_orders: int

    # Delivery status
    not_delivered: int
    partially_delivered: int
    fully_delivered: int

    # Billing status
    not_billed: int
    partially_billed: int
    fully_billed: int

    # Percentages
    delivery_progress: float  # Overall delivery completion
    billing_progress: float  # Overall billing completion

    # Orders needing attention
    pending_delivery: List[Dict[str, Any]]  # [{id, customer, amount, days_pending}]
    pending_billing: List[Dict[str, Any]]  # [{id, customer, amount, days_pending}]


@dataclass
class DeliveryTimeline:
    """Delivery timeline for upcoming deliveries."""

    upcoming_deliveries: List[Dict[str, Any]]  # [{id, customer, delivery_date, amount}]
    overdue_deliveries: List[Dict[str, Any]]  # [{id, customer, expected_date, days_late}]
    today_count: int
    this_week_count: int
    this_month_count: int


@dataclass
class ProductRevenue:
    """Revenue breakdown by product/item."""

    rank: int
    item_id: int
    item_code: str
    item_name: str
    item_group: Optional[str]
    quantity_sold: Decimal
    revenue: Decimal
    order_count: int
    percentage_of_total: float


@dataclass
class CustomerRevenue:
    """Revenue breakdown by customer."""

    rank: int
    party_id: int
    party_name: str
    order_count: int
    revenue: Decimal
    avg_order_value: Decimal
    percentage_of_total: float
    last_order_date: Optional[date]


@dataclass
class SalesMonthlyComparison:
    """Month-over-month sales comparison."""

    current_month: str  # e.g., "2024-01"
    current_orders: int
    current_revenue: Decimal
    current_avg_value: Decimal

    previous_month: str
    previous_orders: int
    previous_revenue: Decimal
    previous_avg_value: Decimal

    # Changes
    order_change: int
    order_change_percent: float
    revenue_change: Decimal
    revenue_change_percent: float


@dataclass
class QuoteConversionChart:
    """Quotation conversion funnel chart data."""

    levels: List[Dict[str, Any]]  # [{name, count, value, conversion_rate}]
    overall_conversion: float
    avg_days_in_each_stage: Dict[str, float]


@dataclass
class RevenueChart:
    """Revenue chart data over time."""

    period_type: str  # daily, weekly, monthly
    data_points: List[Dict[str, Any]]  # [{period, revenue, orders, avg_value}]
    total_revenue: Decimal
    avg_revenue: Decimal
    trend_direction: str  # up, down, stable
    trend_percentage: float
