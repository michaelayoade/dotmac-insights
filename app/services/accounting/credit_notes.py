"""Credit Notes service.

This module contains business logic for AR credit notes.
All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.document_lines import CreditNoteLine
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .credit_notes_types import (
    CreditNoteFilters,
    CreditNoteCreateData,
    CreditNoteUpdateData,
    CreditNoteLineData,
)
from app.services.validation.soft_validation_service import SoftValidationService

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["CreditNoteService"]

# Allowed sort fields
ALLOWED_SORTS = {"issue_date", "credit_number", "amount", "status", "id", "created_at"}


class CreditNoteService:
    """Service for credit note business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def list_credit_notes(
        self,
        filters: Optional[CreditNoteFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[CreditNote]:
        """List credit notes with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing credit notes and total count.
        """
        if filters is None:
            filters = CreditNoteFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(CreditNote)
        query = scoped_query(query, self.principal)

        # Apply filters
        if filters.customer_account_id:
            query = query.filter(CreditNote.customer_account_id == filters.customer_account_id)

        if filters.status:
            query = query.filter(CreditNote.status == filters.status)

        if filters.start_date:
            query = query.filter(CreditNote.issue_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(CreditNote.issue_date <= filters.end_date)

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    CreditNote.credit_number.ilike(search_pattern),
                    CreditNote.description.ilike(search_pattern),
                )
            )

        # Apply sorting
        sort_field = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "issue_date"
        sort_column = getattr(CreditNote, sort_field, CreditNote.issue_date)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc(), CreditNote.id.asc())
        else:
            query = query.order_by(sort_column.desc(), CreditNote.id.desc())

        return paginate(query, pagination)

    def get_credit_note(self, note_id: int) -> CreditNote:
        """Get credit note by ID.

        Args:
            note_id: The credit note ID.

        Returns:
            The CreditNote object with lines loaded.

        Raises:
            NotFoundError: If credit note not found.
        """
        note = (
            self.db.query(CreditNote)
            .filter(CreditNote.id == note_id)
            .first()
        )
        if not note:
            raise NotFoundError(f"Credit note {note_id} not found")
        return note

    def calculate_totals(
        self, lines: list[CreditNoteLineData]
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate totals from lines.

        Args:
            lines: List of line data.

        Returns:
            Tuple of (amount, tax_amount, total_amount).
        """
        amount = Decimal("0")
        tax_amount = Decimal("0")

        for line in lines:
            amount += line.amount
            tax_amount += line.tax_amount

        return amount, tax_amount, amount + tax_amount

    def create_credit_note(self, data: CreditNoteCreateData) -> CreditNote:
        """Create a new credit note.

        Generates credit note number if not provided.

        Args:
            data: Credit note creation data.

        Returns:
            The created CreditNote (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        from app.services.number_generator import generate_voucher_number

        # Validate customer exists
        if not data.customer_account_id:
            raise ValidationError("customer_account_id is required")

        # Validate conversion rate
        if data.conversion_rate <= Decimal("0"):
            raise ValidationError("Conversion rate must be positive")

        # Generate credit number if not provided
        credit_number = data.credit_number
        if not credit_number:
            credit_number = generate_voucher_number(self.db, "credit_note")

        note = CreditNote(
            credit_number=credit_number,
            customer_account_id=data.customer_account_id,
            invoice_id=data.invoice_id,
            description=data.description,
            issue_date=data.issue_date,
            posting_date=data.posting_date or data.issue_date,
            currency=data.currency,
            conversion_rate=data.conversion_rate,
            company=data.company,
            status=CreditNoteStatus.DRAFT,
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(note)
        self.db.flush()

        # Add lines and calculate totals
        total_amount = Decimal("0")
        total_tax = Decimal("0")
        created_lines = []

        for idx, line_data in enumerate(data.lines):
            line = CreditNoteLine(
                credit_note_id=note.id,
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
                return_reason=line_data.return_reason,
                idx=idx,
            )
            self.db.add(line)
            created_lines.append(line)
            total_amount += line_data.amount
            total_tax += line_data.tax_amount

        note.amount = total_amount
        note.tax_amount = total_tax
        note.total_amount = total_amount + total_tax
        note.base_amount = note.amount * note.conversion_rate
        note.base_tax_amount = note.tax_amount * note.conversion_rate

        validator = SoftValidationService(self.db)
        for line in created_lines:
            validator.validate_and_store(line)
        validator.validate_and_store(note)

        return note

    def update_credit_note(
        self, note_id: int, data: CreditNoteUpdateData
    ) -> CreditNote:
        """Update a credit note.

        Can only update draft notes.

        Args:
            note_id: The credit note ID.
            data: Fields to update.

        Returns:
            The updated CreditNote (not yet committed).

        Raises:
            NotFoundError: If credit note not found.
            ValidationError: If credit note is not in draft status.
        """
        note = self.get_credit_note(note_id)

        if note.status != CreditNoteStatus.DRAFT:
            raise ValidationError("Can only update draft credit notes")

        if data.description is not None:
            note.description = data.description

        if data.issue_date is not None:
            note.issue_date = data.issue_date

        if data.posting_date is not None:
            note.posting_date = data.posting_date

        if data.lines is not None:
            # Delete existing lines
            self.db.query(CreditNoteLine).filter(
                CreditNoteLine.credit_note_id == note_id
            ).delete()

            # Add new lines
            total_amount = Decimal("0")
            total_tax = Decimal("0")

            for idx, line_data in enumerate(data.lines):
                line = CreditNoteLine(
                    credit_note_id=note.id,
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
                    return_reason=line_data.return_reason,
                    idx=idx,
                )
                self.db.add(line)
                total_amount += line_data.amount
                total_tax += line_data.tax_amount

            note.amount = total_amount
            note.tax_amount = total_tax
            note.total_amount = total_amount + total_tax
            note.base_amount = note.amount * note.conversion_rate
            note.base_tax_amount = note.tax_amount * note.conversion_rate

        validator = SoftValidationService(self.db)
        if data.lines is not None:
            for line in self.db.query(CreditNoteLine).filter(CreditNoteLine.credit_note_id == note_id).all():
                validator.validate_and_store(line)
        validator.validate_and_store(note)

        return note

    def delete_credit_note(self, note_id: int) -> None:
        """Delete a credit note.

        Can only delete draft notes.

        Args:
            note_id: The credit note ID.

        Raises:
            NotFoundError: If credit note not found.
            ValidationError: If credit note is not in draft status.
        """
        note = self.get_credit_note(note_id)

        if note.status != CreditNoteStatus.DRAFT:
            raise ValidationError("Can only delete draft credit notes")

        self.db.delete(note)

    def submit_credit_note(self, note_id: int) -> CreditNote:
        """Submit a credit note (DRAFT -> ISSUED).

        Args:
            note_id: The credit note ID.

        Returns:
            The updated CreditNote.

        Raises:
            NotFoundError: If credit note not found.
            ValidationError: If credit note is not in draft status.
        """
        note = self.get_credit_note(note_id)

        if note.status != CreditNoteStatus.DRAFT:
            raise ValidationError("Can only submit draft credit notes")

        note.status = CreditNoteStatus.ISSUED
        note.workflow_status = "issued"
        note.docstatus = 1

        return note

    def cancel_credit_note(self, note_id: int, reason: Optional[str] = None) -> CreditNote:
        """Cancel a credit note.

        Args:
            note_id: The credit note ID.
            reason: Optional cancellation reason.

        Returns:
            The updated CreditNote.

        Raises:
            NotFoundError: If credit note not found.
            ValidationError: If credit note is already cancelled or applied.
        """
        note = self.get_credit_note(note_id)

        if note.status == CreditNoteStatus.CANCELLED:
            raise ValidationError("Credit note is already cancelled")

        if note.status == CreditNoteStatus.APPLIED:
            raise ValidationError("Cannot cancel applied credit notes")

        note.status = CreditNoteStatus.CANCELLED
        note.workflow_status = "cancelled"
        note.docstatus = 2

        return note

    def get_credit_note_stats(self) -> dict:
        """Get credit note statistics.

        Returns:
            Dict with counts by status.
        """
        from sqlalchemy import func

        query = scoped_query(self.db.query(CreditNote), self.principal)
        results = (
            query
            .with_entities(CreditNote.status, func.count(CreditNote.id))
            .group_by(CreditNote.status)
            .all()
        )

        stats = {status.value: 0 for status in CreditNoteStatus}
        for status, count in results:
            if status:
                stats[status.value] = count

        stats["total"] = sum(stats.values())
        return stats
