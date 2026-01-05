"""Sales module dashboard service.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription, SubscriptionStatus

if TYPE_CHECKING:
    from app.auth import Principal


class SalesModuleDashboardService:
    """Service for Sales module dashboard summary cards."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def get_dashboard_counts(self) -> Dict[str, int | Decimal]:
        """Return key counts and totals for the Sales dashboard."""
        open_quotes = (
            self.db.query(func.count(Quotation.id))
            .filter(
                Quotation.status == QuotationStatus.OPEN,
                Quotation.is_deleted == False,
            )
            .scalar()
            or 0
        )

        pending_orders = (
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

        pending_invoices = (
            self.db.query(func.count(Invoice.id))
            .filter(
                Invoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.PARTIALLY_PAID,
                ])
            )
            .scalar()
            or 0
        )

        active_subs = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
            or 0
        )

        today = date.today()
        month_start = date(today.year, today.month, 1)
        revenue_mtd = (
            self.db.query(func.sum(Invoice.total_amount))
            .filter(
                Invoice.invoice_date >= month_start,
                Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
            )
            .scalar()
            or Decimal("0")
        )

        return {
            "open_quotes": open_quotes,
            "pending_orders": pending_orders,
            "pending_invoices": pending_invoices,
            "active_subs": active_subs,
            "revenue_mtd": revenue_mtd,
        }
