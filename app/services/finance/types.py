"""Finance service data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class RevenueMetrics:
    """Revenue metrics data class."""

    mrr: float
    arr: float
    active_subscriptions: int
    currency: Optional[str] = None


@dataclass
class CollectionMetrics:
    """Collection metrics data class."""

    collections_30d: float
    invoiced_30d: float
    collection_rate: float
    dso: float
    outstanding_total: float
    outstanding_overdue: float


@dataclass
class InvoiceSummary:
    """Invoice summary by status."""

    status: str
    count: int
    total: float


@dataclass
class InvoiceAgingBucket:
    """Invoice aging bucket data."""

    bucket: str
    count: int
    outstanding: float


@dataclass
class InvoiceAgingResult:
    """Invoice aging analysis result."""

    buckets: List[InvoiceAgingBucket]
    total_outstanding: float
    at_risk: float
    at_risk_percent: float
    total_invoices: int


@dataclass
class PaymentTimingBreakdown:
    """Payment timing classification."""

    early: int
    on_time: int
    late: int
    total: int


@dataclass
class PaymentMethodDistribution:
    """Payment method distribution."""

    method: str
    count: int
    total: float


@dataclass
class DailyCollection:
    """Daily collection total."""

    date: str
    total: float


@dataclass
class CollectionsAnalytics:
    """Collections analytics result."""

    by_method: List[PaymentMethodDistribution]
    payment_timing: PaymentTimingBreakdown
    daily_totals: List[DailyCollection]
    start_date: datetime
    end_date: datetime
    currency: Optional[str] = None


@dataclass
class RevenueTrend:
    """Single revenue trend data point."""

    year: int
    month: Optional[int]
    period: str
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    revenue: float
    payment_count: int


@dataclass
class RevenueTrendResult:
    """Revenue trend result."""

    data: List[RevenueTrend]
    interval: str
    start_date: datetime
    end_date: datetime
    currency: Optional[str] = None


@dataclass
class CurrencyBreakdown:
    """Revenue breakdown by currency."""

    currency: str
    mrr: float
    arr: float
    subscription_count: int
    outstanding: float


@dataclass
class PaymentBehaviorInsights:
    """Customer payment behavior analysis."""

    customers_with_payments: int
    customers_with_overdue: int
    avg_late_payment_delay_days: float
    late_payments_percent: float


@dataclass
class PaymentBehaviorResult:
    """Payment behavior analysis result."""

    summary: PaymentBehaviorInsights
    recommendations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RevenueForecast:
    """Revenue projection data."""

    current_mrr: float
    current_arr: float
    new_subscriptions_30d: int
    month_1_projection: float
    month_2_projection: float
    month_3_projection: float
    quarter_total_projection: float
    currency: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)


@dataclass
class DashboardResult:
    """Finance dashboard result."""

    revenue: RevenueMetrics
    collections: CollectionMetrics
    invoices_by_status: Dict[str, InvoiceSummary]
