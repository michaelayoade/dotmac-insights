"""Service Transaction service - billing for services rendered.

This service handles the financial lifecycle of field services:
- Generate invoices from completed service orders
- Track billable vs non-billable services
- Calculate labor, parts, travel costs
- Integrate with accounting (InvoiceService, ARPaymentService)
- Service transaction history and reporting

All operations integrate with the accounting module for proper GL posting.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderType,
    ServiceOrderItem,
    ServiceTimeEntry,
    TimeEntryType,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.party import CustomerAccount, Party
from app.services.errors import NotFoundError, ValidationError

from .service_types import (
    ServiceInvoiceRequest,
    ServiceBillingData,
    ServiceCostBreakdown,
)
from .service_orders import ServiceOrderService

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.accounting import JournalEntry

__all__ = ["ServiceTransactionService"]


class ServiceTransactionService:
    """Service for billing and invoicing field services.

    Integrates with accounting services for proper double-entry bookkeeping:
    - Invoices: Created via InvoiceService with service line items
    - Payments: Recorded via ARPaymentService
    - Revenue: Tracked as service revenue (distinct from subscriptions)
    """

    # Default GL accounts for service revenue
    DEFAULT_SERVICE_REVENUE_ACCOUNT = "4200"  # Service Revenue
    DEFAULT_LABOR_REVENUE_ACCOUNT = "4210"  # Labor Revenue
    DEFAULT_PARTS_REVENUE_ACCOUNT = "4220"  # Parts Revenue
    DEFAULT_AR_ACCOUNT = "1200"  # Accounts Receivable

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._order_service: Optional[ServiceOrderService] = None

    @property
    def order_service(self) -> ServiceOrderService:
        """Get order service (lazy loaded)."""
        if self._order_service is None:
            self._order_service = ServiceOrderService(self.db, self.principal)
        return self._order_service

    # -------------------------------------------------------------------------
    # Invoice Generation
    # -------------------------------------------------------------------------

    def generate_invoice(
        self, request: ServiceInvoiceRequest
    ) -> Invoice:
        """Generate an invoice from completed service order(s).

        Creates a proper accounting invoice with:
        - Labor charges (hourly rate x hours)
        - Parts/materials used
        - Travel costs (if billable)
        - Tax/VAT

        Args:
            request: Invoice generation request with order IDs.

        Returns:
            Created Invoice.

        Raises:
            ValidationError: If orders not billable or not completed.
        """
        from app.services.accounting import InvoiceService
        from app.services.accounting.invoice_types import (
            InvoiceCreateData,
            InvoiceLineData,
        )

        # Validate orders
        orders = self._validate_orders_for_billing(request.service_order_ids)

        # Get customer account
        customer_account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.id == request.customer_account_id)
            .first()
        )
        if not customer_account:
            raise ValidationError(
                f"Customer account {request.customer_account_id} not found"
            )

        # Build line items from orders
        lines: List[InvoiceLineData] = []
        total_amount = Decimal("0")
        total_tax = Decimal("0")

        for order in orders:
            # Get or calculate costs
            billing = request.billing_overrides.get(order.id)
            costs = self._get_order_costs(order, billing)

            if request.combine_line_items:
                # Single line per order
                line = InvoiceLineData(
                    item_code=f"SO-{order.order_number}",
                    item_name=f"Service: {order.title}",
                    description=(
                        f"{order.order_type.value.title()} service - "
                        f"{order.service_address}"
                    ),
                    quantity=Decimal("1"),
                    rate=costs.subtotal,
                    amount=costs.subtotal,
                    tax_rate=costs.tax_rate,
                    tax_amount=costs.tax_amount,
                    account=self.DEFAULT_SERVICE_REVENUE_ACCOUNT,
                )
                lines.append(line)
            else:
                # Itemized lines
                lines.extend(self._build_itemized_lines(order, costs, request))

            total_amount += costs.subtotal
            total_tax += costs.tax_amount

        # Create invoice via InvoiceService
        invoice_date = request.invoice_date or date.today()
        due_date = request.due_date or (invoice_date + timedelta(days=14))

        invoice_data = InvoiceCreateData(
            customer_account_id=request.customer_account_id,
            invoice_date=datetime.combine(invoice_date, datetime.min.time()),
            due_date=datetime.combine(due_date, datetime.min.time()),
            currency=request.currency,
            description=self._build_invoice_description(orders),
            lines=lines,
            category="service",
        )

        invoice_service = InvoiceService(self.db, self.principal)
        invoice = invoice_service.create_invoice(invoice_data)

        # Store service order references in metadata
        invoice.metadata = invoice.metadata or {}
        invoice.metadata["service_order_ids"] = request.service_order_ids
        invoice.metadata["order_numbers"] = [o.order_number for o in orders]

        # Mark orders as billed
        for order in orders:
            order.metadata = order.metadata if hasattr(order, 'metadata') else {}
            # Track invoice link - use a simpler approach
            self.db.execute(
                f"UPDATE service_orders SET billable_amount = {float(costs.total)} "
                f"WHERE id = {order.id}"
            )

        # Auto-post if requested
        if request.auto_post:
            invoice, _ = invoice_service.post_invoice(invoice.id)

        return invoice

    def generate_invoice_for_order(
        self,
        order_id: int,
        auto_post: bool = False,
        notes: Optional[str] = None,
    ) -> Invoice:
        """Generate an invoice for a single service order.

        Convenience method for single-order invoicing.

        Args:
            order_id: Service order ID.
            auto_post: If True, post invoice to GL.
            notes: Optional invoice notes.

        Returns:
            Created Invoice.
        """
        order = self.order_service.get_order(order_id)

        request = ServiceInvoiceRequest(
            service_order_ids=[order_id],
            customer_account_id=order.customer_account_id,
            party_id=None,
            notes=notes,
            auto_post=auto_post,
        )

        return self.generate_invoice(request)

    def get_unbilled_orders(
        self,
        customer_account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[ServiceOrder]:
        """Get completed orders that haven't been invoiced.

        Args:
            customer_account_id: Optional customer account filter.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            List of unbilled service orders.
        """
        query = (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.is_billable == True,
            )
        )

        if customer_account_id:
            query = query.filter(
                ServiceOrder.customer_account_id == customer_account_id
            )

        if date_from:
            query = query.filter(
                func.date(ServiceOrder.actual_end_time) >= date_from
            )

        if date_to:
            query = query.filter(
                func.date(ServiceOrder.actual_end_time) <= date_to
            )

        # Filter out already invoiced orders
        # Check if order has been linked to an invoice via metadata
        invoiced_order_ids = self._get_invoiced_order_ids()
        if invoiced_order_ids:
            query = query.filter(~ServiceOrder.id.in_(invoiced_order_ids))

        return query.order_by(ServiceOrder.actual_end_time.desc()).all()

    def get_unbilled_summary(
        self, customer_account_id: Optional[int] = None
    ) -> dict:
        """Get summary of unbilled service orders.

        Args:
            customer_account_id: Optional customer account filter.

        Returns:
            Summary with counts and amounts.
        """
        orders = self.get_unbilled_orders(customer_account_id)

        total_amount = Decimal("0")
        by_type: Dict[str, Decimal] = {}

        for order in orders:
            amount = order.total_cost or order.billable_amount or Decimal("0")
            total_amount += amount

            type_key = order.order_type.value
            by_type[type_key] = by_type.get(type_key, Decimal("0")) + amount

        return {
            "unbilled_count": len(orders),
            "total_unbilled_amount": float(total_amount),
            "by_type": {k: float(v) for k, v in by_type.items()},
            "oldest_unbilled_date": (
                orders[-1].actual_end_time.isoformat() if orders else None
            ),
        }

    # -------------------------------------------------------------------------
    # Revenue Reporting
    # -------------------------------------------------------------------------

    def get_service_revenue(
        self,
        period_start: date,
        period_end: date,
        group_by: str = "day",  # day, week, month, type
    ) -> List[dict]:
        """Get service revenue by period.

        Args:
            period_start: Start of reporting period.
            period_end: End of reporting period.
            group_by: Grouping granularity.

        Returns:
            List of revenue by period.
        """
        # Get completed, billed orders in period
        orders = (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.is_billable == True,
                func.date(ServiceOrder.actual_end_time) >= period_start,
                func.date(ServiceOrder.actual_end_time) <= period_end,
            )
            .all()
        )

        # Group by period
        revenue_map: Dict[str, Dict] = {}

        for order in orders:
            end_date = order.actual_end_time.date() if order.actual_end_time else None
            if not end_date:
                continue

            if group_by == "day":
                key = end_date.isoformat()
            elif group_by == "week":
                key = f"{end_date.isocalendar()[0]}-W{end_date.isocalendar()[1]:02d}"
            elif group_by == "month":
                key = f"{end_date.year}-{end_date.month:02d}"
            elif group_by == "type":
                key = order.order_type.value
            else:
                key = end_date.isoformat()

            if key not in revenue_map:
                revenue_map[key] = {
                    "labor": Decimal("0"),
                    "parts": Decimal("0"),
                    "travel": Decimal("0"),
                    "total": Decimal("0"),
                    "count": 0,
                }

            revenue_map[key]["labor"] += order.labor_cost or Decimal("0")
            revenue_map[key]["parts"] += order.parts_cost or Decimal("0")
            revenue_map[key]["travel"] += order.travel_cost or Decimal("0")
            revenue_map[key]["total"] += order.total_cost or Decimal("0")
            revenue_map[key]["count"] += 1

        return [
            {
                "period": k,
                "labor_revenue": float(v["labor"]),
                "parts_revenue": float(v["parts"]),
                "travel_revenue": float(v["travel"]),
                "total_revenue": float(v["total"]),
                "order_count": v["count"],
            }
            for k, v in sorted(revenue_map.items())
        ]

    def get_revenue_by_customer(
        self,
        period_start: date,
        period_end: date,
        limit: int = 20,
    ) -> List[dict]:
        """Get service revenue by customer.

        Args:
            period_start: Start of reporting period.
            period_end: End of reporting period.
            limit: Top N customers.

        Returns:
            List of revenue by customer.
        """
        results = (
            self.db.query(
                ServiceOrder.customer_account_id,
                Party.name,
                func.count(ServiceOrder.id).label("order_count"),
                func.sum(ServiceOrder.labor_cost).label("labor"),
                func.sum(ServiceOrder.parts_cost).label("parts"),
                func.sum(ServiceOrder.travel_cost).label("travel"),
                func.sum(ServiceOrder.total_cost).label("total"),
            )
            .join(CustomerAccount, ServiceOrder.customer_account_id == CustomerAccount.id)
            .join(Party, CustomerAccount.party_id == Party.id)
            .filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.is_billable == True,
                func.date(ServiceOrder.actual_end_time) >= period_start,
                func.date(ServiceOrder.actual_end_time) <= period_end,
            )
            .group_by(ServiceOrder.customer_account_id, Party.name)
            .order_by(func.sum(ServiceOrder.total_cost).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "customer_account_id": r.customer_account_id,
                "customer_name": r.name,
                "order_count": r.order_count,
                "labor_revenue": float(r.labor or 0),
                "parts_revenue": float(r.parts or 0),
                "travel_revenue": float(r.travel or 0),
                "total_revenue": float(r.total or 0),
            }
            for r in results
        ]

    def get_revenue_by_technician(
        self,
        period_start: date,
        period_end: date,
        limit: int = 20,
    ) -> List[dict]:
        """Get service revenue by technician.

        Args:
            period_start: Start of reporting period.
            period_end: End of reporting period.
            limit: Top N technicians.

        Returns:
            List of revenue by technician.
        """
        from app.models.employee import Employee

        results = (
            self.db.query(
                ServiceOrder.assigned_technician_id,
                Employee.first_name,
                Employee.last_name,
                func.count(ServiceOrder.id).label("order_count"),
                func.sum(ServiceOrder.total_cost).label("total"),
                func.avg(ServiceOrder.customer_rating).label("avg_rating"),
            )
            .join(Employee, ServiceOrder.assigned_technician_id == Employee.id)
            .filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.assigned_technician_id.isnot(None),
                func.date(ServiceOrder.actual_end_time) >= period_start,
                func.date(ServiceOrder.actual_end_time) <= period_end,
            )
            .group_by(
                ServiceOrder.assigned_technician_id,
                Employee.first_name,
                Employee.last_name,
            )
            .order_by(func.sum(ServiceOrder.total_cost).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "technician_id": r.assigned_technician_id,
                "technician_name": f"{r.first_name} {r.last_name}",
                "order_count": r.order_count,
                "total_revenue": float(r.total or 0),
                "avg_customer_rating": float(r.avg_rating) if r.avg_rating else None,
            }
            for r in results
        ]

    # -------------------------------------------------------------------------
    # Cost Analysis
    # -------------------------------------------------------------------------

    def get_cost_analysis(
        self,
        period_start: date,
        period_end: date,
    ) -> dict:
        """Get cost analysis for service operations.

        Args:
            period_start: Start of analysis period.
            period_end: End of analysis period.

        Returns:
            Cost analysis breakdown.
        """
        orders = (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                func.date(ServiceOrder.actual_end_time) >= period_start,
                func.date(ServiceOrder.actual_end_time) <= period_end,
            )
            .all()
        )

        # Aggregate costs
        total_labor = sum(o.labor_cost or Decimal("0") for o in orders)
        total_parts = sum(o.parts_cost or Decimal("0") for o in orders)
        total_travel = sum(o.travel_cost or Decimal("0") for o in orders)
        total_revenue = sum(o.total_cost or Decimal("0") for o in orders)

        # Time analysis
        time_entries = (
            self.db.query(ServiceTimeEntry)
            .filter(
                func.date(ServiceTimeEntry.start_time) >= period_start,
                func.date(ServiceTimeEntry.start_time) <= period_end,
            )
            .all()
        )

        total_work_hours = sum(
            t.duration_hours or Decimal("0")
            for t in time_entries
            if t.entry_type == TimeEntryType.WORK
        )
        total_travel_hours = sum(
            t.duration_hours or Decimal("0")
            for t in time_entries
            if t.entry_type == TimeEntryType.TRAVEL
        )
        billable_hours = sum(
            t.duration_hours or Decimal("0")
            for t in time_entries
            if t.is_billable
        )

        # Averages
        order_count = len(orders)
        avg_order_value = total_revenue / order_count if order_count else Decimal("0")
        avg_labor_per_order = total_labor / order_count if order_count else Decimal("0")
        avg_parts_per_order = total_parts / order_count if order_count else Decimal("0")

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "order_count": order_count,
            "revenue": {
                "total": float(total_revenue),
                "labor": float(total_labor),
                "parts": float(total_parts),
                "travel": float(total_travel),
            },
            "averages": {
                "order_value": float(avg_order_value),
                "labor_per_order": float(avg_labor_per_order),
                "parts_per_order": float(avg_parts_per_order),
            },
            "time": {
                "total_work_hours": float(total_work_hours),
                "total_travel_hours": float(total_travel_hours),
                "billable_hours": float(billable_hours),
                "utilization_percent": float(
                    billable_hours / (total_work_hours + total_travel_hours) * 100
                    if (total_work_hours + total_travel_hours) > 0
                    else 0
                ),
            },
            "cost_breakdown_percent": {
                "labor": float(total_labor / total_revenue * 100) if total_revenue else 0,
                "parts": float(total_parts / total_revenue * 100) if total_revenue else 0,
                "travel": float(total_travel / total_revenue * 100) if total_revenue else 0,
            },
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_orders_for_billing(
        self, order_ids: List[int]
    ) -> List[ServiceOrder]:
        """Validate orders can be billed."""
        orders = (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.id.in_(order_ids))
            .all()
        )

        if len(orders) != len(order_ids):
            found_ids = {o.id for o in orders}
            missing = set(order_ids) - found_ids
            raise ValidationError(f"Orders not found: {missing}")

        errors = []
        for order in orders:
            if order.status != ServiceOrderStatus.COMPLETED:
                errors.append(
                    f"Order {order.order_number} not completed "
                    f"(status: {order.status.value})"
                )
            if not order.is_billable:
                errors.append(
                    f"Order {order.order_number} is not billable"
                )

        if errors:
            raise ValidationError("; ".join(errors))

        return orders

    def _get_order_costs(
        self,
        order: ServiceOrder,
        billing: Optional[ServiceBillingData] = None,
    ) -> ServiceCostBreakdown:
        """Get or calculate costs for an order."""
        # If overrides provided, use them
        if billing and billing.total_override:
            return ServiceCostBreakdown(
                labor_cost=billing.labor_cost_override or Decimal("0"),
                parts_cost=billing.parts_cost_override or Decimal("0"),
                travel_cost=billing.travel_cost_override or Decimal("0"),
                subtotal=billing.total_override,
                tax_rate=billing.tax_rate or Decimal("7.5"),
                tax_amount=(
                    billing.total_override * (billing.tax_rate or Decimal("7.5")) / 100
                ),
                total=billing.total_override * (1 + (billing.tax_rate or Decimal("7.5")) / 100),
            )

        # Use pre-calculated costs from order
        if order.total_cost and order.total_cost > 0:
            subtotal = (
                (order.labor_cost or Decimal("0"))
                + (order.parts_cost or Decimal("0"))
                + (order.travel_cost or Decimal("0"))
            )
            tax_rate = Decimal("7.5")
            tax_amount = subtotal * tax_rate / 100

            return ServiceCostBreakdown(
                labor_cost=order.labor_cost or Decimal("0"),
                parts_cost=order.parts_cost or Decimal("0"),
                travel_cost=order.travel_cost or Decimal("0"),
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=subtotal + tax_amount,
            )

        # Calculate from time entries and items
        return self.order_service.calculate_costs(order.id)

    def _build_itemized_lines(
        self,
        order: ServiceOrder,
        costs: ServiceCostBreakdown,
        request: ServiceInvoiceRequest,
    ) -> List:
        """Build itemized invoice lines from an order."""
        from app.services.accounting.invoice_types import InvoiceLineData

        lines = []

        # Labor line
        if costs.labor_cost > 0:
            lines.append(
                InvoiceLineData(
                    item_code=f"LABOR-{order.order_number}",
                    item_name="Labor",
                    description=f"Labor for {order.order_type.value} service",
                    quantity=costs.labor_hours,
                    rate=costs.labor_rate,
                    amount=costs.labor_cost,
                    tax_rate=costs.tax_rate,
                    tax_amount=costs.labor_cost * costs.tax_rate / 100,
                    account=self.DEFAULT_LABOR_REVENUE_ACCOUNT,
                )
            )

        # Travel line
        if costs.travel_cost > 0:
            lines.append(
                InvoiceLineData(
                    item_code=f"TRAVEL-{order.order_number}",
                    item_name="Travel",
                    description=f"Travel to/from service location",
                    quantity=costs.travel_hours,
                    rate=costs.travel_rate,
                    amount=costs.travel_cost,
                    tax_rate=costs.tax_rate,
                    tax_amount=costs.travel_cost * costs.tax_rate / 100,
                    account=self.DEFAULT_SERVICE_REVENUE_ACCOUNT,
                )
            )

        # Parts lines
        if request.include_parts_detail:
            items = (
                self.db.query(ServiceOrderItem)
                .filter(ServiceOrderItem.service_order_id == order.id)
                .all()
            )
            for item in items:
                lines.append(
                    InvoiceLineData(
                        item_code=item.item_code or f"PART-{item.id}",
                        item_name=item.item_name,
                        description=f"Parts/Materials: {item.item_name}",
                        quantity=item.quantity,
                        rate=item.unit_cost,
                        amount=item.total_cost or Decimal("0"),
                        tax_rate=costs.tax_rate,
                        tax_amount=(item.total_cost or Decimal("0")) * costs.tax_rate / 100,
                        account=self.DEFAULT_PARTS_REVENUE_ACCOUNT,
                    )
                )
        elif costs.parts_cost > 0:
            # Single parts line
            lines.append(
                InvoiceLineData(
                    item_code=f"PARTS-{order.order_number}",
                    item_name="Parts & Materials",
                    description=f"Parts and materials used",
                    quantity=Decimal("1"),
                    rate=costs.parts_cost,
                    amount=costs.parts_cost,
                    tax_rate=costs.tax_rate,
                    tax_amount=costs.parts_cost * costs.tax_rate / 100,
                    account=self.DEFAULT_PARTS_REVENUE_ACCOUNT,
                )
            )

        return lines

    def _build_invoice_description(self, orders: List[ServiceOrder]) -> str:
        """Build invoice description from orders."""
        if len(orders) == 1:
            order = orders[0]
            return (
                f"Service: {order.title} ({order.order_type.value}) - "
                f"Order #{order.order_number}"
            )
        else:
            return f"Service charges for {len(orders)} service orders"

    def _get_invoiced_order_ids(self) -> List[int]:
        """Get list of order IDs that have been invoiced."""
        # Query invoices with service_order_ids in metadata
        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.category == "service",
                Invoice.is_deleted == False,
            )
            .all()
        )

        order_ids = []
        for inv in invoices:
            if inv.metadata and "service_order_ids" in inv.metadata:
                order_ids.extend(inv.metadata["service_order_ids"])

        return order_ids
