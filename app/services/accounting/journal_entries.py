"""Journal Entry service - business logic for journal entries.

This service encapsulates all journal entry-related business logic:
- CRUD operations
- Validation via JEValidator
- Workflow (submit, approve, reject, post)
- Audit logging

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.accounting import (
    Account,
    GLEntry,
    JournalEntry,
    JournalEntryItem,
    JournalEntryType,
)
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.services.activity_logger import ActivityLogger
from app.services.validation.soft_validation_service import SoftValidationService

from .journal_entry_types import (
    JECreateData,
    JEFilters,
    JELineData,
    JEUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["JournalEntryService"]

ALLOWED_SORTS = {
    "posting_date",
    "voucher_type",
    "company",
    "docstatus",
    "erpnext_id",
    "id",
}

class JournalEntryService:
    """Service for journal entry business logic.

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

    def list_entries(
        self,
        filters: Optional[JEFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[JournalEntry]:
        """List journal entries with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing journal entries and total count.
        """
        if filters is None:
            filters = JEFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(JournalEntry)
        query = scoped_query(query, self.principal)

        if filters.start_date:
            query = query.filter(JournalEntry.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(JournalEntry.posting_date <= filters.end_date)

        if filters.voucher_type:
            query = query.filter(JournalEntry.voucher_type == filters.voucher_type)

        if filters.company:
            query = query.filter(JournalEntry.company == filters.company)

        if filters.is_opening is not None:
            query = query.filter(JournalEntry.is_opening == filters.is_opening)

        if filters.docstatus is not None:
            query = query.filter(JournalEntry.docstatus == filters.docstatus)

        if filters.search:
            if len(filters.search) < 2:
                raise ValidationError("Search query must be at least 2 characters")
            query = query.filter(
                or_(
                    JournalEntry.erpnext_id.ilike(f"%{filters.search}%"),
                    JournalEntry.user_remark.ilike(f"%{filters.search}%"),
                    JournalEntry.cheque_no.ilike(f"%{filters.search}%"),
                )
            )

        sort_key = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "posting_date"
        sort_column = getattr(JournalEntry, sort_key, JournalEntry.posting_date)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc(), JournalEntry.id.asc())
        else:
            query = query.order_by(sort_column.desc(), JournalEntry.id.desc())

        return paginate(query, pagination)

    def get_entry(self, entry_id: int) -> JournalEntry:
        """Get a journal entry by ID.

        Args:
            entry_id: The journal entry ID.

        Returns:
            The JournalEntry object.

        Raises:
            NotFoundError: If entry not found.
        """
        entry = (
            self.db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id)
            .first()
        )
        if not entry:
            raise NotFoundError(f"Journal entry {entry_id} not found")
        return entry

    def get_entry_lines(self, entry_id: int) -> List[GLEntry]:
        """Get GL entries (line items) for a journal entry.

        Args:
            entry_id: The journal entry ID.

        Returns:
            List of GLEntry objects.
        """
        entry = self.get_entry(entry_id)
        return (
            self.db.query(GLEntry)
            .filter(
                GLEntry.voucher_no == entry.erpnext_id,
                GLEntry.voucher_type == "Journal Entry",
            )
            .order_by(GLEntry.id)
            .all()
        )

    def get_entry_stats(self) -> dict:
        """Get summary stats for journal entries list view."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_count = self.db.query(func.count(JournalEntry.id)).scalar() or 0

        draft_count = self.db.query(func.count(JournalEntry.id)).filter(
            JournalEntry.docstatus == 0
        ).scalar() or 0

        posted_count = self.db.query(func.count(JournalEntry.id)).filter(
            JournalEntry.docstatus == 1
        ).scalar() or 0

        this_month = self.db.query(func.count(JournalEntry.id)).filter(
            JournalEntry.posting_date >= month_start,
            JournalEntry.docstatus == 1,
        ).scalar() or 0

        return {
            "total_count": total_count,
            "draft_count": draft_count,
            "posted_count": posted_count,
            "this_month": this_month,
        }

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_entry(self, data: JECreateData) -> JournalEntry:
        """Create a new journal entry.

        Validates the entry using JEValidator and creates the entry
        with its line items.

        Args:
            data: Journal entry creation data.

        Returns:
            The created JournalEntry (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        from app.services.audit_logger import AuditLogger, serialize_for_audit
        from app.services.je_validator import JEValidator
        from app.services.je_validator import ValidationError as JEValidationError

        user_remark = data.user_remark
        if user_remark is None and data.description:
            user_remark = data.description

        # Create JE
        company = data.company or "Default Company"
        je = JournalEntry(
            voucher_type=data.voucher_type,
            posting_date=datetime.combine(data.posting_date, datetime.min.time()),
            user_remark=user_remark,
            cheque_no=data.cheque_no,
            company=company,
            is_opening=data.is_opening,
            total_debit=Decimal("0"),
            total_credit=Decimal("0"),
            docstatus=0,  # Draft
        )

        # Parse account lines
        je_accounts: List[JournalEntryItem] = []
        for line_data in data.lines:
            account_name = line_data.account
            account_id = line_data.account_id

            if not account_name and account_id:
                account = (
                    self.db.query(Account).filter(Account.id == account_id).first()
                )
                if not account:
                    raise ValidationError(f"Account {account_id} not found")
                account_name = account.account_name
            elif account_name and not account_id:
                account = (
                    self.db.query(Account)
                    .filter(Account.account_name == account_name)
                    .first()
                )
                if account:
                    account_id = account.id

            if not account_name:
                raise ValidationError(
                    "Account is required for journal entry lines"
                )
            if account_id is None:
                raise ValidationError(
                    f"Account '{account_name}' not found in chart of accounts"
                )

            je_acc = JournalEntryItem(
                account=account_name,
                account_id=account_id,
                debit=line_data.debit,
                credit=line_data.credit,
                debit_in_account_currency=line_data.debit,
                credit_in_account_currency=line_data.credit,
                exchange_rate=Decimal("1"),
                party_type=line_data.party_type,
                party=line_data.party,
                cost_center=line_data.cost_center,
            )
            je_accounts.append(je_acc)

        # Validate
        validator = JEValidator(self.db)
        try:
            validator.validate_or_raise(je, je_accounts)
        except JEValidationError as e:
            raise ValidationError("; ".join(e.errors)) from e

        # Calculate totals
        je.total_debit = sum(
            (a.debit or Decimal("0") for a in je_accounts), Decimal("0")
        )
        je.total_credit = sum(
            (a.credit or Decimal("0") for a in je_accounts), Decimal("0")
        )

        self.db.add(je)
        self.db.flush()

        # Add account lines
        for idx, acc in enumerate(je_accounts, 1):
            acc.journal_entry_id = je.id
            acc.idx = idx
            self.db.add(acc)

        validator = SoftValidationService(self.db)
        for acc in je_accounts:
            validator.validate_and_store(acc)
        validator.validate_and_store(je)

        # Audit log
        audit = AuditLogger(self.db)
        audit.log_create(
            doctype="journal_entry",
            document_id=je.id,
            user_id=self.principal.id if self.principal else None,
            new_values=serialize_for_audit(je),
        )

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.journal_entry.create",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="journal_entry",
            entity_id=str(je.id),
            summary=f"Created journal entry {je.id}",
            metadata={"total_debit": float(je.total_debit), "total_credit": float(je.total_credit)},
        )
        return je

    def update_entry(self, entry_id: int, data: JEUpdateData) -> JournalEntry:
        """Update a draft journal entry.

        Args:
            entry_id: The journal entry ID.
            data: Fields to update.

        Returns:
            The updated JournalEntry (not yet committed).

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry is not a draft.
        """
        from app.services.audit_logger import AuditLogger, serialize_for_audit

        je = self.get_entry(entry_id)

        if je.docstatus != 0:
            raise ValidationError("Can only update draft entries")

        old_values = serialize_for_audit(je)

        if data.posting_date is not None:
            je.posting_date = datetime.combine(data.posting_date, datetime.min.time())

        if data.user_remark is not None:
            je.user_remark = data.user_remark

        if data.cheque_no is not None:
            je.cheque_no = data.cheque_no

        if data.company is not None:
            je.company = data.company

        je.updated_at = datetime.now(timezone.utc)

        # Audit log
        audit = AuditLogger(self.db)
        audit.log_update(
            doctype="journal_entry",
            document_id=je.id,
            user_id=self.principal.id if self.principal else None,
            old_values=old_values,
            new_values=serialize_for_audit(je),
        )

        SoftValidationService(self.db).validate_and_store(je)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.journal_entry.update",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="journal_entry",
            entity_id=str(je.id),
            summary=f"Updated journal entry {je.id}",
        )
        return je

    def update_entry_with_lines(self, entry_id: int, data: JECreateData) -> JournalEntry:
        """Update a draft journal entry with new line items."""
        from app.services.audit_logger import AuditLogger, serialize_for_audit
        from app.services.je_validator import JEValidator
        from app.services.je_validator import ValidationError as JEValidationError

        je = self.get_entry(entry_id)
        if je.docstatus != 0:
            raise ValidationError("Can only update draft entries")

        old_values = serialize_for_audit(je)

        # Update header fields
        je.voucher_type = data.voucher_type
        je.posting_date = datetime.combine(data.posting_date, datetime.min.time())
        je.user_remark = data.user_remark
        je.cheque_no = data.cheque_no
        je.company = data.company or je.company
        je.is_opening = data.is_opening

        # Build account lines
        je_accounts: List[JournalEntryItem] = []
        for line_data in data.lines:
            account_name = line_data.account
            account_id = line_data.account_id

            if not account_name and account_id:
                account = (
                    self.db.query(Account).filter(Account.id == account_id).first()
                )
                if not account:
                    raise ValidationError(f"Account {account_id} not found")
                account_name = account.account_name
            elif account_name and not account_id:
                account = (
                    self.db.query(Account)
                    .filter(Account.account_name == account_name)
                    .first()
                )
                if account:
                    account_id = account.id

            if not account_name:
                raise ValidationError("Account is required")
            if account_id is None:
                raise ValidationError(f"Account '{account_name}' not found in chart of accounts")

            je_acc = JournalEntryItem(
                account=account_name,
                account_id=account_id,
                debit=line_data.debit,
                credit=line_data.credit,
                party_type=line_data.party_type,
                party=line_data.party,
                cost_center=line_data.cost_center,
                description=line_data.description,
                user_remark=line_data.user_remark,
            )
            je_accounts.append(je_acc)

        # Validate
        validator = JEValidator(self.db)
        try:
            validator.validate_or_raise(je, je_accounts)
        except JEValidationError as exc:
            raise ValidationError(str(exc)) from exc

        total_debit = sum((a.debit or Decimal("0") for a in je_accounts), Decimal("0"))
        total_credit = sum((a.credit or Decimal("0") for a in je_accounts), Decimal("0"))

        je.total_debit = total_debit
        je.total_credit = total_credit
        je.updated_at = datetime.now(timezone.utc)

        # Replace items
        self.db.query(JournalEntryItem).filter(
            JournalEntryItem.journal_entry_id == je.id
        ).delete()

        for idx, acc in enumerate(je_accounts, 1):
            acc.journal_entry_id = je.id
            acc.idx = idx
            self.db.add(acc)

        validator = SoftValidationService(self.db)
        for acc in je_accounts:
            validator.validate_and_store(acc)
        validator.validate_and_store(je)

        # Audit log
        audit = AuditLogger(self.db)
        audit.log_update(
            doctype="journal_entry",
            document_id=je.id,
            user_id=self.principal.id if self.principal else None,
            old_values=old_values,
            new_values=serialize_for_audit(je),
        )

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.journal_entry.update",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="journal_entry",
            entity_id=str(je.id),
            summary=f"Updated journal entry {je.id}",
            metadata={"with_lines": True},
        )
        return je

    def delete_entry(self, entry_id: int) -> None:
        """Delete a draft journal entry.

        Args:
            entry_id: The journal entry ID.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry is not a draft.
        """
        from app.services.audit_logger import AuditLogger, serialize_for_audit

        je = self.get_entry(entry_id)

        if je.docstatus != 0:
            raise ValidationError("Can only delete draft entries")

        old_values = serialize_for_audit(je)

        # Audit log before delete
        audit = AuditLogger(self.db)
        audit.log_delete(
            doctype="journal_entry",
            document_id=je.id,
            user_id=self.principal.id if self.principal else None,
            old_values=old_values,
        )

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.journal_entry.delete",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="journal_entry",
            entity_id=str(je.id),
            summary=f"Deleted journal entry {je.id}",
        )
        self.db.delete(je)

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------

    def submit_entry(self, entry_id: int) -> JournalEntry:
        """Submit a journal entry for approval.

        Args:
            entry_id: The journal entry ID.

        Returns:
            The submitted JournalEntry with approval info.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If submission fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        je = self.get_entry(entry_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.submit_document(
                doctype="journal_entry",
                document_id=entry_id,
                user_id=self.principal.id if self.principal else None,
                amount=je.total_debit,
                document_name=je.erpnext_id,
            )
            return je
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def approve_entry(
        self, entry_id: int, remarks: Optional[str] = None
    ) -> JournalEntry:
        """Approve a journal entry at the current step.

        Args:
            entry_id: The journal entry ID.
            remarks: Approval remarks.

        Returns:
            The approved JournalEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If approval fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        je = self.get_entry(entry_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.approve_document(
                doctype="journal_entry",
                document_id=entry_id,
                user_id=self.principal.id if self.principal else None,
                remarks=remarks,
            )
            return je
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def reject_entry(self, entry_id: int, reason: str) -> JournalEntry:
        """Reject a journal entry.

        Args:
            entry_id: The journal entry ID.
            reason: Rejection reason.

        Returns:
            The rejected JournalEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If rejection fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        je = self.get_entry(entry_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.reject_document(
                doctype="journal_entry",
                document_id=entry_id,
                user_id=self.principal.id if self.principal else None,
                reason=reason,
            )
            return je
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def post_entry(self, entry_id: int, remarks: Optional[str] = None) -> JournalEntry:
        """Post an approved journal entry to the GL.

        Args:
            entry_id: The journal entry ID.
            remarks: Posting remarks.

        Returns:
            The posted JournalEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If posting fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        je = self.get_entry(entry_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.post_document(
                doctype="journal_entry",
                document_id=entry_id,
                user_id=self.principal.id if self.principal else None,
                remarks=remarks,
            )
            # Update JE docstatus to posted
            je.docstatus = 1
            activity_logger = ActivityLogger(self.db)
            activity_logger.log(
                action="finance.journal_entry.post",
                user_id=self.principal.id if self.principal else None,
                user_email=getattr(self.principal, "email", None),
                entity_type="journal_entry",
                entity_id=str(je.id),
                summary=f"Posted journal entry {je.id}",
                metadata={"remarks": remarks},
            )
            return je
        except ApprovalError as e:
            raise ValidationError(str(e)) from e
