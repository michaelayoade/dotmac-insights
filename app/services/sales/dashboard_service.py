"""Service layer for Sales dashboard analytics."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus
from app.models.subscription import Subscription, SubscriptionStatus


class SalesDashboardService:
    """Encapsulate sales dashboard data queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_open_quotations(self) -> int:
        return (
            self.db.query(func.count(Quotation.id))
            .filter(Quotation.status == QuotationStatus.OPEN, Quotation.is_deleted == False)
            .scalar()
            or 0
        )

    def get_pending_orders(self) -> int:
        return (
            self.db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.status.in_([
                    SalesOrderStatus.DRAFT,
                    SalesOrderStatus.TO_DELIVER_AND_BILL,
                    SalesOrderStatus.TO_BILL,
                    SalesOrderStatus.TO_DELIVER,
                ])
            )
            .scalar()
            or 0
        )

    def get_pending_invoices(self) -> int:
        return (
            self.db.query(func.count(Invoice.id))
            .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]))
            .scalar()
            or 0
        )

    def get_active_subscriptions(self) -> int:
        return (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
            or 0
        )

    def get_revenue_mtd(self, month_start: date) -> Decimal:
        return (
            self.db.query(func.sum(Invoice.total_amount))
            .filter(
                Invoice.invoice_date >= month_start,
                Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
            )
            .scalar()
            or Decimal("0")
        )
