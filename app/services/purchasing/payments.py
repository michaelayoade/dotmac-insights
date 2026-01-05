"""Vendor Payments and Purchase Orders Service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import PurchaseInvoice, GLEntry
from app.services.types import PaginationParams, PaginatedResult

from .types import PaymentFilters


class VendorPaymentService:
    """Service for vendor payments."""

    def __init__(self, db: Session):
        self.db = db

    def list_payments(
        self,
        filters: PaymentFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[GLEntry]:
        """List vendor payments from GL entries."""
        query = self.db.query(GLEntry).filter(
            GLEntry.voucher_type == "Payment Entry",
            GLEntry.party_type == "Supplier",
            GLEntry.is_cancelled == False,
        )

        if filters.supplier:
            query = query.filter(GLEntry.party.ilike(f"%{filters.supplier}%"))

        if filters.start_date:
            query = query.filter(GLEntry.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(GLEntry.posting_date <= filters.end_date)

        total = query.count()
        payments = query.order_by(GLEntry.posting_date.desc()).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=payments, total=total)


class PurchaseOrderService:
    """Service for purchase orders."""

    def __init__(self, db: Session):
        self.db = db

    def list_orders(
        self,
        supplier: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> Dict[str, Any]:
        """List purchase orders from GL entries."""
        query = self.db.query(
            GLEntry.voucher_no,
            GLEntry.party,
            func.min(GLEntry.posting_date).label("date"),
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.voucher_type == "Purchase Order",
            GLEntry.is_cancelled == False,
        )

        if supplier:
            query = query.filter(GLEntry.party.ilike(f"%{supplier}%"))

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)

        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        query = query.group_by(GLEntry.voucher_no, GLEntry.party)

        total = query.count()

        if pagination:
            orders = query.order_by(func.min(GLEntry.posting_date).desc()).offset(pagination.offset).limit(pagination.limit).all()
        else:
            orders = query.order_by(func.min(GLEntry.posting_date).desc()).all()

        return {
            "total": total,
            "orders": [
                {
                    "order_no": o.voucher_no,
                    "supplier": o.party,
                    "date": o.date.isoformat() if o.date else None,
                    "total": float(o.total_debit or 0),
                }
                for o in orders
            ],
        }

    def get_order_detail(self, order_no: str) -> Dict[str, Any]:
        """Get purchase order details with linked bills."""
        gl_entries = self.db.query(GLEntry).filter(
            GLEntry.voucher_no == order_no,
            GLEntry.voucher_type == "Purchase Order",
            GLEntry.is_cancelled == False,
        ).all()

        if not gl_entries:
            from app.services.errors import NotFoundError
            raise NotFoundError(f"Purchase order {order_no} not found")

        supplier = gl_entries[0].party if gl_entries else None
        linked_bills = []

        if supplier:
            bills = self.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.supplier == supplier,
            ).limit(10).all()
            linked_bills = [
                {
                    "id": b.id,
                    "bill_no": b.erpnext_id,
                    "date": b.posting_date.isoformat() if b.posting_date else None,
                    "amount": float(b.grand_total),
                    "status": b.status.value if b.status else None,
                }
                for b in bills
            ]

        return {
            "order_no": order_no,
            "supplier": supplier,
            "date": gl_entries[0].posting_date.isoformat() if gl_entries and gl_entries[0].posting_date else None,
            "gl_entries": [
                {
                    "account": e.account,
                    "debit": float(e.debit),
                    "credit": float(e.credit),
                }
                for e in gl_entries
            ],
            "linked_bills": linked_bills,
        }


class DebitNoteService:
    """Service for debit notes (returns)."""

    def __init__(self, db: Session):
        self.db = db

    def list_debit_notes(
        self,
        supplier: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[PurchaseInvoice]:
        """List debit notes."""
        from sqlalchemy import or_
        from app.models.accounting import PurchaseInvoiceStatus

        query = self.db.query(PurchaseInvoice).filter(
            PurchaseInvoice.status == PurchaseInvoiceStatus.RETURN,
        )

        if supplier:
            query = query.filter(
                or_(
                    PurchaseInvoice.supplier.ilike(f"%{supplier}%"),
                    PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"),
                )
            )

        if start_date:
            query = query.filter(PurchaseInvoice.posting_date >= start_date)

        if end_date:
            query = query.filter(PurchaseInvoice.posting_date <= end_date)

        total = query.count()

        if pagination:
            notes = query.order_by(PurchaseInvoice.posting_date.desc()).offset(pagination.offset).limit(pagination.limit).all()
        else:
            notes = query.order_by(PurchaseInvoice.posting_date.desc()).all()

        return PaginatedResult(data=notes, total=total)

    def get_debit_note(self, note_id: int) -> Dict[str, Any]:
        """Get debit note details."""
        from app.models.accounting import PurchaseInvoiceStatus
        from app.services.errors import NotFoundError

        note = self.db.query(PurchaseInvoice).filter(
            PurchaseInvoice.id == note_id,
            PurchaseInvoice.status == PurchaseInvoiceStatus.RETURN,
        ).first()

        if not note:
            raise NotFoundError(f"Debit note {note_id} not found")

        # Get original invoice
        original_invoice = None
        return_against = getattr(note, "return_against", None)
        if return_against:
            original = self.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.erpnext_id == return_against
            ).first()
            if original:
                original_invoice = {
                    "id": original.id,
                    "erpnext_id": original.erpnext_id,
                    "grand_total": float(original.grand_total),
                    "posting_date": original.posting_date.isoformat() if original.posting_date else None,
                }

        return {
            "note": note,
            "original_invoice": original_invoice,
        }
