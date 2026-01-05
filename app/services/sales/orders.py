"""Sales order service - business logic for sales order management.

This service encapsulates sales order-related business logic:
- Core CRUD for sales orders
- Line item management
- Workflow (submit, hold, close, cancel)
- Delivery and billing status tracking
- Invoice generation
- Summary analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.sales import SalesOrder, SalesOrderStatus
from app.models.document_lines import SalesOrderItem
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .order_types import (
    SalesOrderFilters,
    SalesOrderCreateData,
    SalesOrderUpdateData,
    SalesOrderLineItemData,
    SalesOrderLineItemUpdateData,
    SalesOrderSummary,
    FulfillmentStatus,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.accounting import Invoice


class SalesOrderService:
    """Service for sales order management.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Sales Order CRUD
    # -------------------------------------------------------------------------

    def list_orders(
        self,
        filters: Optional[SalesOrderFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_items: bool = False,
    ) -> PaginatedResult[SalesOrder]:
        """List sales orders with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_items: Whether to eagerly load line items.

        Returns:
            PaginatedResult containing orders and total count.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)

        if include_items:
            query = query.options(joinedload(SalesOrder.items))

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        SalesOrder.customer.ilike(like),
                        SalesOrder.customer_name.ilike(like),
                        SalesOrder.erpnext_id.ilike(like),
                    )
                )

            if filters.status:
                try:
                    status_enum = SalesOrderStatus(filters.status.lower())
                    query = query.filter(SalesOrder.status == status_enum)
                except ValueError:
                    pass

            if filters.customer:
                query = query.filter(SalesOrder.customer == filters.customer)

            if filters.customer_account_id:
                query = query.filter(SalesOrder.customer_account_id == filters.customer_account_id)

            if filters.sales_partner_id:
                query = query.filter(SalesOrder.sales_partner_id == filters.sales_partner_id)

            if filters.territory_id:
                query = query.filter(SalesOrder.territory_id == filters.territory_id)

            if filters.min_value is not None:
                query = query.filter(SalesOrder.grand_total >= filters.min_value)

            if filters.max_value is not None:
                query = query.filter(SalesOrder.grand_total <= filters.max_value)

            if filters.date_from:
                query = query.filter(SalesOrder.transaction_date >= filters.date_from)

            if filters.date_to:
                query = query.filter(SalesOrder.transaction_date <= filters.date_to)

            if filters.delivery_date_from:
                query = query.filter(SalesOrder.delivery_date >= filters.delivery_date_from)

            if filters.delivery_date_to:
                query = query.filter(SalesOrder.delivery_date <= filters.delivery_date_to)

            if filters.billing_status:
                query = query.filter(SalesOrder.billing_status == filters.billing_status)

            if filters.delivery_status:
                query = query.filter(SalesOrder.delivery_status == filters.delivery_status)

            if filters.source:
                query = query.filter(SalesOrder.source == filters.source)

            if filters.campaign:
                query = query.filter(SalesOrder.campaign == filters.campaign)

            if filters.company:
                query = query.filter(SalesOrder.company == filters.company)

        query = query.order_by(SalesOrder.created_at.desc())
        return paginate(query, pagination)

    def get_order(self, order_id: int, include_items: bool = True) -> SalesOrder:
        """Get a sales order by ID.

        Args:
            order_id: The order ID.
            include_items: Whether to eagerly load line items.

        Returns:
            The SalesOrder.

        Raises:
            NotFoundError: If order not found.
        """
        query = scoped_query(self.db.query(SalesOrder), self.principal)

        if include_items:
            query = query.options(joinedload(SalesOrder.items))

        order = query.filter(SalesOrder.id == order_id).first()
        if not order:
            raise NotFoundError(f"Sales order {order_id} not found")

        return order

    def create_order(self, data: SalesOrderCreateData) -> SalesOrder:
        """Create a new sales order.

        Args:
            data: Order creation data.

        Returns:
            The created SalesOrder (not yet committed).
        """
        order = SalesOrder(
            customer=data.customer,
            customer_name=data.customer_name or data.customer,
            customer_account_id=data.customer_account_id,
            company=data.company,
            currency=data.currency,
            transaction_date=data.transaction_date or date.today(),
            delivery_date=data.delivery_date,
            order_type=data.order_type,
            sales_partner_id=data.sales_partner_id,
            territory_id=data.territory_id,
            source=data.source,
            campaign=data.campaign,
            status=SalesOrderStatus.DRAFT,
        )

        self.db.add(order)
        self.db.flush()

        # Add line items
        for item_data in data.items:
            self.add_line_item(order.id, item_data)

        self._recalculate_totals(order)
        return order

    def update_order(self, order_id: int, data: SalesOrderUpdateData) -> SalesOrder:
        """Update a sales order.

        Args:
            order_id: The order ID.
            data: Fields to update.

        Returns:
            The updated SalesOrder (not yet committed).

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order is not in draft status.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status not in (SalesOrderStatus.DRAFT, SalesOrderStatus.ON_HOLD):
            raise ValidationError(f"Cannot update order in {order.status.value} status")

        # Update simple fields
        update_fields = [
            "customer_name", "delivery_date", "order_type",
            "sales_partner_id", "territory_id", "source", "campaign",
        ]
        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(order, field_name, value)

        return order

    def delete_order(self, order_id: int) -> None:
        """Delete a sales order.

        Args:
            order_id: The order ID.

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order cannot be deleted.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status not in (SalesOrderStatus.DRAFT, SalesOrderStatus.ON_HOLD):
            raise ValidationError(f"Cannot delete order in {order.status.value} status")

        self.db.delete(order)

    def cancel_order(self, order_id: int, reason: Optional[str] = None) -> SalesOrder:
        """Cancel a sales order.

        Args:
            order_id: The order ID.
            reason: Optional cancellation reason.

        Returns:
            The updated SalesOrder.

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order cannot be cancelled.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status == SalesOrderStatus.COMPLETED:
            raise ValidationError("Cannot cancel completed order")

        if order.per_delivered > 0 or order.per_billed > 0:
            raise ValidationError("Cannot cancel order with deliveries or invoices")

        order.status = SalesOrderStatus.CANCELLED
        order.docstatus = 2
        return order

    # -------------------------------------------------------------------------
    # Line Item Management
    # -------------------------------------------------------------------------

    def add_line_item(self, order_id: int, data: SalesOrderLineItemData) -> SalesOrderItem:
        """Add a line item to a sales order.

        Args:
            order_id: The order ID.
            data: Line item data.

        Returns:
            The created SalesOrderItem.

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order is not editable.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status not in (SalesOrderStatus.DRAFT,):
            raise ValidationError(f"Cannot add items to order in {order.status.value} status")

        # Calculate line amount
        amount = data.qty * data.rate
        if data.discount_percentage:
            amount = amount * (1 - data.discount_percentage / 100)
        elif data.discount_amount:
            amount = amount - data.discount_amount

        item = SalesOrderItem(
            sales_order_id=order_id,
            item_code=data.item_code,
            item_name=data.item_name,
            description=data.description,
            qty=data.qty,
            rate=data.rate,
            uom=data.uom,
            discount_percentage=data.discount_percentage,
            discount_amount=data.discount_amount,
            amount=amount,
            warehouse=data.warehouse,
            delivery_date=data.delivery_date,
        )

        self.db.add(item)
        self.db.flush()

        self._recalculate_totals(order)
        return item

    def update_line_item(self, item_id: int, data: SalesOrderLineItemUpdateData) -> SalesOrderItem:
        """Update a sales order line item.

        Args:
            item_id: The line item ID.
            data: Fields to update.

        Returns:
            The updated SalesOrderItem.

        Raises:
            NotFoundError: If line item not found.
        """
        item = self.db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
        if not item:
            raise NotFoundError(f"Sales order item {item_id} not found")

        order = self.get_order(item.sales_order_id, include_items=False)
        if order.status != SalesOrderStatus.DRAFT:
            raise ValidationError(f"Cannot update items on order in {order.status.value} status")

        # Update fields
        if data.qty is not None:
            item.qty = data.qty
        if data.rate is not None:
            item.rate = data.rate
        if data.discount_percentage is not None:
            item.discount_percentage = data.discount_percentage
        if data.discount_amount is not None:
            item.discount_amount = data.discount_amount
        if data.description is not None:
            item.description = data.description
        if data.delivery_date is not None:
            item.delivery_date = data.delivery_date

        # Recalculate amount
        amount = item.qty * item.rate
        if item.discount_percentage:
            amount = amount * (1 - item.discount_percentage / 100)
        elif item.discount_amount:
            amount = amount - item.discount_amount
        item.amount = amount

        self._recalculate_totals(order)
        return item

    def remove_line_item(self, item_id: int) -> None:
        """Remove a line item from a sales order.

        Args:
            item_id: The line item ID.

        Raises:
            NotFoundError: If line item not found.
        """
        item = self.db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
        if not item:
            raise NotFoundError(f"Sales order item {item_id} not found")

        order = self.get_order(item.sales_order_id, include_items=False)
        if order.status != SalesOrderStatus.DRAFT:
            raise ValidationError(f"Cannot remove items from order in {order.status.value} status")

        self.db.delete(item)
        self.db.flush()

        self._recalculate_totals(order)

    # -------------------------------------------------------------------------
    # Workflow Operations
    # -------------------------------------------------------------------------

    def submit_order(self, order_id: int) -> SalesOrder:
        """Submit a draft order (DRAFT → TO_DELIVER_AND_BILL).

        Args:
            order_id: The order ID.

        Returns:
            The updated SalesOrder.

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order cannot be submitted.
        """
        order = self.get_order(order_id, include_items=True)

        if order.status != SalesOrderStatus.DRAFT:
            raise ValidationError(f"Can only submit orders in draft status, current: {order.status.value}")

        if not order.items:
            raise ValidationError("Cannot submit order without line items")

        order.status = SalesOrderStatus.TO_DELIVER_AND_BILL
        order.docstatus = 1
        return order

    def hold_order(self, order_id: int, reason: Optional[str] = None) -> SalesOrder:
        """Put order on hold.

        Args:
            order_id: The order ID.
            reason: Optional hold reason.

        Returns:
            The updated SalesOrder.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status in (SalesOrderStatus.COMPLETED, SalesOrderStatus.CANCELLED):
            raise ValidationError(f"Cannot hold order in {order.status.value} status")

        order.status = SalesOrderStatus.ON_HOLD
        return order

    def resume_order(self, order_id: int) -> SalesOrder:
        """Resume a held order.

        Args:
            order_id: The order ID.

        Returns:
            The updated SalesOrder.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status != SalesOrderStatus.ON_HOLD:
            raise ValidationError(f"Can only resume orders on hold, current: {order.status.value}")

        # Determine appropriate status based on fulfillment
        if order.per_delivered >= 100 and order.per_billed < 100:
            order.status = SalesOrderStatus.TO_BILL
        elif order.per_billed >= 100 and order.per_delivered < 100:
            order.status = SalesOrderStatus.TO_DELIVER
        elif order.per_delivered >= 100 and order.per_billed >= 100:
            order.status = SalesOrderStatus.COMPLETED
        else:
            order.status = SalesOrderStatus.TO_DELIVER_AND_BILL

        return order

    def close_order(self, order_id: int) -> SalesOrder:
        """Close an order (mark as completed regardless of fulfillment).

        Args:
            order_id: The order ID.

        Returns:
            The updated SalesOrder.
        """
        order = self.get_order(order_id, include_items=False)

        if order.status in (SalesOrderStatus.CANCELLED, SalesOrderStatus.DRAFT):
            raise ValidationError(f"Cannot close order in {order.status.value} status")

        order.status = SalesOrderStatus.CLOSED
        return order

    # -------------------------------------------------------------------------
    # Fulfillment Tracking
    # -------------------------------------------------------------------------

    def update_delivery_status(self, order_id: int, per_delivered: Decimal) -> SalesOrder:
        """Update delivery percentage.

        Args:
            order_id: The order ID.
            per_delivered: New delivery percentage (0-100).

        Returns:
            The updated SalesOrder.
        """
        order = self.get_order(order_id, include_items=False)
        order.per_delivered = per_delivered

        self._update_fulfillment_status(order)
        return order

    def update_billing_status(self, order_id: int, per_billed: Decimal) -> SalesOrder:
        """Update billing percentage.

        Args:
            order_id: The order ID.
            per_billed: New billing percentage (0-100).

        Returns:
            The updated SalesOrder.
        """
        order = self.get_order(order_id, include_items=False)
        order.per_billed = per_billed

        self._update_fulfillment_status(order)
        return order

    def get_fulfillment_status(self, order_id: int) -> FulfillmentStatus:
        """Get detailed fulfillment status for an order.

        Args:
            order_id: The order ID.

        Returns:
            FulfillmentStatus with delivery and billing details.
        """
        order = self.get_order(order_id, include_items=True)

        pending_qty = sum(
            item.qty * (1 - order.per_delivered / 100)
            for item in order.items
        )
        pending_amount = order.grand_total * (1 - order.per_billed / 100)

        return FulfillmentStatus(
            order_id=order_id,
            per_delivered=order.per_delivered,
            per_billed=order.per_billed,
            is_fully_delivered=order.per_delivered >= 100,
            is_fully_billed=order.per_billed >= 100,
            pending_delivery_qty=pending_qty,
            pending_billing_amount=pending_amount,
        )

    # -------------------------------------------------------------------------
    # Invoice Generation
    # -------------------------------------------------------------------------

    def create_invoice_from_order(
        self,
        order_id: int,
        percent: Decimal = Decimal("100"),
    ) -> "Invoice":
        """Create an invoice from sales order.

        Args:
            order_id: The order ID.
            percent: Percentage of order to invoice (default 100%).

        Returns:
            The created Invoice.

        Raises:
            NotFoundError: If order not found.
            ValidationError: If order cannot be invoiced.
        """
        from app.models.accounting import Invoice, InvoiceStatus, InvoiceLine

        order = self.get_order(order_id, include_items=True)

        if order.status == SalesOrderStatus.DRAFT:
            raise ValidationError("Cannot create invoice from draft order")

        if order.per_billed >= 100:
            raise ValidationError("Order is already fully billed")

        # Calculate invoice amount
        remaining_percent = Decimal("100") - order.per_billed
        invoice_percent = min(percent, remaining_percent)
        multiplier = invoice_percent / Decimal("100")

        # Create invoice
        invoice = Invoice(
            customer=order.customer,
            customer_name=order.customer_name,
            customer_account_id=order.customer_account_id,
            company=order.company,
            currency=order.currency,
            posting_date=date.today(),
            due_date=date.today(),  # Should be calculated from payment terms
            sales_order_id=order.id,
            status=InvoiceStatus.DRAFT,
            # Amounts will be calculated from lines
        )

        self.db.add(invoice)
        self.db.flush()

        # Create invoice lines from order items
        total = Decimal("0")
        for item in order.items:
            line_amount = item.amount * multiplier
            total += line_amount

            line = InvoiceLine(
                invoice_id=invoice.id,
                item_code=item.item_code,
                item_name=item.item_name,
                description=item.description,
                qty=item.qty * multiplier,
                rate=item.rate,
                amount=line_amount,
                uom=item.uom,
            )
            self.db.add(line)

        # Update invoice totals
        invoice.total = total
        invoice.net_total = total
        invoice.grand_total = total + (order.total_taxes_and_charges * multiplier)
        invoice.outstanding_amount = invoice.grand_total

        # Update order billing status
        order.per_billed = order.per_billed + invoice_percent
        self._update_fulfillment_status(order)

        return invoice

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self, filters: Optional[SalesOrderFilters] = None) -> SalesOrderSummary:
        """Get sales order summary statistics.

        Args:
            filters: Optional filters to apply.

        Returns:
            SalesOrderSummary with aggregated stats.
        """
        base_query = scoped_query(self.db.query(SalesOrder), self.principal)

        if filters:
            if filters.date_from:
                base_query = base_query.filter(SalesOrder.transaction_date >= filters.date_from)
            if filters.date_to:
                base_query = base_query.filter(SalesOrder.transaction_date <= filters.date_to)
            if filters.company:
                base_query = base_query.filter(SalesOrder.company == filters.company)

        # Total
        total = base_query.count()
        total_value = base_query.with_entities(func.sum(SalesOrder.grand_total)).scalar() or Decimal("0")

        # By status
        def get_status_stats(status: SalesOrderStatus):
            q = base_query.filter(SalesOrder.status == status)
            count = q.count()
            value = q.with_entities(func.sum(SalesOrder.grand_total)).scalar() or Decimal("0")
            return count, value

        draft_count, draft_value = get_status_stats(SalesOrderStatus.DRAFT)
        on_hold_count, on_hold_value = get_status_stats(SalesOrderStatus.ON_HOLD)
        completed_count, completed_value = get_status_stats(SalesOrderStatus.COMPLETED)

        # Pending delivery
        pending_delivery = base_query.filter(
            SalesOrder.status.in_([
                SalesOrderStatus.TO_DELIVER_AND_BILL,
                SalesOrderStatus.TO_DELIVER,
            ])
        )
        pending_delivery_count = pending_delivery.count()
        pending_delivery_value = pending_delivery.with_entities(
            func.sum(SalesOrder.grand_total)
        ).scalar() or Decimal("0")

        # Pending billing
        pending_billing = base_query.filter(
            SalesOrder.status.in_([
                SalesOrderStatus.TO_DELIVER_AND_BILL,
                SalesOrderStatus.TO_BILL,
            ])
        )
        pending_billing_count = pending_billing.count()
        pending_billing_value = pending_billing.with_entities(
            func.sum(SalesOrder.grand_total)
        ).scalar() or Decimal("0")

        # Fulfillment rate
        submitted = total - draft_count
        fulfillment_rate = (completed_count / submitted * 100) if submitted > 0 else 0.0

        # Average
        avg_value = total_value / total if total > 0 else Decimal("0")

        return SalesOrderSummary(
            total_count=total,
            total_value=total_value,
            draft_count=draft_count,
            draft_value=draft_value,
            pending_delivery_count=pending_delivery_count,
            pending_delivery_value=pending_delivery_value,
            pending_billing_count=pending_billing_count,
            pending_billing_value=pending_billing_value,
            completed_count=completed_count,
            completed_value=completed_value,
            on_hold_count=on_hold_count,
            on_hold_value=on_hold_value,
            fulfillment_rate=fulfillment_rate,
            avg_order_value=avg_value,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _recalculate_totals(self, order: SalesOrder) -> None:
        """Recalculate order totals from line items."""
        items = self.db.query(SalesOrderItem).filter(
            SalesOrderItem.sales_order_id == order.id
        ).all()

        total_qty = sum(item.qty for item in items)
        total = sum(item.amount for item in items)
        order.total_qty = total_qty
        order.total = total
        order.net_total = total
        order.grand_total = total + order.total_taxes_and_charges
        order.rounded_total = round(order.grand_total, 0)

    def _update_fulfillment_status(self, order: SalesOrder) -> None:
        """Update order status based on fulfillment percentages."""
        if order.status in (SalesOrderStatus.DRAFT, SalesOrderStatus.CANCELLED, SalesOrderStatus.CLOSED):
            return

        if order.per_delivered >= 100 and order.per_billed >= 100:
            order.status = SalesOrderStatus.COMPLETED
        elif order.per_delivered >= 100:
            order.status = SalesOrderStatus.TO_BILL
        elif order.per_billed >= 100:
            order.status = SalesOrderStatus.TO_DELIVER
        else:
            order.status = SalesOrderStatus.TO_DELIVER_AND_BILL
