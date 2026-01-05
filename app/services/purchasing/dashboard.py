"""Purchasing Dashboard Service."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier

from .types import DashboardMetrics


class PurchasingDashboardService:
    """Service for purchasing dashboard metrics."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_metrics(self, as_of_date: Optional[date] = None) -> DashboardMetrics:
        """Get comprehensive purchasing dashboard metrics."""
        cutoff = as_of_date or date.today()

        # Total outstanding AP
        total_outstanding = self.db.query(
            func.sum(PurchaseInvoice.outstanding_amount)
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ])
        ).scalar() or Decimal("0")

        # Bills count by status
        bills_by_status = self.db.query(
            PurchaseInvoice.status,
            func.count(PurchaseInvoice.id).label("count"),
            func.sum(PurchaseInvoice.grand_total).label("total"),
        ).group_by(PurchaseInvoice.status).all()

        status_breakdown = {
            row.status.value if row.status else "unknown": {
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in bills_by_status
        }

        # Overdue amounts
        total_overdue = self.db.query(
            func.sum(PurchaseInvoice.outstanding_amount)
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < cutoff,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ])
        ).scalar() or Decimal("0")

        # Top 5 suppliers by outstanding
        top_suppliers = self.db.query(
            PurchaseInvoice.supplier_name,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.count(PurchaseInvoice.id).label("bill_count"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
        ).group_by(
            PurchaseInvoice.supplier_name
        ).order_by(
            func.sum(PurchaseInvoice.outstanding_amount).desc()
        ).limit(5).all()

        # Bills due this week
        week_end = cutoff + timedelta(days=7)
        due_result = self.db.query(
            func.count(PurchaseInvoice.id),
            func.sum(PurchaseInvoice.outstanding_amount),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date >= cutoff,
            PurchaseInvoice.due_date <= week_end,
        ).first()

        due_count = int(due_result[0] or 0) if due_result else 0
        due_total = Decimal(str(due_result[1] or 0)) if due_result else Decimal("0")

        # Supplier count
        supplier_count = self.db.query(func.count(Supplier.id)).filter(
            Supplier.disabled == False
        ).scalar() or 0

        # Calculate overdue percentage
        overdue_pct = 0.0
        if total_outstanding > 0:
            overdue_pct = round(float(total_overdue / total_outstanding * 100), 1)

        return DashboardMetrics(
            total_outstanding=total_outstanding,
            total_overdue=total_overdue,
            overdue_percentage=overdue_pct,
            supplier_count=supplier_count,
            status_breakdown=status_breakdown,
            due_this_week={"count": due_count, "total": float(due_total)},
            top_suppliers=[
                {
                    "name": row.supplier_name,
                    "outstanding": float(row.outstanding),
                    "bill_count": row.bill_count,
                }
                for row in top_suppliers
            ],
        )

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get quick summary statistics."""
        total_bills = self.db.query(func.count(PurchaseInvoice.id)).scalar() or 0

        total_outstanding = self.db.query(
            func.sum(PurchaseInvoice.outstanding_amount)
        ).filter(PurchaseInvoice.outstanding_amount > 0).scalar() or Decimal("0")

        overdue_count = self.db.query(func.count(PurchaseInvoice.id)).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < date.today(),
        ).scalar() or 0

        return {
            "total_bills": total_bills,
            "total_outstanding": float(total_outstanding),
            "overdue_count": overdue_count,
        }
