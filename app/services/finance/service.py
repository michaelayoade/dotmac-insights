"""
Finance Service - Business logic for finance analytics and metrics.

Encapsulates all business logic for:
- Revenue calculations (MRR, ARR)
- Collections and outstanding metrics
- Invoice aging analysis
- Payment behavior insights
- Revenue forecasting
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, cast

from sqlalchemy import func, case, and_, distinct
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.errors import ValidationError

from .types import (
    RevenueMetrics,
    CollectionMetrics,
    InvoiceSummary,
    InvoiceAgingBucket,
    InvoiceAgingResult,
    PaymentTimingBreakdown,
    PaymentMethodDistribution,
    DailyCollection,
    CollectionsAnalytics,
    RevenueTrend,
    RevenueTrendResult,
    CurrencyBreakdown,
    PaymentBehaviorInsights,
    PaymentBehaviorResult,
    RevenueForecast,
    DashboardResult,
)


class FinanceService:
    """
    Service for finance analytics, metrics, and reporting.

    All methods enforce single-currency constraints when aggregating
    monetary values to prevent accidental currency mixing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _parse_iso_utc(self, value: Optional[str], field_name: str) -> Optional[datetime]:
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
            raise ValidationError(f"Invalid {field_name} date: {value}")

    def _resolve_currency_or_raise(self, column, requested: Optional[str]) -> Optional[str]:
        """
        Ensure we do not mix currencies.

        If none requested and multiple exist, raise ValidationError.
        """
        if requested:
            return requested
        currencies = [
            row[0]
            for row in self.db.query(distinct(column)).filter(column.isnot(None)).all()
        ]
        if not currencies:
            return None
        if len(set(currencies)) > 1:
            raise ValidationError(
                "Multiple currencies detected; please provide the 'currency' parameter "
                "to avoid mixed-currency aggregates."
            )
        return cast(Optional[str], currencies[0])

    def _get_mrr_case(self):
        """Get the CASE expression for MRR calculation."""
        return case(
            (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
            (Subscription.billing_cycle == "yearly", Subscription.price / 12),
            else_=Subscription.price,
        )

    # =========================================================================
    # REVENUE METRICS
    # =========================================================================

    def calculate_mrr(self, currency: Optional[str] = None) -> float:
        """
        Calculate Monthly Recurring Revenue from active subscriptions.

        Args:
            currency: Optional currency filter (required if multiple currencies)

        Returns:
            MRR as float (annualized billing converted to monthly)

        Raises:
            ValidationError: If multiple currencies detected and none specified
        """
        currency = self._resolve_currency_or_raise(Subscription.currency, currency)
        mrr_case = self._get_mrr_case()

        query = self.db.query(func.sum(mrr_case)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        if currency:
            query = query.filter(Subscription.currency == currency)

        return float(query.scalar() or 0)

    def calculate_revenue_metrics(self, currency: Optional[str] = None) -> RevenueMetrics:
        """
        Calculate comprehensive revenue metrics (MRR, ARR, subscription count).

        Args:
            currency: Optional currency filter

        Returns:
            RevenueMetrics dataclass with calculated values

        Raises:
            ValidationError: If multiple currencies detected and none specified
        """
        currency = self._resolve_currency_or_raise(Subscription.currency, currency)

        mrr = self.calculate_mrr(currency)
        arr = mrr * 12

        active_subscriptions = (
            self.db.query(func.count(Subscription.id))
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                *([Subscription.currency == currency] if currency else []),
            )
            .scalar()
            or 0
        )

        return RevenueMetrics(
            mrr=mrr,
            arr=arr,
            active_subscriptions=active_subscriptions,
            currency=currency,
        )

    def get_revenue_by_currency(self) -> List[CurrencyBreakdown]:
        """
        Get revenue breakdown by currency.

        Returns:
            List of CurrencyBreakdown with mrr, arr, subscription_count, outstanding
        """
        mrr_case = self._get_mrr_case()

        by_currency = (
            self.db.query(
                Subscription.currency,
                func.sum(mrr_case).label("mrr"),
                func.count(Subscription.id).label("subscription_count"),
            )
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(Subscription.currency)
            .all()
        )

        # Outstanding by currency
        outstanding = (
            self.db.query(
                Invoice.currency,
                func.sum(
                    func.coalesce(
                        Invoice.balance,
                        Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
                    )
                ).label("outstanding"),
            )
            .filter(
                Invoice.status.in_(
                    [InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]
                ),
                Invoice.is_deleted == False,
                func.coalesce(
                    Invoice.balance,
                    Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
                ) > 0,
            )
            .group_by(Invoice.currency)
            .all()
        )

        outstanding_map = {row.currency: float(row.outstanding or 0) for row in outstanding}

        return [
            CurrencyBreakdown(
                currency=row.currency,
                mrr=float(row.mrr or 0),
                arr=float(row.mrr or 0) * 12,
                subscription_count=row.subscription_count,
                outstanding=outstanding_map.get(row.currency, 0),
            )
            for row in by_currency
        ]

    # =========================================================================
    # OUTSTANDING & COLLECTIONS
    # =========================================================================

    def calculate_outstanding_balance(self, currency: Optional[str] = None) -> float:
        """
        Calculate total outstanding balance from unpaid invoices.

        Includes: PENDING, OVERDUE, PARTIALLY_PAID invoices

        Args:
            currency: Optional currency filter

        Returns:
            Outstanding balance as float
        """
        query = self.db.query(
            func.sum(
                func.coalesce(
                    Invoice.balance,
                    Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
                )
            )
        ).filter(
            Invoice.status.in_(
                [InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]
            ),
            Invoice.is_deleted == False,
            func.coalesce(
                Invoice.balance,
                Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
            ) > 0,
        )
        if currency:
            query = query.filter(Invoice.currency == currency)

        return float(query.scalar() or 0)

    def calculate_overdue_amount(self, currency: Optional[str] = None) -> float:
        """
        Calculate amount overdue from overdue invoices.

        Args:
            currency: Optional currency filter

        Returns:
            Overdue amount as float
        """
        query = self.db.query(
            func.sum(
                func.coalesce(
                    Invoice.balance,
                    Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
                )
            )
        ).filter(
            Invoice.status == InvoiceStatus.OVERDUE,
            Invoice.is_deleted == False,
            func.coalesce(
                Invoice.balance,
                Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
            ) > 0,
        )
        if currency:
            query = query.filter(Invoice.currency == currency)

        return float(query.scalar() or 0)

    def calculate_collection_metrics(
        self,
        days_lookback: int = 30,
        currency: Optional[str] = None,
    ) -> CollectionMetrics:
        """
        Calculate collections and DSO metrics for a time period.

        Args:
            days_lookback: Number of days to look back (default 30)
            currency: Optional currency filter

        Returns:
            CollectionMetrics with collections, collection_rate, DSO, etc.

        Raises:
            ValidationError: If multiple currencies and none specified
        """
        currency = self._resolve_currency_or_raise(Payment.currency, currency)
        lookback_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        # Collections in period
        collections_query = self.db.query(func.sum(Payment.amount)).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date >= lookback_date,
        )
        if currency:
            collections_query = collections_query.filter(Payment.currency == currency)
        collections = float(collections_query.scalar() or 0)

        # Invoiced in period
        invoiced_query = self.db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date >= lookback_date,
            Invoice.is_deleted == False,
        )
        if currency:
            invoiced_query = invoiced_query.filter(Invoice.currency == currency)
        invoiced = float(invoiced_query.scalar() or 0)

        # Collection rate
        collection_rate = round(collections / invoiced * 100, 1) if invoiced else 0

        # Outstanding
        outstanding = self.calculate_outstanding_balance(currency)
        overdue = self.calculate_overdue_amount(currency)

        # DSO (Days Sales Outstanding) - simplified calculation
        avg_daily_revenue = collections / days_lookback if collections else 0
        dso = round(outstanding / avg_daily_revenue, 1) if avg_daily_revenue > 0 else 0

        return CollectionMetrics(
            collections_30d=collections,
            invoiced_30d=invoiced,
            collection_rate=collection_rate,
            dso=dso,
            outstanding_total=outstanding,
            outstanding_overdue=overdue,
        )

    # =========================================================================
    # INVOICE METRICS
    # =========================================================================

    def get_invoice_summary_by_status(
        self,
        currency: Optional[str] = None,
    ) -> Dict[str, InvoiceSummary]:
        """
        Get invoice count and total amount grouped by status.

        Args:
            currency: Optional currency filter

        Returns:
            Dict mapping status -> InvoiceSummary
        """
        query = self.db.query(
            Invoice.status,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_amount).label("total"),
        ).filter(
            Invoice.is_deleted == False,
        )
        if currency:
            query = query.filter(Invoice.currency == currency)

        invoice_summary = query.group_by(Invoice.status).all()

        return {
            row.status.value: InvoiceSummary(
                status=row.status.value,
                count=row.count,
                total=float(row.total or 0),
            )
            for row in invoice_summary
        }

    def get_invoice_aging_analysis(
        self,
        currency: Optional[str] = None,
    ) -> InvoiceAgingResult:
        """
        Analyze invoices by aging bucket (current, 1-30, 31-60, 61-90, 90+).

        Args:
            currency: Optional currency filter

        Returns:
            InvoiceAgingResult with buckets and summary

        Raises:
            ValidationError: If multiple currencies and none specified
        """
        currency = self._resolve_currency_or_raise(Invoice.currency, currency)
        days_overdue = func.date_part("day", func.current_date() - Invoice.due_date)

        aging_bucket = case(
            (Invoice.due_date >= func.current_date(), "current"),
            (days_overdue <= 30, "1-30 days"),
            (days_overdue <= 60, "31-60 days"),
            (days_overdue <= 90, "61-90 days"),
            else_="over 90 days",
        )

        query = self.db.query(
            aging_bucket.label("bucket"),
            func.count(Invoice.id).label("count"),
            func.sum(
                func.coalesce(
                    Invoice.balance,
                    Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
                )
            ).label("outstanding"),
        ).filter(
            Invoice.status.in_(
                [InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]
            ),
            Invoice.due_date.isnot(None),
            Invoice.is_deleted == False,
            func.coalesce(
                Invoice.balance,
                Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0),
            ) > 0,
        )

        if currency:
            query = query.filter(Invoice.currency == currency)

        aging = query.group_by(aging_bucket).all()

        bucket_order = ["current", "1-30 days", "31-60 days", "61-90 days", "over 90 days"]
        aging_map = {
            row.bucket: {"count": row.count, "outstanding": float(row.outstanding or 0)}
            for row in aging
        }

        buckets = [
            InvoiceAgingBucket(
                bucket=b,
                count=aging_map.get(b, {}).get("count", 0),
                outstanding=aging_map.get(b, {}).get("outstanding", 0),
            )
            for b in bucket_order
        ]

        total_outstanding = sum(b.outstanding for b in buckets)
        at_risk = sum(b.outstanding for b in buckets if b.bucket != "current")
        total_invoices = sum(b.count for b in buckets)

        return InvoiceAgingResult(
            buckets=buckets,
            total_outstanding=total_outstanding,
            at_risk=at_risk,
            at_risk_percent=round(at_risk / total_outstanding * 100, 1) if total_outstanding > 0 else 0,
            total_invoices=total_invoices,
        )

    # =========================================================================
    # REVENUE TRENDS & ANALYTICS
    # =========================================================================

    def get_revenue_trend(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: str = "month",
        currency: Optional[str] = None,
        months: int = 12,
    ) -> RevenueTrendResult:
        """
        Get revenue trend grouped by month or week.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            interval: "month" or "week"
            currency: Optional currency filter
            months: Fallback months if dates not provided

        Returns:
            RevenueTrendResult with trend data

        Raises:
            ValidationError: If interval not in (month, week)
            ValidationError: If multiple currencies and none specified
        """
        if interval not in ("month", "week"):
            raise ValidationError("interval must be 'month' or 'week'")

        currency = self._resolve_currency_or_raise(Payment.currency, currency)
        end_dt = end_date or datetime.now(timezone.utc)
        start_dt = start_date or (end_dt - timedelta(days=months * 30))

        trunc = func.date_trunc(interval, Payment.payment_date)
        query = self.db.query(
            func.extract("year", trunc).label("year"),
            func.extract("month", trunc).label("month"),
            func.to_char(trunc, "YYYY-MM" if interval == "month" else "IYYY-IW").label("period"),
            func.sum(Payment.amount).label("revenue"),
            func.count(Payment.id).label("payment_count"),
            func.min(Payment.payment_date).label("period_start"),
            func.max(Payment.payment_date).label("period_end"),
        ).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date >= start_dt,
            Payment.payment_date <= end_dt,
        )

        if currency:
            query = query.filter(Payment.currency == currency)

        revenue = query.group_by(trunc).order_by(trunc).all()

        return RevenueTrendResult(
            data=[
                RevenueTrend(
                    year=int(r.year),
                    month=int(r.month) if r.month is not None else None,
                    period=r.period,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    revenue=float(r.revenue or 0),
                    payment_count=int(r.payment_count or 0),
                )
                for r in revenue
            ],
            interval=interval,
            start_date=start_dt,
            end_date=end_dt,
            currency=currency,
        )

    def get_collections_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        currency: Optional[str] = None,
    ) -> CollectionsAnalytics:
        """
        Get collection analytics including payment methods, timing, and daily totals.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            currency: Optional currency filter

        Returns:
            CollectionsAnalytics with by_method, payment_timing, daily_totals
        """
        currency = self._resolve_currency_or_raise(Payment.currency, currency)
        end_dt = end_date or datetime.now(timezone.utc)
        start_dt = start_date or (end_dt - timedelta(days=30))

        # Payment method distribution
        by_method = (
            self.db.query(
                Payment.payment_method,
                func.count(Payment.id).label("count"),
                func.sum(Payment.amount).label("total"),
            )
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
            )
        )

        if currency:
            by_method = by_method.filter(Payment.currency == currency)

        by_method_rows = by_method.group_by(Payment.payment_method).all()

        # Payment timing analysis (early/on-time/late)
        days_diff = func.date_part("day", Invoice.due_date - Payment.payment_date)

        timing_query = (
            self.db.query(
                func.sum(
                    case(
                        (and_(Payment.payment_date <= Invoice.due_date, days_diff > 3), 1),
                        else_=0,
                    )
                ).label("early"),
                func.sum(
                    case(
                        (and_(Payment.payment_date <= Invoice.due_date, days_diff <= 3), 1),
                        else_=0,
                    )
                ).label("on_time"),
                func.sum(case((Payment.payment_date > Invoice.due_date, 1), else_=0)).label(
                    "late"
                ),
                func.count(Payment.id).label("total"),
            )
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Invoice.due_date.isnot(None),
                Payment.payment_date.isnot(None),
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
            )
        )
        if currency:
            timing_query = timing_query.filter(
                Payment.currency == currency, Invoice.currency == currency
            )

        timing = timing_query.one_or_none()

        # Daily totals for charting
        daily = (
            self.db.query(
                func.date(Payment.payment_date).label("date"),
                func.sum(Payment.amount).label("total"),
            )
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
            )
        )
        if currency:
            daily = daily.filter(Payment.currency == currency)

        daily_totals = [
            DailyCollection(date=row.date.isoformat(), total=float(row.total or 0))
            for row in daily.group_by(func.date(Payment.payment_date))
            .order_by(func.date(Payment.payment_date))
            .all()
        ]

        return CollectionsAnalytics(
            by_method=[
                PaymentMethodDistribution(
                    method=row.payment_method.value if row.payment_method else "unknown",
                    count=row.count,
                    total=float(row.total or 0),
                )
                for row in by_method_rows
            ],
            payment_timing=PaymentTimingBreakdown(
                early=int(timing.early or 0) if timing else 0,
                on_time=int(timing.on_time or 0) if timing else 0,
                late=int(timing.late or 0) if timing else 0,
                total=int(timing.total or 0) if timing else 0,
            ),
            daily_totals=daily_totals,
            start_date=start_dt,
            end_date=end_dt,
            currency=currency,
        )

    # =========================================================================
    # INSIGHTS & BEHAVIOR ANALYSIS
    # =========================================================================

    def analyze_payment_behavior(
        self,
        currency: Optional[str] = None,
    ) -> PaymentBehaviorResult:
        """
        Analyze customer payment behavior patterns.

        Metrics:
        - Customers with payment history
        - Customers with overdue invoices
        - Average late payment delay (days)
        - Percentage of late payments

        Args:
            currency: Optional currency filter

        Returns:
            PaymentBehaviorResult with behavior metrics and recommendations

        Raises:
            ValidationError: If multiple currencies and none specified
        """
        currency = self._resolve_currency_or_raise(Payment.currency, currency)

        # Get customers with payment history
        customer_payments_query = (
            self.db.query(
                Payment.customer_account_id,
                func.count(Payment.id).label("total_payments"),
            )
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.customer_account_id.isnot(None),
            )
        )
        if currency:
            customer_payments_query = customer_payments_query.filter(
                Payment.currency == currency
            )
        customer_payments = customer_payments_query.group_by(
            Payment.customer_account_id
        ).subquery()

        # Count customers by payment frequency
        customers_with_payments = (
            self.db.query(func.count(customer_payments.c.customer_account_id)).scalar() or 0
        )

        # Customers with overdue invoices
        customers_overdue_query = self.db.query(
            func.count(distinct(Invoice.customer_account_id))
        ).filter(Invoice.status == InvoiceStatus.OVERDUE)
        if currency:
            customers_overdue_query = customers_overdue_query.filter(
                Invoice.currency == currency
            )
        customers_overdue = customers_overdue_query.scalar() or 0

        # Average payment delay for late payments
        late_payments_query = (
            self.db.query(
                func.avg(
                    func.date_part("day", Payment.payment_date - Invoice.due_date)
                ).label("avg_delay")
            )
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.payment_date > Invoice.due_date,
            )
        )
        if currency:
            late_payments_query = late_payments_query.filter(
                Payment.currency == currency, Invoice.currency == currency
            )
        late_payments = late_payments_query.scalar() or 0

        # Late payments percentage
        late_count_query = (
            self.db.query(func.count(Payment.id))
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.payment_date > Invoice.due_date,
            )
        )
        total_payments_query = self.db.query(func.count(Payment.id)).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date.isnot(None),
        )
        if currency:
            late_count_query = late_count_query.filter(
                Payment.currency == currency, Invoice.currency == currency
            )
            total_payments_query = total_payments_query.filter(Payment.currency == currency)

        late_count = late_count_query.scalar() or 0
        total_payments = total_payments_query.scalar() or 0
        late_percent = round(late_count / total_payments * 100, 1) if total_payments else 0

        # Build recommendations
        recommendations = []
        if customers_overdue > 0:
            recommendations.append(
                {
                    "priority": (
                        "high" if customers_overdue > customers_with_payments * 0.1 else "medium"
                    ),
                    "issue": f"{customers_overdue} customers have overdue invoices",
                    "action": "Send payment reminders and review collection process",
                }
            )

        return PaymentBehaviorResult(
            summary=PaymentBehaviorInsights(
                customers_with_payments=customers_with_payments,
                customers_with_overdue=customers_overdue,
                avg_late_payment_delay_days=round(float(late_payments), 1),
                late_payments_percent=late_percent,
            ),
            recommendations=recommendations,
        )

    def forecast_revenue(
        self,
        currency: Optional[str] = None,
        projection_months: int = 3,
    ) -> RevenueForecast:
        """
        Generate simple revenue forecast based on current MRR.

        Current implementation assumes stable MRR (no churn/growth modeling).

        Args:
            currency: Optional currency filter
            projection_months: Number of months to project (default 3)

        Returns:
            RevenueForecast with current metrics and projections

        Raises:
            ValidationError: If multiple currencies and none specified
        """
        currency = self._resolve_currency_or_raise(Subscription.currency, currency)

        # Current MRR
        current_mrr = self.calculate_mrr(currency)

        # Calculate growth (compare to 30 days ago - simplified)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        new_subs_query = self.db.query(func.count(Subscription.id)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.start_date >= thirty_days_ago,
        )
        if currency:
            new_subs_query = new_subs_query.filter(Subscription.currency == currency)
        new_subs_30d = new_subs_query.scalar() or 0

        return RevenueForecast(
            current_mrr=current_mrr,
            current_arr=current_mrr * 12,
            new_subscriptions_30d=new_subs_30d,
            month_1_projection=current_mrr,
            month_2_projection=current_mrr,
            month_3_projection=current_mrr,
            quarter_total_projection=current_mrr * 3,
            currency=currency,
            assumptions=[
                "Current MRR remains stable (no churn/upgrade modeled)",
                "Same currency across all subscriptions",
            ],
        )

    # =========================================================================
    # DASHBOARD
    # =========================================================================

    def get_dashboard(self, currency: Optional[str] = None) -> DashboardResult:
        """
        Get comprehensive finance dashboard data.

        Args:
            currency: Optional currency filter

        Returns:
            DashboardResult with revenue, collections, and invoice summary

        Raises:
            ValidationError: If multiple currencies and none specified
        """
        revenue = self.calculate_revenue_metrics(currency)
        collections = self.calculate_collection_metrics(currency=currency)
        invoices_by_status = self.get_invoice_summary_by_status(currency)

        return DashboardResult(
            revenue=revenue,
            collections=collections,
            invoices_by_status=invoices_by_status,
        )
