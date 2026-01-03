"""Debit Notes service.

This module contains business logic for AP debit notes.
All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.books_settings import DebitNote, DebitNoteStatus
from app.models.document_lines import DebitNoteLine
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .debit_notes_types import (
    DebitNoteFilters,
    DebitNoteCreateData,
    DebitNoteUpdateData,
    DebitNoteLineData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["DebitNoteService"]

# Allowed sort fields
ALLOWED_SORTS = {"posting_date", "debit_note_number", "total_amount", "status", "id", "created_at"}


class DebitNoteService:
    """Service for debit note business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def list_debit_notes(
        self,
        filters: Optional[DebitNoteFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[DebitNote]:
        """List debit notes with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing debit notes and total count.
        """
        if filters is None:
            filters = DebitNoteFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(DebitNote)
        query = scoped_query(query, self.principal)

        # Apply filters
        if filters.supplier_id:
            query = query.filter(DebitNote.supplier_id == filters.supplier_id)

        if filters.status:
            query = query.filter(DebitNote.status == filters.status)

        if filters.start_date:
            query = query.filter(DebitNote.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(DebitNote.posting_date <= filters.end_date)

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    DebitNote.debit_note_number.ilike(search_pattern),
                    DebitNote.supplier_name.ilike(search_pattern),
                    DebitNote.remarks.ilike(search_pattern),
                )
            )

        # Apply sorting
        sort_field = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "posting_date"
        sort_column = getattr(DebitNote, sort_field, DebitNote.posting_date)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc(), DebitNote.id.asc())
        else:
            query = query.order_by(sort_column.desc(), DebitNote.id.desc())

        return paginate(query, pagination)

    def get_debit_note(self, note_id: int) -> DebitNote:
        """Get debit note by ID.

        Args:
            note_id: The debit note ID.

        Returns:
            The DebitNote object with lines loaded.

        Raises:
            NotFoundError: If debit note not found.
        """
        note = (
            self.db.query(DebitNote)
            .filter(DebitNote.id == note_id)
            .first()
        )
        if not note:
            raise NotFoundError(f"Debit note {note_id} not found")
        return note

    def calculate_totals(
        self, lines: list[DebitNoteLineData]
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

    def create_debit_note(self, data: DebitNoteCreateData) -> DebitNote:
        """Create a new debit note.

        Generates debit note number automatically.

        Args:
            data: Debit note creation data.

        Returns:
            The created DebitNote (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        from app.services.number_generator import generate_voucher_number

        # Validate supplier
        if not data.supplier_id:
            raise ValidationError("supplier_id is required")

        # Validate conversion rate
        if data.conversion_rate <= Decimal("0"):
            raise ValidationError("Conversion rate must be positive")

        # Generate debit note number
        debit_note_number = generate_voucher_number(self.db, "debit_note")

        # Posting date defaults to issue date
        posting_date = data.posting_date or data.issue_date

        note = DebitNote(
            debit_note_number=debit_note_number,
            supplier_id=data.supplier_id,
            supplier_name=data.supplier_name,
            purchase_invoice_id=data.original_bill_id,
            remarks=data.description,
            posting_date=posting_date,
            currency=data.currency,
            conversion_rate=data.conversion_rate,
            company=data.company,
            status=DebitNoteStatus.DRAFT,
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(note)
        self.db.flush()

        # Add lines and calculate totals
        total_amount = Decimal("0")
        total_tax = Decimal("0")

        for idx, line_data in enumerate(data.lines):
            line = DebitNoteLine(
                debit_note_id=note.id,
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

        note.total_amount = total_amount + total_tax
        note.outstanding_amount = note.total_amount
        note.base_amount = note.total_amount * note.conversion_rate

        return note

    def update_debit_note(
        self, note_id: int, data: DebitNoteUpdateData
    ) -> DebitNote:
        """Update a debit note.

        Can only update draft notes.

        Args:
            note_id: The debit note ID.
            data: Fields to update.

        Returns:
            The updated DebitNote (not yet committed).

        Raises:
            NotFoundError: If debit note not found.
            ValidationError: If debit note is not in draft status.
        """
        note = self.get_debit_note(note_id)

        if note.status != DebitNoteStatus.DRAFT:
            raise ValidationError("Can only update draft debit notes")

        if data.description is not None:
            note.remarks = data.description

        if data.posting_date is not None:
            note.posting_date = data.posting_date

        if data.lines is not None:
            # Delete existing lines
            self.db.query(DebitNoteLine).filter(
                DebitNoteLine.debit_note_id == note_id
            ).delete()

            # Add new lines
            total_amount = Decimal("0")
            total_tax = Decimal("0")

            for idx, line_data in enumerate(data.lines):
                line = DebitNoteLine(
                    debit_note_id=note.id,
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

            note.total_amount = total_amount + total_tax
            note.outstanding_amount = note.total_amount
            note.base_amount = note.total_amount * note.conversion_rate

        return note

    def delete_debit_note(self, note_id: int) -> None:
        """Delete a debit note.

        Can only delete draft notes.

        Args:
            note_id: The debit note ID.

        Raises:
            NotFoundError: If debit note not found.
            ValidationError: If debit note is not in draft status.
        """
        note = self.get_debit_note(note_id)

        if note.status != DebitNoteStatus.DRAFT:
            raise ValidationError("Can only delete draft debit notes")

        self.db.delete(note)

    def submit_debit_note(self, note_id: int) -> DebitNote:
        """Submit a debit note (DRAFT -> ISSUED).

        Args:
            note_id: The debit note ID.

        Returns:
            The updated DebitNote.

        Raises:
            NotFoundError: If debit note not found.
            ValidationError: If debit note is not in draft status.
        """
        note = self.get_debit_note(note_id)

        if note.status != DebitNoteStatus.DRAFT:
            raise ValidationError("Can only submit draft debit notes")

        note.status = DebitNoteStatus.ISSUED
        note.workflow_status = "issued"
        note.docstatus = 1

        return note

    def cancel_debit_note(self, note_id: int, reason: Optional[str] = None) -> DebitNote:
        """Cancel a debit note.

        Args:
            note_id: The debit note ID.
            reason: Optional cancellation reason.

        Returns:
            The updated DebitNote.

        Raises:
            NotFoundError: If debit note not found.
            ValidationError: If debit note is already cancelled or applied.
        """
        note = self.get_debit_note(note_id)

        if note.status == DebitNoteStatus.CANCELLED:
            raise ValidationError("Debit note is already cancelled")

        if note.status == DebitNoteStatus.APPLIED:
            raise ValidationError("Cannot cancel applied debit notes")

        note.status = DebitNoteStatus.CANCELLED
        note.workflow_status = "cancelled"
        note.docstatus = 2

        return note

    def get_debit_note_stats(self) -> dict:
        """Get debit note statistics.

        Returns:
            Dict with counts by status.
        """
        from sqlalchemy import func

        query = scoped_query(self.db.query(DebitNote), self.principal)
        results = (
            query
            .with_entities(DebitNote.status, func.count(DebitNote.id))
            .group_by(DebitNote.status)
            .all()
        )

        stats = {status.value: 0 for status in DebitNoteStatus}
        for status, count in results:
            if status:
                stats[status.value] = count

        stats["total"] = sum(stats.values())
        return stats
