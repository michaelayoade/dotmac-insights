"""Service for cash advance lifecycle."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, Type

from sqlalchemy.orm import Session

from app.models.expense_management import CashAdvance, CashAdvanceStatus
from app.services.errors import ValidationError
from app.services.approval_engine import (
    ApprovalEngine,
    WorkflowNotFoundError,
    ApprovalNotFoundError,
    UnauthorizedApprovalError,
    InvalidStateError,
)
from app.services.number_generator import NumberGenerator, FormatNotFoundError
from app.services.expense_posting_service import ExpensePostingService

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
        advance.submitted_at = datetime.utcnow()
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
            advance.approved_at = datetime.utcnow()
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
        advance.disbursed_at = datetime.utcnow()
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
