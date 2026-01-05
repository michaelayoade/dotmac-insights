"""AP Aging Service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Any, List, cast

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus

from .types import AgingBucket


class APAgingService:
    """Service for accounts payable aging analysis."""

    def __init__(self, db: Session):
        self.db = db

    def get_aging_report(
        self,
        as_of_date: Optional[date] = None,
        supplier: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get AP aging buckets."""
        cutoff = as_of_date or date.today()

        query = self.db.query(PurchaseInvoice).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ]),
        )

        if supplier:
            query = query.filter(
                or_(
                    PurchaseInvoice.supplier.ilike(f"%{supplier}%"),
                    PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"),
                )
            )

        if currency:
            query = query.filter(PurchaseInvoice.currency == currency)

        invoices = query.all()

        # Initialize buckets
        buckets: Dict[str, AgingBucket] = {
            "current": AgingBucket(),
            "1_30": AgingBucket(),
            "31_60": AgingBucket(),
            "61_90": AgingBucket(),
            "over_90": AgingBucket(),
        }

        for inv in invoices:
            due = inv.due_date.date() if inv.due_date else (
                inv.posting_date.date() if inv.posting_date else cutoff
            )
            days_overdue = (cutoff - due).days if cutoff > due else 0

            if days_overdue <= 0:
                bucket_key = "current"
            elif days_overdue <= 30:
                bucket_key = "1_30"
            elif days_overdue <= 60:
                bucket_key = "31_60"
            elif days_overdue <= 90:
                bucket_key = "61_90"
            else:
                bucket_key = "over_90"

            bucket = buckets[bucket_key]
            bucket.count += 1
            bucket.total += inv.outstanding_amount or Decimal("0")
            bucket.invoices.append({
                "id": inv.id,
                "invoice_no": inv.erpnext_id,
                "supplier": inv.supplier_name or inv.supplier,
                "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "grand_total": float(inv.grand_total),
                "outstanding": float(inv.outstanding_amount),
                "days_overdue": days_overdue,
            })

        total_payable = sum(b.total for b in buckets.values())

        return {
            "as_of_date": cutoff.isoformat(),
            "total_payable": float(total_payable),
            "total_invoices": sum(b.count for b in buckets.values()),
            "aging": {
                key: {
                    "count": b.count,
                    "total": float(b.total),
                    "invoices": b.invoices,
                }
                for key, b in buckets.items()
            },
        }

    def get_aging_summary(self, as_of_date: Optional[date] = None) -> Dict[str, Decimal]:
        """Get aging summary without invoice details."""
        report = self.get_aging_report(as_of_date)
        return {
            key: Decimal(str(data["total"]))
            for key, data in report["aging"].items()
        }

    def get_supplier_aging(
        self,
        supplier_name: str,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get aging for a specific supplier."""
        return self.get_aging_report(as_of_date=as_of_date, supplier=supplier_name)
