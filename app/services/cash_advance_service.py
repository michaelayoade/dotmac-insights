"""Service for cash advance lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, Type, List

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session, selectinload

from app.models.expense_management import CashAdvance, CashAdvanceStatus
from app.services.errors import ValidationError, NotFoundError
from app.services.types import PaginatedResult, PaginationParams
from app.services.approval_engine import (
    ApprovalEngine,
    WorkflowNotFoundError,
    ApprovalNotFoundError,
    UnauthorizedApprovalError,
    InvalidStateError,
)
from app.services.number_generator import NumberGenerator, FormatNotFoundError
from app.services.expense_posting_service import ExpensePostingService
from app.services.expenses.types import CashAdvanceFilters

if TYPE_CHECKING:
    from app.models.books_settings import DocumentType as BooksDocumentTypeType

BooksDocumentType: Optional[Type["BooksDocumentTypeType"]]
try:
    from app.models.books_settings import DocumentType as BooksDocumentType
except Exception:
    BooksDocumentType = None


class CashAdvanceService:
    """Handles cash advance creation and state transitions."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_advances(
        self,
        filters: Optional[CashAdvanceFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[CashAdvance]:
        """List cash advances with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing advances and total count.
        """
        filters = filters or CashAdvanceFilters()
        pagination = pagination or PaginationParams()

        query = self.db.query(CashAdvance)

        # Search
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                or_(
                    CashAdvance.purpose.ilike(search),
                    CashAdvance.advance_number.ilike(search),
                    CashAdvance.destination.ilike(search),
                )
            )

        # Filters
        if filters.status:
            # Convert string status to enum if needed
            if isinstance(filters.status, str):
                try:
                    status_enum = CashAdvanceStatus(filters.status)
                    query = query.filter(CashAdvance.status == status_enum)
                except ValueError:
                    pass
            else:
                query = query.filter(CashAdvance.status == filters.status)
        if filters.employee_id:
            query = query.filter(CashAdvance.employee_id == filters.employee_id)
        if filters.from_date:
            query = query.filter(CashAdvance.request_date >= filters.from_date)
        if filters.to_date:
            query = query.filter(CashAdvance.request_date <= filters.to_date)
        if filters.has_balance is not None:
            if filters.has_balance:
                query = query.filter(CashAdvance.outstanding_amount > 0)
            else:
                query = query.filter(CashAdvance.outstanding_amount <= 0)

        # Count total
        total = query.count()

        # Sorting
        sort_col = getattr(CashAdvance, filters.sort_by, CashAdvance.request_date)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(
            items=query.all(),
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_advance(self, advance_id: int) -> CashAdvance:
        """Get a single cash advance by ID.

        Args:
            advance_id: The cash advance ID.

        Returns:
            The CashAdvance object.

        Raises:
            NotFoundError: If advance not found.
        """
        advance = (
            self.db.query(CashAdvance)
            .filter(CashAdvance.id == advance_id)
            .first()
        )
        if not advance:
            raise NotFoundError(f"Cash advance {advance_id} not found")
        return advance

    def update_advance(self, advance_id: int, payload) -> CashAdvance:
        """Update a draft cash advance.

        Only draft advances can be updated.

        Args:
            advance_id: The cash advance ID.
            payload: Update data.

        Returns:
            The updated CashAdvance.

        Raises:
            NotFoundError: If advance not found.
            ValidationError: If advance is not in draft status.
        """
        advance = self.get_advance(advance_id)

        if advance.status != CashAdvanceStatus.DRAFT:
            raise ValidationError("Only draft advances can be updated")

        # Update fields if provided
        if hasattr(payload, 'purpose') and payload.purpose is not None:
            advance.purpose = payload.purpose
        if hasattr(payload, 'request_date') and payload.request_date is not None:
            advance.request_date = payload.request_date
        if hasattr(payload, 'required_by_date') and payload.required_by_date is not None:
            advance.required_by_date = payload.required_by_date
        if hasattr(payload, 'requested_amount') and payload.requested_amount is not None:
            advance.requested_amount = payload.requested_amount
            advance.approved_amount = payload.requested_amount
            advance.base_requested_amount = payload.requested_amount * (advance.conversion_rate or Decimal("1"))
        if hasattr(payload, 'project_id'):
            advance.project_id = payload.project_id
        if hasattr(payload, 'destination') and payload.destination is not None:
            advance.destination = payload.destination
        if hasattr(payload, 'trip_start_date'):
            advance.trip_start_date = payload.trip_start_date
        if hasattr(payload, 'trip_end_date'):
            advance.trip_end_date = payload.trip_end_date

        advance.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return advance

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_advance(self, payload) -> CashAdvance:
        advance = CashAdvance(
            employee_id=payload.employee_id,
            purpose=payload.purpose,
            request_date=payload.request_date,
            required_by_date=payload.required_by_date,
            project_id=payload.project_id,
            trip_start_date=payload.trip_start_date,
            trip_end_date=payload.trip_end_date,
            destination=payload.destination,
            requested_amount=payload.requested_amount,
            approved_amount=payload.requested_amount,
            currency=payload.currency,
            base_currency=payload.base_currency,
            conversion_rate=payload.conversion_rate,
            base_requested_amount=payload.requested_amount * payload.conversion_rate,
            company=payload.company,
        )
        self.db.add(advance)
        self.db.flush()
        return advance

    def submit(self, advance: CashAdvance, user_id: int, company_code: Optional[str]) -> CashAdvance:
        if advance.status not in {CashAdvanceStatus.DRAFT, CashAdvanceStatus.RECALLED if hasattr(CashAdvanceStatus, "RECALLED") else CashAdvanceStatus.DRAFT}:
            raise ValidationError("Only draft advances can be submitted")

        advance.status = CashAdvanceStatus.PENDING_APPROVAL
        advance.docstatus = 1
        advance.submitted_at = datetime.now(timezone.utc)
        advance.advance_number = advance.advance_number or self._generate_number(advance, company_code)

        engine = ApprovalEngine(self.db)
        try:
            approval = engine.submit_document(
                doctype="cash_advance",
                document_id=advance.id,
                user_id=user_id,
                amount=advance.requested_amount,
                document_name=advance.advance_number or advance.purpose,
            )
        except WorkflowNotFoundError:
            # Auto-approve when no workflow is configured
            advance.status = CashAdvanceStatus.APPROVED
            advance.approved_at = datetime.now(timezone.utc)
            advance.approved_by_id = user_id
            approval = None

        self._sync_status_from_approval(advance, approval)
        return advance

    def approve(self, advance: CashAdvance, user_id: int) -> CashAdvance:
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.approve_document("cash_advance", advance.id, user_id=user_id)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise ValidationError(str(exc)) from exc

        self._sync_status_from_approval(advance, approval)
        return advance

    def reject(self, advance: CashAdvance, user_id: int, reason: str) -> CashAdvance:
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.reject_document("cash_advance", advance.id, user_id=user_id, reason=reason)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise ValidationError(str(exc)) from exc

        advance.rejection_reason = reason
        self._sync_status_from_approval(advance, approval)
        return advance

    def disburse(self, advance: CashAdvance, amount: Decimal, mode_of_payment: Optional[str], payment_reference: Optional[str], bank_account_id: Optional[int], user_id: int) -> CashAdvance:
        if advance.status not in {CashAdvanceStatus.APPROVED, CashAdvanceStatus.PENDING_APPROVAL}:
            raise ValidationError("Advance must be approved before disbursement")

        advance.disbursed_amount += amount
        advance.disbursed_at = datetime.now(timezone.utc)
        advance.mode_of_payment = mode_of_payment
        advance.payment_reference = payment_reference
        advance.bank_account_id = bank_account_id
        advance.disbursed_by_id = user_id

        advance.outstanding_amount = (advance.disbursed_amount or Decimal("0")) - (advance.settled_amount or Decimal("0")) - (advance.refund_amount or Decimal("0"))
        advance.status = CashAdvanceStatus.DISBURSED

        posting_service = ExpensePostingService(self.db)
        posting_service.post_cash_advance_disbursement(advance, amount=amount, user_id=user_id)
        return advance

    def settle(self, advance: CashAdvance, amount: Decimal, refund_amount: Decimal) -> CashAdvance:
        if advance.status not in {CashAdvanceStatus.DISBURSED, CashAdvanceStatus.PARTIALLY_SETTLED, CashAdvanceStatus.APPROVED}:
            raise ValidationError("Advance must be disbursed before settlement")

        advance.settled_amount += amount
        advance.refund_amount = (advance.refund_amount or Decimal("0")) + refund_amount
        advance.outstanding_amount = (advance.disbursed_amount or Decimal("0")) - advance.settled_amount - advance.refund_amount

        if advance.outstanding_amount <= 0:
            advance.status = CashAdvanceStatus.FULLY_SETTLED
        else:
            advance.status = CashAdvanceStatus.PARTIALLY_SETTLED

        if refund_amount and refund_amount > 0:
            posting_service = ExpensePostingService(self.db)
            posting_service.post_cash_advance_refund(advance, refund_amount=refund_amount, user_id=advance.disbursed_by_id or 0)

        return advance

    def _generate_number(self, advance: CashAdvance, company_code: Optional[str]) -> str:
        if BooksDocumentType is None:
            return f"ADV-{advance.request_date:%Y%m%d}-{advance.id}"

        document_type = getattr(BooksDocumentType, "CASH_ADVANCE", None)
        if document_type is None:
            return f"ADV-{advance.request_date:%Y%m%d}-{advance.id}"

        generator = NumberGenerator(self.db)
        try:
            return generator.get_next_number(
                document_type,
                company=advance.company,
                posting_date=advance.request_date,
                company_code=company_code,
            )
        except FormatNotFoundError:
            return f"ADV-{advance.request_date:%Y%m%d}-{advance.id}"

    def _sync_status_from_approval(self, advance: CashAdvance, approval) -> None:
        from app.models.accounting_ext import ApprovalStatus

        if approval is None:
            return
        if approval.status == ApprovalStatus.APPROVED:
            advance.status = CashAdvanceStatus.APPROVED
            advance.approved_at = approval.approved_at
            advance.approved_by_id = approval.approved_by_id
        elif approval.status == ApprovalStatus.PENDING:
            advance.status = CashAdvanceStatus.PENDING_APPROVAL
        elif approval.status == ApprovalStatus.REJECTED:
            advance.status = CashAdvanceStatus.REJECTED
