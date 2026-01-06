"""Sales dashboard service - business logic for sales dashboard and KPIs.

This service encapsulates sales dashboard operations:
- Dashboard summary with KPI cards
- Quote and order metrics
- Fulfillment tracking
- Revenue analytics
- Top products and customers

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sales import (
    SalesOrder,
    SalesOrderStatus,
    Quotation,
    QuotationStatus,
)
from app.models.document_lines import SalesOrderItem, QuotationItem
from app.models.party import Party
from app.services.base import scoped_query
from app.utils.datetime_utils import utc_now

from .dashboard_types import (
    SalesDashboardFilters,
    SalesDashboardSummary,
    SalesKPICard,
    OrderMetrics,
    QuoteSummary,
    AgingChart,
    FulfillmentStatus,
    DeliveryTimeline,
    ProductRevenue,
    CustomerRevenue,
    SalesMonthlyComparison,
    QuoteConversionChart,
    RevenueChart,
)

if TYPE_CHECKING:
    from app.auth import Principal


class SalesDashboardService:
    """Service for Sales dashboard and KPIs.

    All methods are read-only queries. No commits needed.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Main Dashboard
    # -------------------------------------------------------------------------

    def get_dashboard_summary(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> SalesDashboardSummary:
        """Get complete sales dashboard summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            SalesDashboardSummary with all metrics.
        """
        today = date.today()
        period_start = self._get_period_start(
            filters.period if filters else "month", today
        )

        # Quote metrics
        quote_query = self.db.query(Quotation).filter(Quotation.deleted_at.is_(None))
        total_quotes = quote_query.count()

        open_quotes_list = quote_query.filter(
            Quotation.status.in_([QuotationStatus.OPEN, QuotationStatus.REPLIED])
        ).all()
        open_quotes = len(open_quotes_list)
        open_quote_value = sum(q.grand_total or Decimal("0") for q in open_quotes_list)

        # Quote conversion rate
        ordered_quotes = quote_query.filter(
            Quotation.status == QuotationStatus.ORDERED
        ).count()
        closed_quotes = quote_query.filter(
            Quotation.status.in_([QuotationStatus.ORDERED, QuotationStatus.LOST])
        ).count()
        quote_conversion = (
            (ordered_quotes / closed_quotes * 100) if closed_quotes > 0 else 0.0
        )

        # Order metrics
        order_query = self.db.query(SalesOrder)
        if filters and filters.start_date:
            order_query = order_query.filter(
                SalesOrder.transaction_date >= filters.start_date
            )
        if filters and filters.end_date:
            order_query = order_query.filter(
                SalesOrder.transaction_date <= filters.end_date
            )

        total_orders = order_query.count()

        pending_orders_list = order_query.filter(
            SalesOrder.status.in_([
                SalesOrderStatus.DRAFT,
                SalesOrderStatus.TO_DELIVER_AND_BILL,
                SalesOrderStatus.TO_BILL,
                SalesOrderStatus.TO_DELIVER,
            ])
        ).all()
        pending_orders = len(pending_orders_list)
        pending_order_value = sum(
            o.grand_total or Decimal("0") for o in pending_orders_list
        )

        completed_orders = order_query.filter(
            SalesOrder.status.in_([SalesOrderStatus.COMPLETED, SalesOrderStatus.CLOSED])
        ).count()

        # Revenue this period
        period_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.transaction_date >= period_start,
                SalesOrder.status.in_([
                    SalesOrderStatus.COMPLETED,
                    SalesOrderStatus.CLOSED,
                    SalesOrderStatus.TO_BILL,
                ])
            )
            .all()
        )
        total_revenue = sum(o.grand_total or Decimal("0") for o in period_orders)
        avg_order = (
            (total_revenue / len(period_orders)) if period_orders else Decimal("0")
        )

        # Items sold
        items_sold = (
            self.db.query(func.sum(SalesOrderItem.quantity))
            .join(SalesOrder)
            .filter(SalesOrder.transaction_date >= period_start)
            .scalar()
            or 0
        )

        # Fulfillment metrics
        all_active_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.status.notin_([
                    SalesOrderStatus.DRAFT,
                    SalesOrderStatus.CANCELLED,
                ])
            )
            .all()
        )
        if all_active_orders:
            total_delivery = sum(
                float(o.per_delivered or 0) for o in all_active_orders
            )
            total_billing = sum(float(o.per_billed or 0) for o in all_active_orders)
            fulfillment_rate = total_delivery / len(all_active_orders)
            billing_rate = total_billing / len(all_active_orders)
        else:
            fulfillment_rate = 0.0
            billing_rate = 0.0

        # Build KPI cards
        kpi_cards = self._build_kpi_cards(
            open_quotes=open_quotes,
            open_quote_value=open_quote_value,
            pending_orders=pending_orders,
            pending_order_value=pending_order_value,
            total_revenue=total_revenue,
            fulfillment_rate=fulfillment_rate,
        )

        return SalesDashboardSummary(
            total_quotes=total_quotes,
            open_quotes=open_quotes,
            open_quote_value=open_quote_value,
            quote_conversion_rate=quote_conversion,
            total_orders=total_orders,
            pending_orders=pending_orders,
            pending_order_value=pending_order_value,
            completed_orders=completed_orders,
            total_revenue_this_period=total_revenue,
            avg_order_value=avg_order,
            items_sold=int(items_sold),
            fulfillment_rate=fulfillment_rate,
            billing_rate=billing_rate,
            kpi_cards=kpi_cards,
        )

    def _build_kpi_cards(
        self,
        open_quotes: int,
        open_quote_value: Decimal,
        pending_orders: int,
        pending_order_value: Decimal,
        total_revenue: Decimal,
        fulfillment_rate: float,
    ) -> List[SalesKPICard]:
        """Build KPI cards from metrics."""
        return [
            SalesKPICard(
                key="open_quotes",
                title="Open Quotes",
                value=open_quotes,
                formatted_value=str(open_quotes),
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="document-text",
                color="blue",
            ),
            SalesKPICard(
                key="quote_value",
                title="Quote Pipeline",
                value=open_quote_value,
                formatted_value=f"₦{open_quote_value:,.0f}",
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="currency-dollar",
                color="indigo",
            ),
            SalesKPICard(
                key="pending_orders",
                title="Pending Orders",
                value=pending_orders,
                formatted_value=str(pending_orders),
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="shopping-cart",
                color="amber",
            ),
            SalesKPICard(
                key="order_value",
                title="Order Pipeline",
                value=pending_order_value,
                formatted_value=f"₦{pending_order_value:,.0f}",
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="banknotes",
                color="emerald",
            ),
            SalesKPICard(
                key="revenue",
                title="Revenue",
                value=total_revenue,
                formatted_value=f"₦{total_revenue:,.0f}",
                trend=None,
                trend_direction=None,
                comparison_period="this month",
                icon="chart-bar",
                color="green",
            ),
            SalesKPICard(
                key="fulfillment",
                title="Fulfillment Rate",
                value=fulfillment_rate,
                formatted_value=f"{fulfillment_rate:.1f}%",
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="truck",
                color="purple",
            ),
        ]

    # -------------------------------------------------------------------------
    # Order Metrics
    # -------------------------------------------------------------------------

    def get_order_metrics(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> OrderMetrics:
        """Get detailed order metrics.

        Args:
            filters: Optional filter criteria.

        Returns:
            OrderMetrics.
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = date(today.year, today.month, 1)

        query = self.db.query(SalesOrder)
        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)
            if filters.sales_person_id:
                query = query.filter(
                    SalesOrder.sales_partner_id == filters.sales_person_id
                )
            if filters.territory_id:
                query = query.filter(SalesOrder.territory_id == filters.territory_id)

        orders = query.all()
        total_orders = len(orders)

        # Group by status
        by_status: Dict[str, int] = defaultdict(int)
        by_status_value: Dict[str, Decimal] = defaultdict(Decimal)
        for order in orders:
            status_key = order.status.value if hasattr(order.status, 'value') else str(order.status)
            by_status[status_key] += 1
            by_status_value[status_key] += order.grand_total or Decimal("0")

        # Orders this week/month
        orders_this_week = len([
            o for o in orders
            if o.transaction_date and o.transaction_date >= week_start
        ])
        orders_this_month = len([
            o for o in orders
            if o.transaction_date and o.transaction_date >= month_start
        ])

        # On-time delivery rate
        completed_with_delivery = [
            o for o in orders
            if o.status in [SalesOrderStatus.COMPLETED, SalesOrderStatus.CLOSED]
            and o.delivery_date
        ]
        on_time = len([
            o for o in completed_with_delivery
            if o.transaction_date and o.delivery_date
            and o.delivery_date <= (o.transaction_date + timedelta(days=7))  # Assume 7-day SLA
        ])
        on_time_rate = (
            (on_time / len(completed_with_delivery) * 100)
            if completed_with_delivery
            else 0.0
        )

        return OrderMetrics(
            total_orders=total_orders,
            by_status=dict(by_status),
            by_status_value=dict(by_status_value),
            orders_this_week=orders_this_week,
            orders_this_month=orders_this_month,
            avg_processing_days=None,  # Would need processing time tracking
            on_time_rate=on_time_rate,
        )

    # -------------------------------------------------------------------------
    # Quote Summary
    # -------------------------------------------------------------------------

    def get_quote_summary(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> QuoteSummary:
        """Get quotation summary for dashboard.

        Args:
            filters: Optional filter criteria.

        Returns:
            QuoteSummary.
        """
        today = date.today()
        expiring_soon_date = today + timedelta(days=7)

        query = self.db.query(Quotation).filter(Quotation.deleted_at.is_(None))
        if filters:
            if filters.start_date:
                query = query.filter(Quotation.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(Quotation.transaction_date <= filters.end_date)

        quotes = query.all()
        total = len(quotes)

        open_quotes = [
            q for q in quotes
            if q.status in [QuotationStatus.OPEN, QuotationStatus.REPLIED]
        ]
        ordered = [q for q in quotes if q.status == QuotationStatus.ORDERED]
        lost = [q for q in quotes if q.status == QuotationStatus.LOST]
        expired = [q for q in quotes if q.status == QuotationStatus.EXPIRED]

        open_value = sum(q.grand_total or Decimal("0") for q in open_quotes)
        ordered_value = sum(q.grand_total or Decimal("0") for q in ordered)

        # Conversion rate
        closed = len(ordered) + len(lost)
        conversion = (len(ordered) / closed * 100) if closed > 0 else 0.0

        # Expiring soon
        expiring = len([
            q for q in open_quotes
            if q.valid_till and q.valid_till <= expiring_soon_date
        ])

        return QuoteSummary(
            total_quotes=total,
            open_quotes=len(open_quotes),
            ordered_quotes=len(ordered),
            lost_quotes=len(lost),
            expired_quotes=len(expired),
            open_value=open_value,
            ordered_value=ordered_value,
            conversion_rate=conversion,
            avg_days_to_convert=None,  # Would need timestamp tracking
            expiring_soon=expiring,
        )

    def get_quote_aging_chart(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> AgingChart:
        """Get quote aging chart data.

        Args:
            filters: Optional filter criteria.

        Returns:
            AgingChart.
        """
        today = date.today()

        quotes = (
            self.db.query(Quotation)
            .filter(
                Quotation.deleted_at.is_(None),
                Quotation.status.in_([QuotationStatus.OPEN, QuotationStatus.REPLIED]),
            )
            .all()
        )

        buckets = [
            {"label": "0-7 days", "min_days": 0, "max_days": 7, "count": 0, "value": Decimal("0"), "color": "green"},
            {"label": "8-14 days", "min_days": 8, "max_days": 14, "count": 0, "value": Decimal("0"), "color": "blue"},
            {"label": "15-30 days", "min_days": 15, "max_days": 30, "count": 0, "value": Decimal("0"), "color": "amber"},
            {"label": "31-60 days", "min_days": 31, "max_days": 60, "count": 0, "value": Decimal("0"), "color": "orange"},
            {"label": "60+ days", "min_days": 61, "max_days": 9999, "count": 0, "value": Decimal("0"), "color": "red"},
        ]

        total_days = 0
        for quote in quotes:
            if quote.transaction_date:
                age = (today - quote.transaction_date).days
                total_days += age
                for bucket in buckets:
                    if bucket["min_days"] <= age <= bucket["max_days"]:
                        bucket["count"] += 1
                        bucket["value"] += quote.grand_total or Decimal("0")
                        break

        total_count = len(quotes)
        total_value = sum(q.grand_total or Decimal("0") for q in quotes)
        avg_age = (total_days / total_count) if total_count > 0 else 0.0

        return AgingChart(
            entity_type="quotation",
            buckets=buckets,
            total_count=total_count,
            total_value=total_value,
            avg_age_days=avg_age,
        )

    # -------------------------------------------------------------------------
    # Fulfillment
    # -------------------------------------------------------------------------

    def get_fulfillment_status(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> FulfillmentStatus:
        """Get order fulfillment status breakdown.

        Args:
            filters: Optional filter criteria.

        Returns:
            FulfillmentStatus.
        """
        query = self.db.query(SalesOrder).filter(
            SalesOrder.status.notin_([
                SalesOrderStatus.DRAFT,
                SalesOrderStatus.CANCELLED,
            ])
        )

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        orders = query.all()
        total = len(orders)

        # Delivery breakdown
        not_delivered = len([o for o in orders if (o.per_delivered or 0) == 0])
        partially_delivered = len([
            o for o in orders
            if 0 < (o.per_delivered or 0) < 100
        ])
        fully_delivered = len([o for o in orders if (o.per_delivered or 0) >= 100])

        # Billing breakdown
        not_billed = len([o for o in orders if (o.per_billed or 0) == 0])
        partially_billed = len([
            o for o in orders
            if 0 < (o.per_billed or 0) < 100
        ])
        fully_billed = len([o for o in orders if (o.per_billed or 0) >= 100])

        # Overall progress
        total_delivery = sum(float(o.per_delivered or 0) for o in orders)
        total_billing = sum(float(o.per_billed or 0) for o in orders)
        delivery_progress = (total_delivery / total) if total > 0 else 0.0
        billing_progress = (total_billing / total) if total > 0 else 0.0

        # Pending items (top 10)
        pending_delivery_orders = sorted(
            [o for o in orders if (o.per_delivered or 0) < 100],
            key=lambda x: x.grand_total or Decimal("0"),
            reverse=True,
        )[:10]

        pending_delivery = [
            {
                "id": o.id,
                "customer": o.customer_name or o.customer,
                "amount": o.grand_total,
                "days_pending": (
                    (date.today() - o.transaction_date).days
                    if o.transaction_date
                    else 0
                ),
            }
            for o in pending_delivery_orders
        ]

        pending_billing_orders = sorted(
            [o for o in orders if (o.per_billed or 0) < 100],
            key=lambda x: x.grand_total or Decimal("0"),
            reverse=True,
        )[:10]

        pending_billing = [
            {
                "id": o.id,
                "customer": o.customer_name or o.customer,
                "amount": o.grand_total,
                "days_pending": (
                    (date.today() - o.transaction_date).days
                    if o.transaction_date
                    else 0
                ),
            }
            for o in pending_billing_orders
        ]

        return FulfillmentStatus(
            total_orders=total,
            not_delivered=not_delivered,
            partially_delivered=partially_delivered,
            fully_delivered=fully_delivered,
            not_billed=not_billed,
            partially_billed=partially_billed,
            fully_billed=fully_billed,
            delivery_progress=delivery_progress,
            billing_progress=billing_progress,
            pending_delivery=pending_delivery,
            pending_billing=pending_billing,
        )

    def get_delivery_timeline(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> DeliveryTimeline:
        """Get delivery timeline for upcoming deliveries.

        Args:
            filters: Optional filter criteria.

        Returns:
            DeliveryTimeline.
        """
        today = date.today()
        week_end = today + timedelta(days=7)
        month_end = date(
            today.year + (1 if today.month == 12 else 0),
            (today.month % 12) + 1,
            1
        ) - timedelta(days=1)

        orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.status.in_([
                    SalesOrderStatus.TO_DELIVER_AND_BILL,
                    SalesOrderStatus.TO_DELIVER,
                ]),
                SalesOrder.delivery_date.isnot(None),
            )
            .all()
        )

        upcoming = []
        overdue = []
        today_count = 0
        week_count = 0
        month_count = 0

        for order in orders:
            if order.delivery_date:
                item = {
                    "id": order.id,
                    "customer": order.customer_name or order.customer,
                    "delivery_date": order.delivery_date,
                    "amount": order.grand_total,
                }

                if order.delivery_date < today:
                    overdue.append({
                        "id": order.id,
                        "customer": order.customer_name or order.customer,
                        "expected_date": order.delivery_date,
                        "days_late": (today - order.delivery_date).days,
                    })
                else:
                    upcoming.append(item)
                    if order.delivery_date == today:
                        today_count += 1
                    if order.delivery_date <= week_end:
                        week_count += 1
                    if order.delivery_date <= month_end:
                        month_count += 1

        # Sort upcoming by date
        upcoming.sort(key=lambda x: x["delivery_date"])
        overdue.sort(key=lambda x: x["days_late"], reverse=True)

        return DeliveryTimeline(
            upcoming_deliveries=upcoming[:10],
            overdue_deliveries=overdue[:10],
            today_count=today_count,
            this_week_count=week_count,
            this_month_count=month_count,
        )

    # -------------------------------------------------------------------------
    # Revenue Analytics
    # -------------------------------------------------------------------------

    def get_revenue_by_product(
        self,
        filters: Optional[SalesDashboardFilters] = None,
        limit: int = 10,
    ) -> List[ProductRevenue]:
        """Get top products by revenue.

        Args:
            filters: Optional filter criteria.
            limit: Maximum products to return.

        Returns:
            List of ProductRevenue.
        """
        query = (
            self.db.query(
                SalesOrderItem.item_code,
                SalesOrderItem.item_name,
                SalesOrderItem.item_group,
                func.sum(SalesOrderItem.quantity).label("quantity"),
                func.sum(SalesOrderItem.amount).label("revenue"),
                func.count(func.distinct(SalesOrderItem.sales_order_id)).label("order_count"),
            )
            .join(SalesOrder)
            .filter(
                SalesOrder.status.in_([
                    SalesOrderStatus.COMPLETED,
                    SalesOrderStatus.CLOSED,
                    SalesOrderStatus.TO_BILL,
                ])
            )
            .group_by(
                SalesOrderItem.item_code,
                SalesOrderItem.item_name,
                SalesOrderItem.item_group,
            )
            .order_by(func.sum(SalesOrderItem.amount).desc())
        )

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        results = query.limit(limit).all()

        total_revenue = sum(r.revenue or Decimal("0") for r in results)

        products = []
        for i, r in enumerate(results, 1):
            pct = float((r.revenue or Decimal("0")) / total_revenue * 100) if total_revenue > 0 else 0.0
            products.append(ProductRevenue(
                rank=i,
                item_id=0,  # No item_id in denormalized line
                item_code=r.item_code or "",
                item_name=r.item_name or "",
                item_group=r.item_group,
                quantity_sold=r.quantity or Decimal("0"),
                revenue=r.revenue or Decimal("0"),
                order_count=r.order_count or 0,
                percentage_of_total=pct,
            ))

        return products

    def get_revenue_by_customer(
        self,
        filters: Optional[SalesDashboardFilters] = None,
        limit: int = 10,
    ) -> List[CustomerRevenue]:
        """Get top customers by revenue.

        Args:
            filters: Optional filter criteria.
            limit: Maximum customers to return.

        Returns:
            List of CustomerRevenue.
        """
        query = (
                self.db.query(
                    SalesOrder.party_id,
                    SalesOrder.customer,
                    SalesOrder.customer_name,
                    func.count(SalesOrder.id).label("order_count"),
                    func.sum(SalesOrder.grand_total).label("revenue"),
                    func.max(SalesOrder.transaction_date).label("last_order"),
                )
            .filter(
                SalesOrder.status.in_([
                    SalesOrderStatus.COMPLETED,
                    SalesOrderStatus.CLOSED,
                    SalesOrderStatus.TO_BILL,
                ])
            )
            .group_by(SalesOrder.party_id, SalesOrder.customer, SalesOrder.customer_name)
            .order_by(func.sum(SalesOrder.grand_total).desc())
        )

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        results = query.limit(limit).all()

        total_revenue = sum(r.revenue or Decimal("0") for r in results)

        customers = []
        for i, r in enumerate(results, 1):
            revenue = r.revenue or Decimal("0")
            order_count = r.order_count or 0
            avg_value = (revenue / order_count) if order_count > 0 else Decimal("0")
            pct = float(revenue / total_revenue * 100) if total_revenue > 0 else 0.0

            customers.append(CustomerRevenue(
                rank=i,
                party_id=r.party_id or 0,
                party_name=r.customer_name or r.customer or "",
                order_count=order_count,
                revenue=revenue,
                avg_order_value=avg_value,
                percentage_of_total=pct,
                last_order_date=r.last_order,
            ))

        return customers

    def get_monthly_comparison(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> SalesMonthlyComparison:
        """Get month-over-month sales comparison.

        Args:
            filters: Optional filter criteria.

        Returns:
            SalesMonthlyComparison.
        """
        today = date.today()
        current_month_start = date(today.year, today.month, 1)

        if today.month == 1:
            prev_month_start = date(today.year - 1, 12, 1)
            prev_month_end = date(today.year - 1, 12, 31)
        else:
            prev_month_start = date(today.year, today.month - 1, 1)
            prev_month_end = current_month_start - timedelta(days=1)

        # Current month
        current_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.transaction_date >= current_month_start,
                SalesOrder.status.notin_([
                    SalesOrderStatus.DRAFT,
                    SalesOrderStatus.CANCELLED,
                ])
            )
            .all()
        )
        current_count = len(current_orders)
        current_revenue = sum(o.grand_total or Decimal("0") for o in current_orders)
        current_avg = (current_revenue / current_count) if current_count > 0 else Decimal("0")

        # Previous month
        prev_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.transaction_date >= prev_month_start,
                SalesOrder.transaction_date <= prev_month_end,
                SalesOrder.status.notin_([
                    SalesOrderStatus.DRAFT,
                    SalesOrderStatus.CANCELLED,
                ])
            )
            .all()
        )
        prev_count = len(prev_orders)
        prev_revenue = sum(o.grand_total or Decimal("0") for o in prev_orders)
        prev_avg = (prev_revenue / prev_count) if prev_count > 0 else Decimal("0")

        # Calculate changes
        order_change = current_count - prev_count
        order_change_pct = (
            (order_change / prev_count * 100) if prev_count > 0 else 0.0
        )

        revenue_change = current_revenue - prev_revenue
        revenue_change_pct = (
            float((revenue_change / prev_revenue) * 100) if prev_revenue > 0 else 0.0
        )

        return SalesMonthlyComparison(
            current_month=current_month_start.strftime("%Y-%m"),
            current_orders=current_count,
            current_revenue=current_revenue,
            current_avg_value=current_avg,
            previous_month=prev_month_start.strftime("%Y-%m"),
            previous_orders=prev_count,
            previous_revenue=prev_revenue,
            previous_avg_value=prev_avg,
            order_change=order_change,
            order_change_percent=order_change_pct,
            revenue_change=revenue_change,
            revenue_change_percent=revenue_change_pct,
        )

    # -------------------------------------------------------------------------
    # Charts
    # -------------------------------------------------------------------------

    def get_quote_conversion_chart(
        self,
        filters: Optional[SalesDashboardFilters] = None,
    ) -> QuoteConversionChart:
        """Get quote conversion funnel chart data.

        Args:
            filters: Optional filter criteria.

        Returns:
            QuoteConversionChart.
        """
        query = self.db.query(Quotation).filter(Quotation.deleted_at.is_(None))

        if filters:
            if filters.start_date:
                query = query.filter(Quotation.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(Quotation.transaction_date <= filters.end_date)

        quotes = query.all()
        total = len(quotes)

        draft = [q for q in quotes if q.status == QuotationStatus.DRAFT]
        open_q = [q for q in quotes if q.status == QuotationStatus.OPEN]
        replied = [q for q in quotes if q.status == QuotationStatus.REPLIED]
        ordered = [q for q in quotes if q.status == QuotationStatus.ORDERED]

        levels = []
        if total > 0:
            levels.append({
                "name": "Draft",
                "count": len(draft),
                "value": sum(q.grand_total or Decimal("0") for q in draft),
                "conversion_rate": 100.0,
            })

        if open_q:
            levels.append({
                "name": "Open",
                "count": len(open_q),
                "value": sum(q.grand_total or Decimal("0") for q in open_q),
                "conversion_rate": (len(open_q) / total * 100) if total > 0 else 0,
            })

        if replied:
            levels.append({
                "name": "Replied",
                "count": len(replied),
                "value": sum(q.grand_total or Decimal("0") for q in replied),
                "conversion_rate": (len(replied) / total * 100) if total > 0 else 0,
            })

        if ordered:
            levels.append({
                "name": "Ordered",
                "count": len(ordered),
                "value": sum(q.grand_total or Decimal("0") for q in ordered),
                "conversion_rate": (len(ordered) / total * 100) if total > 0 else 0,
            })

        overall = (len(ordered) / total * 100) if total > 0 else 0.0

        return QuoteConversionChart(
            levels=levels,
            overall_conversion=overall,
            avg_days_in_each_stage={},
        )

    def get_revenue_chart(
        self,
        filters: Optional[SalesDashboardFilters] = None,
        period: str = "monthly",
    ) -> RevenueChart:
        """Get revenue chart data over time.

        Args:
            filters: Optional filter criteria.
            period: Grouping period.

        Returns:
            RevenueChart.
        """
        query = self.db.query(SalesOrder).filter(
            SalesOrder.status.in_([
                SalesOrderStatus.COMPLETED,
                SalesOrderStatus.CLOSED,
                SalesOrderStatus.TO_BILL,
            ])
        )

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        orders = query.all()

        # Group by period
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"revenue": Decimal("0"), "orders": 0}
        )

        for order in orders:
            if order.transaction_date:
                if period == "monthly":
                    key = order.transaction_date.strftime("%Y-%m")
                elif period == "weekly":
                    key = order.transaction_date.strftime("%Y-W%W")
                else:
                    key = order.transaction_date.strftime("%Y-%m-%d")

                grouped[key]["revenue"] += order.grand_total or Decimal("0")
                grouped[key]["orders"] += 1

        data_points = []
        for period_key in sorted(grouped.keys()):
            data = grouped[period_key]
            avg = (
                data["revenue"] / data["orders"]
            ) if data["orders"] > 0 else Decimal("0")
            data_points.append({
                "period": period_key,
                "revenue": data["revenue"],
                "orders": data["orders"],
                "avg_value": avg,
            })

        total = sum(d["revenue"] for d in data_points)
        avg_rev = (total / len(data_points)) if data_points else Decimal("0")

        # Trend
        if len(data_points) >= 2:
            recent = data_points[-1]["revenue"]
            previous = data_points[-2]["revenue"]
            if recent > previous:
                direction = "up"
                pct = float((recent - previous) / previous * 100) if previous > 0 else 0
            elif recent < previous:
                direction = "down"
                pct = float((previous - recent) / previous * 100) if previous > 0 else 0
            else:
                direction = "stable"
                pct = 0.0
        else:
            direction = "stable"
            pct = 0.0

        return RevenueChart(
            period_type=period,
            data_points=data_points,
            total_revenue=total,
            avg_revenue=avg_rev,
            trend_direction=direction,
            trend_percentage=pct,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_period_start(self, period: str, reference_date: date) -> date:
        """Get start date for a period."""
        if period == "day":
            return reference_date
        elif period == "week":
            return reference_date - timedelta(days=reference_date.weekday())
        elif period == "month":
            return date(reference_date.year, reference_date.month, 1)
        elif period == "quarter":
            quarter = (reference_date.month - 1) // 3
            return date(reference_date.year, quarter * 3 + 1, 1)
        elif period == "year":
            return date(reference_date.year, 1, 1)
        return date(reference_date.year, reference_date.month, 1)
