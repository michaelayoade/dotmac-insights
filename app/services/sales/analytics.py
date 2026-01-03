"""Sales analytics service - business logic for sales reporting and analytics.

This service encapsulates Sales analytics operations:
- Quote analytics and conversion
- Order analytics and fulfillment
- Product/item performance
- Customer revenue analysis
- Trend analysis

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.sales import (
    Quotation,
    QuotationStatus,
    QuotationItem,
    SalesOrder,
    SalesOrderStatus,
    SalesOrderItem,
)
from app.models.party import Party
from app.services.base import scoped_query

from .analytics_types import (
    SalesAnalyticsFilters,
    QuoteAnalytics,
    OrderAnalytics,
    FulfillmentMetrics,
    ItemSalesData,
    CustomerSalesData,
    SalesTrendPoint,
    ProductMixItem,
    SalesAgingAnalysis,
    MonthlyComparison,
    RevenueByPeriod,
)

if TYPE_CHECKING:
    from app.auth import Principal


class SalesAnalyticsService:
    """Service for sales analytics and reporting.

    All methods are read-only queries. No commits needed.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Quote Analytics
    # -------------------------------------------------------------------------

    def get_quote_analytics(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> QuoteAnalytics:
        """Get quotation analytics summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            QuoteAnalytics with quote metrics.
        """
        query = scoped_query(self.db.query(Quotation), self.principal)

        if filters:
            if filters.start_date:
                query = query.filter(Quotation.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(Quotation.transaction_date <= filters.end_date)
            if filters.party_id:
                query = query.filter(Quotation.party_id == filters.party_id)
            if filters.sales_person_id:
                query = query.filter(Quotation.sales_person_id == filters.sales_person_id)

        quotes = query.all()
        total = len(quotes)

        # Count by status
        by_status: Dict[str, int] = defaultdict(int)
        open_count = 0
        converted_count = 0
        lost_count = 0
        expired_count = 0

        total_value = Decimal("0")
        converted_value = Decimal("0")

        for q in quotes:
            status = q.status.value if hasattr(q.status, 'value') else str(q.status)
            by_status[status] += 1
            total_value += q.grand_total or Decimal("0")

            if q.status == QuotationStatus.OPEN:
                open_count += 1
            elif q.status == QuotationStatus.ORDERED:
                converted_count += 1
                converted_value += q.grand_total or Decimal("0")
            elif q.status == QuotationStatus.LOST:
                lost_count += 1
            elif q.status == QuotationStatus.EXPIRED:
                expired_count += 1

        conversion_rate = (converted_count / total * 100) if total > 0 else 0.0
        avg_value = (total_value / total) if total > 0 else Decimal("0")

        return QuoteAnalytics(
            total_quotes=total,
            open_quotes=open_count,
            converted_quotes=converted_count,
            lost_quotes=lost_count,
            expired_quotes=expired_count,
            total_value=total_value,
            converted_value=converted_value,
            conversion_rate=conversion_rate,
            avg_quote_value=avg_value,
            avg_time_to_convert_days=None,  # Would need order creation tracking
            by_status=dict(by_status),
        )

    def get_quote_conversion_rate(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> float:
        """Get quotation-to-order conversion rate.

        Args:
            filters: Optional filter criteria.

        Returns:
            Conversion rate as percentage.
        """
        analytics = self.get_quote_analytics(filters)
        return analytics.conversion_rate

    def get_quote_aging(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> SalesAgingAnalysis:
        """Get quotation aging analysis.

        Args:
            filters: Optional filter criteria.

        Returns:
            SalesAgingAnalysis with aging buckets.
        """
        query = scoped_query(self.db.query(Quotation), self.principal)
        query = query.filter(Quotation.status == QuotationStatus.OPEN)

        if filters and filters.sales_person_id:
            query = query.filter(Quotation.sales_person_id == filters.sales_person_id)

        quotes = query.all()
        today = date.today()

        buckets = [
            {"label": "0-7 days", "min_days": 0, "max_days": 7, "count": 0, "value": Decimal("0")},
            {"label": "8-14 days", "min_days": 8, "max_days": 14, "count": 0, "value": Decimal("0")},
            {"label": "15-30 days", "min_days": 15, "max_days": 30, "count": 0, "value": Decimal("0")},
            {"label": "30+ days", "min_days": 31, "max_days": 9999, "count": 0, "value": Decimal("0")},
        ]

        total_value = Decimal("0")
        overdue_count = 0
        overdue_value = Decimal("0")

        for q in quotes:
            if q.transaction_date:
                age_days = (today - q.transaction_date).days
                quote_val = q.grand_total or Decimal("0")
                total_value += quote_val

                for bucket in buckets:
                    if bucket["min_days"] <= age_days <= bucket["max_days"]:
                        bucket["count"] += 1
                        bucket["value"] += quote_val
                        break

                # Check if past valid_till
                if q.valid_till and q.valid_till < today:
                    overdue_count += 1
                    overdue_value += quote_val

        return SalesAgingAnalysis(
            entity_type="quotation",
            total_count=len(quotes),
            total_value=total_value,
            buckets=buckets,
            overdue_count=overdue_count,
            overdue_value=overdue_value,
        )

    # -------------------------------------------------------------------------
    # Order Analytics
    # -------------------------------------------------------------------------

    def get_order_analytics(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> OrderAnalytics:
        """Get sales order analytics summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            OrderAnalytics with order metrics.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)
            if filters.party_id:
                query = query.filter(SalesOrder.party_id == filters.party_id)
            if filters.sales_person_id:
                query = query.filter(SalesOrder.sales_person_id == filters.sales_person_id)

        orders = query.all()
        total = len(orders)

        by_status: Dict[str, int] = defaultdict(int)
        pending_count = 0
        delivered_count = 0
        cancelled_count = 0

        total_value = Decimal("0")
        delivered_value = Decimal("0")

        for o in orders:
            status = o.status.value if hasattr(o.status, 'value') else str(o.status)
            by_status[status] += 1
            total_value += o.grand_total or Decimal("0")

            if o.status == SalesOrderStatus.CANCELLED:
                cancelled_count += 1
            elif o.status == SalesOrderStatus.COMPLETED:
                delivered_count += 1
                delivered_value += o.grand_total or Decimal("0")
            else:
                pending_count += 1

        fulfillment_rate = (delivered_count / total * 100) if total > 0 else 0.0
        avg_value = (total_value / total) if total > 0 else Decimal("0")

        return OrderAnalytics(
            total_orders=total,
            pending_orders=pending_count,
            delivered_orders=delivered_count,
            cancelled_orders=cancelled_count,
            total_value=total_value,
            delivered_value=delivered_value,
            avg_order_value=avg_value,
            fulfillment_rate=fulfillment_rate,
            avg_fulfillment_days=None,  # Would need delivery tracking
            by_status=dict(by_status),
        )

    def get_fulfillment_metrics(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> FulfillmentMetrics:
        """Get order fulfillment metrics.

        Args:
            filters: Optional filter criteria.

        Returns:
            FulfillmentMetrics with delivery/billing stats.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)
        query = query.filter(SalesOrder.status != SalesOrderStatus.CANCELLED)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        orders = query.all()
        total = len(orders)

        fully_delivered = 0
        partially_delivered = 0
        not_delivered = 0
        fully_billed = 0
        partially_billed = 0
        not_billed = 0

        total_delivery_percent = Decimal("0")
        total_billing_percent = Decimal("0")

        for o in orders:
            per_delivered = o.per_delivered or Decimal("0")
            per_billed = o.per_billed or Decimal("0")

            total_delivery_percent += per_delivered
            total_billing_percent += per_billed

            if per_delivered >= 100:
                fully_delivered += 1
            elif per_delivered > 0:
                partially_delivered += 1
            else:
                not_delivered += 1

            if per_billed >= 100:
                fully_billed += 1
            elif per_billed > 0:
                partially_billed += 1
            else:
                not_billed += 1

        avg_delivery = float(total_delivery_percent / total) if total > 0 else 0.0
        avg_billing = float(total_billing_percent / total) if total > 0 else 0.0

        return FulfillmentMetrics(
            total_orders=total,
            fully_delivered=fully_delivered,
            partially_delivered=partially_delivered,
            not_delivered=not_delivered,
            fully_billed=fully_billed,
            partially_billed=partially_billed,
            not_billed=not_billed,
            avg_delivery_percent=avg_delivery,
            avg_billing_percent=avg_billing,
            on_time_delivery_rate=0.0,  # Would need delivery date tracking
        )

    def get_order_value_trend(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
        period: str = "monthly",
    ) -> List[SalesTrendPoint]:
        """Get order value trend over time.

        Args:
            filters: Optional filter criteria.
            period: Grouping period (daily, weekly, monthly).

        Returns:
            List of SalesTrendPoint.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)
        query = query.filter(SalesOrder.status != SalesOrderStatus.CANCELLED)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        orders = query.all()

        # Group by period
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "value": Decimal("0"), "quantity": Decimal("0")}
        )

        for o in orders:
            if o.transaction_date:
                if period == "monthly":
                    key = o.transaction_date.strftime("%Y-%m")
                elif period == "weekly":
                    key = o.transaction_date.strftime("%Y-W%W")
                else:  # daily
                    key = o.transaction_date.strftime("%Y-%m-%d")

                grouped[key]["count"] += 1
                grouped[key]["value"] += o.grand_total or Decimal("0")

        results = []
        for period_key in sorted(grouped.keys()):
            data = grouped[period_key]
            results.append(SalesTrendPoint(
                period=period_key,
                period_type=period,
                order_count=data["count"],
                order_value=data["value"],
                item_quantity=data["quantity"],
            ))

        return results

    # -------------------------------------------------------------------------
    # Product Analytics
    # -------------------------------------------------------------------------

    def get_top_selling_items(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
        limit: int = 10,
    ) -> List[ItemSalesData]:
        """Get top selling items by revenue.

        Args:
            filters: Optional filter criteria.
            limit: Maximum items to return.

        Returns:
            List of ItemSalesData sorted by revenue.
        """
        # Query order items with order filter
        query = self.db.query(SalesOrderItem).join(SalesOrder)
        query = scoped_query(query, self.principal, entity=SalesOrder)
        query = query.filter(SalesOrder.status != SalesOrderStatus.CANCELLED)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)
            if filters.party_id:
                query = query.filter(SalesOrder.party_id == filters.party_id)
            if filters.item_group:
                query = query.filter(SalesOrderItem.item_group == filters.item_group)

        items = query.all()

        # Group by item
        by_item: Dict[str, Dict[str, Any]] = {}
        for item in items:
            key = item.item_code or str(item.item_id)
            if key not in by_item:
                by_item[key] = {
                    "item_id": item.item_id,
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "item_group": item.item_group,
                    "quantity": Decimal("0"),
                    "revenue": Decimal("0"),
                    "order_ids": set(),
                }
            by_item[key]["quantity"] += item.qty or Decimal("0")
            by_item[key]["revenue"] += item.amount or Decimal("0")
            by_item[key]["order_ids"].add(item.sales_order_id)

        results = []
        for data in by_item.values():
            order_count = len(data["order_ids"])
            avg_price = (data["revenue"] / data["quantity"]) if data["quantity"] > 0 else Decimal("0")

            results.append(ItemSalesData(
                item_id=data["item_id"] or 0,
                item_code=data["item_code"] or "",
                item_name=data["item_name"] or "",
                item_group=data["item_group"],
                quantity_sold=data["quantity"],
                total_revenue=data["revenue"],
                order_count=order_count,
                avg_selling_price=avg_price,
            ))

        # Sort by revenue and assign ranks
        results.sort(key=lambda x: x.total_revenue, reverse=True)
        for i, item in enumerate(results[:limit], 1):
            item.rank = i

        return results[:limit]

    def get_product_mix(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> List[ProductMixItem]:
        """Get product mix breakdown by item group.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of ProductMixItem by group.
        """
        query = self.db.query(SalesOrderItem).join(SalesOrder)
        query = scoped_query(query, self.principal, entity=SalesOrder)
        query = query.filter(SalesOrder.status != SalesOrderStatus.CANCELLED)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)

        items = query.all()

        # Group by item_group
        by_group: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"revenue": Decimal("0"), "quantity": Decimal("0"), "order_ids": set()}
        )

        total_revenue = Decimal("0")

        for item in items:
            group = item.item_group or "Uncategorized"
            by_group[group]["revenue"] += item.amount or Decimal("0")
            by_group[group]["quantity"] += item.qty or Decimal("0")
            by_group[group]["order_ids"].add(item.sales_order_id)
            total_revenue += item.amount or Decimal("0")

        results = []
        for group, data in by_group.items():
            pct = float(data["revenue"] / total_revenue * 100) if total_revenue > 0 else 0.0
            results.append(ProductMixItem(
                item_group=group,
                revenue=data["revenue"],
                quantity=data["quantity"],
                order_count=len(data["order_ids"]),
                percentage_of_total=pct,
            ))

        # Sort by revenue
        results.sort(key=lambda x: x.revenue, reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Customer Analytics
    # -------------------------------------------------------------------------

    def get_revenue_by_customer(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
        limit: int = 10,
    ) -> List[CustomerSalesData]:
        """Get revenue breakdown by customer.

        Args:
            filters: Optional filter criteria.
            limit: Maximum customers to return.

        Returns:
            List of CustomerSalesData sorted by revenue.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)
        query = query.filter(SalesOrder.status != SalesOrderStatus.CANCELLED)

        if filters:
            if filters.start_date:
                query = query.filter(SalesOrder.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(SalesOrder.transaction_date <= filters.end_date)
            if filters.party_ids:
                query = query.filter(SalesOrder.party_id.in_(filters.party_ids))

        orders = query.all()

        # Group by party
        by_party: Dict[int, Dict[str, Any]] = {}
        for o in orders:
            if o.party_id:
                if o.party_id not in by_party:
                    by_party[o.party_id] = {
                        "count": 0,
                        "revenue": Decimal("0"),
                        "first_date": None,
                        "last_date": None,
                    }
                by_party[o.party_id]["count"] += 1
                by_party[o.party_id]["revenue"] += o.grand_total or Decimal("0")

                if o.transaction_date:
                    if not by_party[o.party_id]["first_date"] or o.transaction_date < by_party[o.party_id]["first_date"]:
                        by_party[o.party_id]["first_date"] = o.transaction_date
                    if not by_party[o.party_id]["last_date"] or o.transaction_date > by_party[o.party_id]["last_date"]:
                        by_party[o.party_id]["last_date"] = o.transaction_date

        # Get party names
        party_ids = list(by_party.keys())
        parties = {}
        if party_ids:
            party_records = self.db.query(Party).filter(Party.id.in_(party_ids)).all()
            parties = {p.id: p.name for p in party_records}

        results = []
        for party_id, data in by_party.items():
            avg_value = (data["revenue"] / data["count"]) if data["count"] > 0 else Decimal("0")
            results.append(CustomerSalesData(
                party_id=party_id,
                party_name=parties.get(party_id, f"Party {party_id}"),
                order_count=data["count"],
                total_revenue=data["revenue"],
                avg_order_value=avg_value,
                first_order_date=data["first_date"],
                last_order_date=data["last_date"],
            ))

        # Sort by revenue and assign ranks
        results.sort(key=lambda x: x.total_revenue, reverse=True)
        for i, cust in enumerate(results[:limit], 1):
            cust.rank = i

        return results[:limit]

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------

    def get_monthly_comparison(
        self,
        filters: Optional[SalesAnalyticsFilters] = None,
    ) -> MonthlyComparison:
        """Get month-over-month comparison.

        Args:
            filters: Optional filter criteria.

        Returns:
            MonthlyComparison with current vs previous month.
        """
        today = date.today()
        current_month_start = date(today.year, today.month, 1)
        if today.month == 1:
            prev_month_start = date(today.year - 1, 12, 1)
        else:
            prev_month_start = date(today.year, today.month - 1, 1)
        prev_month_end = current_month_start - timedelta(days=1)

        # Current month
        current_query = scoped_query(self.db.query(SalesOrder), self.principal)
        current_query = current_query.filter(
            SalesOrder.status != SalesOrderStatus.CANCELLED,
            SalesOrder.transaction_date >= current_month_start,
            SalesOrder.transaction_date <= today,
        )
        current_orders = current_query.all()
        current_value = sum(o.grand_total or Decimal("0") for o in current_orders)
        current_count = len(current_orders)

        # Previous month
        prev_query = scoped_query(self.db.query(SalesOrder), self.principal)
        prev_query = prev_query.filter(
            SalesOrder.status != SalesOrderStatus.CANCELLED,
            SalesOrder.transaction_date >= prev_month_start,
            SalesOrder.transaction_date <= prev_month_end,
        )
        prev_orders = prev_query.all()
        prev_value = sum(o.grand_total or Decimal("0") for o in prev_orders)
        prev_count = len(prev_orders)

        # Calculate changes
        value_change = current_value - prev_value
        value_pct = float((value_change / prev_value * 100) if prev_value > 0 else 0)
        count_change = current_count - prev_count
        count_pct = float((count_change / prev_count * 100) if prev_count > 0 else 0)

        return MonthlyComparison(
            current_month=current_month_start.strftime("%Y-%m"),
            current_value=current_value,
            current_count=current_count,
            previous_month=prev_month_start.strftime("%Y-%m"),
            previous_value=prev_value,
            previous_count=prev_count,
            value_change=value_change,
            value_change_percent=value_pct,
            count_change=count_change,
            count_change_percent=count_pct,
        )
