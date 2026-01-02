"""Invoice service - business logic for accounts receivable invoices.

This service encapsulates all invoice-related business logic:
- CRUD operations
- Workflow transitions (submit, post, cancel)
- Totals calculation
- GL posting via DocumentPostingService

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.document_lines import InvoiceLine
from app.models.invoice import Invoice, InvoiceSource, InvoiceStatus
from app.models.party import CustomerAccount
from app.services.base import paginate, safe_filter, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .invoice_types import InvoiceCreateData, InvoiceFilters, InvoiceUpdateData

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.accounting import JournalEntry

__all__ = ["InvoiceService"]

# Allowed filter fields for safe_filter
ALLOWED_FILTERS = {"customer_account_id", "status"}


class InvoiceService:
    """Service for invoice business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_invoices(
        self,
        filters: Optional[InvoiceFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Invoice]:
        """List invoices with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing invoices and total count.
        """
        if filters is None:
            filters = InvoiceFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Invoice).filter(Invoice.is_deleted == False)
        query = scoped_query(query, self.principal)

        # Apply simple equality filters
        filter_dict = {
            "customer_account_id": filters.customer_account_id,
            "status": filters.status,
        }
        query = safe_filter(query, Invoice, filter_dict, ALLOWED_FILTERS)

        # Date range filters
        if filters.start_date:
            query = query.filter(Invoice.invoice_date >= filters.start_date)
        if filters.end_date:
            query = query.filter(Invoice.invoice_date <= filters.end_date)

        # Overdue filter
        if filters.overdue_only:
            query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

        # Default ordering
        query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())

        return paginate(query, pagination)

    def get_invoice(self, invoice_id: int) -> Invoice:
        """Get an invoice by ID.

        Args:
            invoice_id: The invoice ID.

        Returns:
            The Invoice object with lines loaded.

        Raises:
            NotFoundError: If invoice not found or soft-deleted.
        """
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.is_deleted == False)
            .first()
        )
        if not invoice:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_invoice(self, data: InvoiceCreateData) -> Invoice:
        """Create a new invoice in draft status.

        Validates customer, generates invoice number if not provided,
        creates lines, and calculates totals.

        Args:
            data: Invoice creation data.

        Returns:
            The created Invoice (not yet committed).

        Raises:
            ValidationError: If validation fails (e.g., customer not found).
        """
        from app.services.number_generator import generate_voucher_number

        # Validate customer exists
        customer_account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.id == data.customer_account_id)
            .first()
        )
        if not customer_account:
            raise ValidationError(f"Customer account {data.customer_account_id} not found")

        # Require at least one line
        if not data.lines:
            raise ValidationError("At least one line item is required")

        # Generate invoice number if not provided
        invoice_number = data.invoice_number
        if not invoice_number:
            invoice_number = generate_voucher_number(self.db, "invoice")

        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            customer_account_id=data.customer_account_id,
            description=data.description,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            posting_date=data.posting_date or data.invoice_date,
            currency=data.currency,
            conversion_rate=data.conversion_rate,
            payment_terms_id=data.payment_terms_id,
            company=data.company,
            category=data.category,
            source=InvoiceSource.INTERNAL,
            status=InvoiceStatus.DRAFT,
            docstatus=0,
            workflow_status="draft",
            created_by_id=self.principal.id if self.principal else None,
            origin_system="local",
        )

        self.db.add(invoice)
        self.db.flush()  # Get invoice.id for line FK

        # Create lines and calculate totals
        total_amount = Decimal("0")
        total_tax = Decimal("0")

        for idx, line_data in enumerate(data.lines):
            line = InvoiceLine(
                invoice_id=invoice.id,
                item_code=line_data.item_code,
                item_name=line_data.item_name,
                description=line_data.description,
                quantity=line_data.quantity,
                rate=line_data.rate,
                amount=line_data.amount,
                tax_code_id=line_data.tax_code_id,
                tax_rate=line_data.tax_rate,
                tax_amount=line_data.tax_amount,
                account=line_data.account,
                cost_center=line_data.cost_center,
                idx=idx,
            )
            self.db.add(line)
            total_amount += line_data.amount
            total_tax += line_data.tax_amount

        # Set totals
        invoice.amount = total_amount
        invoice.tax_amount = total_tax
        invoice.total_amount = total_amount + total_tax
        invoice.balance = invoice.total_amount
        invoice.amount_paid = Decimal("0")
        invoice.base_amount = invoice.amount * invoice.conversion_rate
        invoice.base_tax_amount = invoice.tax_amount * invoice.conversion_rate
        invoice.base_total_amount = invoice.total_amount * invoice.conversion_rate

        return invoice

    def update_invoice(self, invoice_id: int, data: InvoiceUpdateData) -> Invoice:
        """Update a draft invoice.

        Args:
            invoice_id: The invoice ID.
            data: Fields to update.

        Returns:
            The updated Invoice (not yet committed).

        Raises:
            NotFoundError: If invoice not found.
            ValidationError: If invoice is not a draft or customer invalid.
        """
        invoice = self.get_invoice(invoice_id)

        if invoice.docstatus != 0:
            raise ValidationError("Can only update draft invoices")

        # Validate customer if changing
        if data.customer_account_id is not None:
            customer_account = (
                self.db.query(CustomerAccount)
                .filter(CustomerAccount.id == data.customer_account_id)
                .first()
            )
            if not customer_account:
                raise ValidationError(f"Customer account {data.customer_account_id} not found")
            invoice.customer_account_id = data.customer_account_id

        if data.description is not None:
            invoice.description = data.description

        if data.invoice_date is not None:
            invoice.invoice_date = data.invoice_date

        if data.due_date is not None:
            invoice.due_date = data.due_date

        if data.posting_date is not None:
            invoice.posting_date = data.posting_date

        if data.currency is not None:
            invoice.currency = data.currency

        if data.conversion_rate is not None:
            invoice.conversion_rate = data.conversion_rate
            # Recalculate base amounts
            invoice.base_amount = invoice.amount * invoice.conversion_rate
            invoice.base_tax_amount = invoice.tax_amount * invoice.conversion_rate
            invoice.base_total_amount = invoice.total_amount * invoice.conversion_rate

        if data.payment_terms_id is not None:
            invoice.payment_terms_id = data.payment_terms_id

        if data.category is not None:
            invoice.category = data.category

        invoice.updated_by_id = self.principal.id if self.principal else None

        return invoice

    def delete_invoice(self, invoice_id: int) -> None:
        """Soft delete a draft invoice.

        Args:
            invoice_id: The invoice ID.

        Raises:
            NotFoundError: If invoice not found.
            ValidationError: If invoice is not a draft.
        """
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .first()
        )
        if not invoice:
            raise NotFoundError(f"Invoice {invoice_id} not found")

        if invoice.docstatus != 0:
            raise ValidationError("Can only delete draft invoices")

        invoice.is_deleted = True
        invoice.deleted_at = datetime.now(timezone.utc)
        invoice.deleted_by_id = self.principal.id if self.principal else None

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------

    def submit_invoice(self, invoice_id: int) -> Invoice:
        """Submit an invoice for approval (draft → pending).

        Args:
            invoice_id: The invoice ID.

        Returns:
            The updated Invoice.

        Raises:
            NotFoundError: If invoice not found.
            ValidationError: If invoice is not a draft.
        """
        invoice = self.get_invoice(invoice_id)

        if invoice.docstatus != 0:
            raise ValidationError("Can only submit draft invoices")

        invoice.status = InvoiceStatus.PENDING
        invoice.workflow_status = "pending"

        return invoice

    def post_invoice(self, invoice_id: int) -> Tuple[Invoice, "JournalEntry"]:
        """Post invoice to GL - creates AR debit, revenue credit.

        Args:
            invoice_id: The invoice ID.

        Returns:
            Tuple of (Invoice, JournalEntry).

        Raises:
            NotFoundError: If invoice not found.
            ValidationError: If invoice already posted or posting fails.
        """
        from app.services.document_posting import DocumentPostingService, PostingError

        invoice = self.get_invoice(invoice_id)

        if invoice.docstatus != 0:
            raise ValidationError("Invoice already posted or cancelled")

        posting_service = DocumentPostingService(self.db)
        try:
            je = posting_service.post_invoice(
                invoice_id,
                self.principal.id if self.principal else None,
            )
        except PostingError as e:
            raise ValidationError(str(e)) from e

        invoice.docstatus = 1
        invoice.status = InvoiceStatus.PENDING  # Will become UNPAID after commit
        invoice.workflow_status = "posted"
        invoice.journal_entry_id = je.id

        return invoice, je

    def cancel_invoice(
        self, invoice_id: int, reason: str
    ) -> Tuple[Invoice, Optional["JournalEntry"]]:
        """Cancel a posted invoice (creates reversal journal entry).

        Args:
            invoice_id: The invoice ID.
            reason: Cancellation reason (required).

        Returns:
            Tuple of (Invoice, reversal JournalEntry or None).

        Raises:
            NotFoundError: If invoice not found.
            ValidationError: If invoice not posted or has payments.
        """
        from app.services.document_posting import DocumentPostingService, PostingError

        invoice = self.get_invoice(invoice_id)

        if invoice.docstatus != 1:
            raise ValidationError("Can only cancel posted invoices")

        if invoice.amount_paid and invoice.amount_paid > 0:
            raise ValidationError(
                "Cannot cancel invoice with payments. Reverse payments first."
            )

        posting_service = DocumentPostingService(self.db)
        try:
            reversal_je = posting_service.reverse_invoice(
                invoice_id,
                self.principal.id if self.principal else None,
                reason,
            )
        except PostingError as e:
            raise ValidationError(str(e)) from e

        invoice.docstatus = 2
        invoice.status = InvoiceStatus.CANCELLED
        invoice.workflow_status = "cancelled"

        return invoice, reversal_je
