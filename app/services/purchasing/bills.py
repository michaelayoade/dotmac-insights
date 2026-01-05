"""Bill (Purchase Invoice) Service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
    GLEntry,
)
from app.models.document_lines import BillLine
from app.services.validation.soft_validation_service import SoftValidationService
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError
from app.utils.company_context import get_company_context

from .types import BillFilters, BillCreateData, BillUpdateData


class BillService:
    """Service for purchase invoice (bill) management."""

    def __init__(self, db: Session):
        self.db = db

    def list_bills(
        self,
        filters: BillFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[PurchaseInvoice]:
        """List bills with filtering and pagination."""
        query = self.db.query(PurchaseInvoice)

        # Apply filters
        if filters.status:
            try:
                status_enum = PurchaseInvoiceStatus(filters.status.lower())
                query = query.filter(PurchaseInvoice.status == status_enum)
            except ValueError:
                raise ValidationError(f"Invalid status: {filters.status}")

        if filters.supplier:
            query = query.filter(
                or_(
                    PurchaseInvoice.supplier.ilike(f"%{filters.supplier}%"),
                    PurchaseInvoice.supplier_name.ilike(f"%{filters.supplier}%"),
                )
            )

        if filters.currency:
            query = query.filter(PurchaseInvoice.currency == filters.currency)

        if filters.start_date:
            query = query.filter(PurchaseInvoice.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(PurchaseInvoice.posting_date <= filters.end_date)

        if filters.min_amount is not None:
            query = query.filter(PurchaseInvoice.grand_total >= filters.min_amount)

        if filters.max_amount is not None:
            query = query.filter(PurchaseInvoice.grand_total <= filters.max_amount)

        if filters.overdue_only:
            query = query.filter(
                PurchaseInvoice.due_date < date.today(),
                PurchaseInvoice.outstanding_amount > 0,
            )

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(PurchaseInvoice, filters.sort_by, PurchaseInvoice.posting_date)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        # Apply pagination
        bills = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=bills, total=total)

    def get_bill(self, bill_id: int) -> PurchaseInvoice:
        """Get a bill by ID."""
        bill = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == bill_id).first()
        if not bill:
            raise NotFoundError(f"Bill {bill_id} not found")
        return bill

    def get_bill_detail(self, bill_id: int) -> Dict[str, Any]:
        """Get detailed bill information with line items and GL entries."""
        bill = self.get_bill(bill_id)

        # Get bill line items
        bill_lines = self.db.query(BillLine).filter(
            BillLine.purchase_invoice_id == bill.id
        ).order_by(BillLine.idx).all()

        # Get related GL entries
        gl_entries = []
        if bill.erpnext_id:
            gl_entries = self.db.query(GLEntry).filter(
                GLEntry.voucher_no == bill.erpnext_id,
                GLEntry.voucher_type == "Purchase Invoice",
            ).all()

        return {
            "bill": bill,
            "lines": bill_lines,
            "gl_entries": gl_entries,
        }

    def create_bill(self, data: BillCreateData) -> PurchaseInvoice:
        """Create a new purchase invoice."""
        # Validate supplier if provided
        if data.supplier_id:
            supplier_exists = self.db.query(Supplier.id).filter(
                Supplier.id == data.supplier_id
            ).first()
            if not supplier_exists:
                raise ValidationError(f"Supplier {data.supplier_id} not found")

        # Parse status
        status_enum = PurchaseInvoiceStatus.DRAFT
        if data.status:
            try:
                status_enum = PurchaseInvoiceStatus(data.status)
            except ValueError:
                raise ValidationError(f"Invalid status: {data.status}")

        bill = PurchaseInvoice(
            bill_number=data.bill_number,
            supplier=data.supplier,
            supplier_name=data.supplier_name,
            supplier_id=data.supplier_id,
            company=data.company or get_company_context(allow_null=True),
            supplier_tax_id=data.supplier_tax_id,
            supplier_address=data.supplier_address,
            posting_date=data.posting_date,
            due_date=data.due_date,
            grand_total=data.grand_total,
            outstanding_amount=data.outstanding_amount,
            paid_amount=data.paid_amount,
            tax_amount=data.tax_amount,
            currency=data.currency,
            status=status_enum,
            docstatus=data.docstatus,
            is_return=data.is_return,
            workflow_status=data.workflow_status,
            fiscal_period_id=data.fiscal_period_id,
            journal_entry_id=data.journal_entry_id,
        )
        self.db.add(bill)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(bill)
        return bill

    def update_bill(self, bill_id: int, data: BillUpdateData) -> PurchaseInvoice:
        """Update a purchase invoice."""
        bill = self.get_bill(bill_id)

        # Validate supplier if being updated
        if data.supplier_id is not None:
            supplier_exists = self.db.query(Supplier.id).filter(
                Supplier.id == data.supplier_id
            ).first()
            if not supplier_exists:
                raise ValidationError(f"Supplier {data.supplier_id} not found")

        # Apply updates
        update_fields = [
            'bill_number', 'supplier_id', 'supplier', 'supplier_name', 'company',
            'supplier_tax_id', 'supplier_address', 'posting_date', 'due_date',
            'grand_total', 'outstanding_amount', 'paid_amount', 'tax_amount',
            'currency', 'docstatus', 'is_return', 'workflow_status',
            'fiscal_period_id', 'journal_entry_id',
        ]

        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(bill, field_name, value)

        # Handle status separately
        if data.status is not None:
            try:
                bill.status = PurchaseInvoiceStatus(data.status)
            except ValueError:
                raise ValidationError(f"Invalid status: {data.status}")

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(bill)
        return bill

    def delete_bill(self, bill_id: int) -> None:
        """Delete a purchase invoice."""
        bill = self.get_bill(bill_id)
        self.db.delete(bill)
        self.db.flush()

    def get_overdue_bills(self, as_of_date: Optional[date] = None) -> List[PurchaseInvoice]:
        """Get all overdue bills."""
        cutoff = as_of_date or date.today()
        return self.db.query(PurchaseInvoice).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < cutoff,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ])
        ).all()

    def get_bills_due_soon(self, days: int = 7) -> List[PurchaseInvoice]:
        """Get bills due within the specified number of days."""
        from datetime import timedelta
        today = date.today()
        end_date = today + timedelta(days=days)

        return self.db.query(PurchaseInvoice).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date >= today,
            PurchaseInvoice.due_date <= end_date,
        ).all()
