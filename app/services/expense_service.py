"""Expense claim service for creation and submission."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.expense_management import (
    ExpenseClaim,
    ExpenseClaimLine,
    ExpenseClaimStatus,
    FundingMethod,
)
from app.models.employee import Employee
from app.services.expense_policy_service import ExpensePolicyService, PolicyViolation
from app.services.number_generator import NumberGenerator, FormatNotFoundError
from app.services.approval_engine import (
    ApprovalEngine,
    WorkflowNotFoundError,
    ApprovalNotFoundError,
    UnauthorizedApprovalError,
    InvalidStateError,
)
from app.models.accounting_ext import ApprovalStatus

try:
    from app.models.books_settings import DocumentType
except Exception:  # pragma: no cover - defensive for environments without books settings
    DocumentType = None


class ExpenseService:
    """Handles expense claim lifecycle and totals calculation."""

    def __init__(self, db: Session):
        self.db = db
        self.policy_service = ExpensePolicyService(db)

    def create_claim(self, payload) -> ExpenseClaim:
        """Create a draft claim with lines and calculated totals."""
        if not payload.lines:
            raise HTTPException(status_code=400, detail="At least one line is required")

        employee = self._get_employee(payload.employee_id)
        claim = ExpenseClaim(
            title=payload.title,
            description=payload.description,
            employee_id=payload.employee_id,
            department_id=employee.department_id if employee else None,
            claim_date=payload.claim_date,
            currency=payload.currency,
            base_currency=payload.base_currency,
            conversion_rate=payload.conversion_rate,
            project_id=payload.project_id,
            cost_center=payload.cost_center,
            cash_advance_id=payload.cash_advance_id,
            company=payload.company,
        )
        self.db.add(claim)
        self.db.flush()  # assign ID for line FK

        totals = {
            "claimed": Decimal("0"),
            "sanctioned": Decimal("0"),
            "taxes": Decimal("0"),
            "out_of_pocket": Decimal("0"),
            "corporate_card": Decimal("0"),
            "cash_advance": Decimal("0"),
            "per_diem": Decimal("0"),
        }

        for idx, line in enumerate(payload.lines, start=1):
            policy = self.policy_service.get_applicable_policy(
                category_id=line.category_id,
                employee=employee,
                as_of=payload.claim_date,
                company=payload.company,
            )
            try:
                self.policy_service.ensure_funding_allowed(policy, line.funding_method)
                self.policy_service.ensure_receipt_compliance(
                    policy,
                    line.claimed_amount,
                    line.has_receipt,
                    line.receipt_missing_reason,
                )
                self.policy_service.ensure_amount_within_limits(policy, line.claimed_amount)
            except PolicyViolation as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            base_amount = (line.claimed_amount or Decimal("0")) * (line.conversion_rate or Decimal("1"))

            claim_line = ExpenseClaimLine(
                expense_claim_id=claim.id,
                category_id=line.category_id,
                expense_date=line.expense_date,
                description=line.description,
                merchant_name=line.merchant_name,
                invoice_number=line.invoice_number,
                claimed_amount=line.claimed_amount,
                sanctioned_amount=line.claimed_amount,
                currency=line.currency,
                tax_code_id=line.tax_code_id,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                is_tax_inclusive=line.is_tax_inclusive,
                is_tax_reclaimable=line.is_tax_reclaimable,
                withholding_tax_rate=line.withholding_tax_rate,
                withholding_tax_amount=line.withholding_tax_amount,
                conversion_rate=line.conversion_rate,
                base_claimed_amount=base_amount,
                base_sanctioned_amount=base_amount,
                rate_source=line.rate_source,
                rate_date=line.rate_date,
                funding_method=line.funding_method,
                cost_center=line.cost_center or claim.cost_center,
                project_id=line.project_id or claim.project_id,
                has_receipt=line.has_receipt,
                receipt_missing_reason=line.receipt_missing_reason,
                idx=idx,
            )

            totals["claimed"] += line.claimed_amount
            totals["sanctioned"] += line.claimed_amount
            totals["taxes"] += line.tax_amount
            totals[self._funding_bucket(line.funding_method)] += line.claimed_amount
            self.db.add(claim_line)

        claim.total_claimed_amount = totals["claimed"]
        claim.total_sanctioned_amount = totals["sanctioned"]
        claim.total_taxes = totals["taxes"]
        claim.base_total_claimed = totals["claimed"] * payload.conversion_rate
        claim.base_total_sanctioned = totals["sanctioned"] * payload.conversion_rate
        claim.out_of_pocket_amount = totals["out_of_pocket"]
        claim.corporate_card_amount = totals["corporate_card"]
        claim.cash_advance_amount = totals["cash_advance"]
        claim.per_diem_amount = totals["per_diem"]

        return claim

    def submit_claim(
        self,
        claim: ExpenseClaim,
        user_id: int,
        company_code: Optional[str] = None,
    ) -> ExpenseClaim:
        """Submit claim for approval and assign claim number."""
        if claim.status not in {ExpenseClaimStatus.DRAFT, ExpenseClaimStatus.RECALLED, ExpenseClaimStatus.RETURNED}:
            raise HTTPException(status_code=400, detail="Only draft/returned claims can be submitted")

        claim.status = ExpenseClaimStatus.PENDING_APPROVAL
        claim.docstatus = 1
        claim.submitted_at = datetime.utcnow()
        claim.claim_number = claim.claim_number or self._generate_claim_number(claim, company_code)

        # Approval workflow integration
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.submit_document(
                doctype="expense_claim",
                document_id=claim.id,
                user_id=user_id,
                amount=claim.total_claimed_amount,
                document_name=claim.claim_number or claim.title,
            )
        except WorkflowNotFoundError as exc:
            # If no workflow, auto-approve and continue
            claim.status = ExpenseClaimStatus.APPROVED
            claim.approval_status = "approved"
            claim.approved_at = datetime.utcnow()
            claim.approved_by_id = user_id
            approval = None

        self._sync_status_from_approval(claim, approval)
        return claim

    def approve_claim(self, claim: ExpenseClaim, user_id: int) -> ExpenseClaim:
        """Approve a claim via approval engine and sync status."""
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.approve_document("expense_claim", claim.id, user_id=user_id)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        self._sync_status_from_approval(claim, approval)
        return claim

    def reject_claim(self, claim: ExpenseClaim, user_id: int, reason: str) -> ExpenseClaim:
        """Reject a claim and sync status."""
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.reject_document("expense_claim", claim.id, user_id=user_id, reason=reason)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        self._sync_status_from_approval(claim, approval)
        claim.rejection_reason = reason
        return claim

    def return_claim(self, claim: ExpenseClaim, reason: str) -> ExpenseClaim:
        """Return a claim to drafter for edits."""
        if claim.status not in {ExpenseClaimStatus.PENDING_APPROVAL, ExpenseClaimStatus.REJECTED, ExpenseClaimStatus.RETURNED}:
            raise HTTPException(status_code=400, detail="Only pending/rejected claims can be returned")

        claim.status = ExpenseClaimStatus.RETURNED
        claim.approval_status = "returned"
        claim.return_reason = reason
        claim.docstatus = 0
        return claim

    def recall_claim(self, claim: ExpenseClaim, user_id: int) -> ExpenseClaim:
        """Recall a pending claim before approval decision."""
        if claim.status not in {ExpenseClaimStatus.PENDING_APPROVAL, ExpenseClaimStatus.RETURNED}:
            raise HTTPException(status_code=400, detail="Only pending/returned claims can be recalled")

        claim.status = ExpenseClaimStatus.RECALLED
        claim.approval_status = "recalled"
        claim.docstatus = 0
        claim.return_reason = None
        return claim

    def _generate_claim_number(self, claim: ExpenseClaim, company_code: Optional[str]) -> str:
        """Generate a claim number using number formats if available."""
        if DocumentType is None:
            return f"EXP-{claim.claim_date:%Y%m%d}-{claim.id}"

        document_type = getattr(DocumentType, "EXPENSE_CLAIM", None)
        if document_type is None:
            return f"EXP-{claim.claim_date:%Y%m%d}-{claim.id}"

        generator = NumberGenerator(self.db)
        try:
            return generator.get_next_number(
                document_type,
                company=claim.company,
                posting_date=claim.claim_date,
                company_code=company_code,
            )
        except FormatNotFoundError:
            return f"EXP-{claim.claim_date:%Y%m%d}-{claim.id}"

    def _get_employee(self, employee_id: int) -> Optional[Employee]:
        return self.db.query(Employee).filter(Employee.id == employee_id).first()

    def _funding_bucket(self, funding_method: FundingMethod) -> str:
        if funding_method == FundingMethod.CORPORATE_CARD:
            return "corporate_card"
        if funding_method == FundingMethod.CASH_ADVANCE:
            return "cash_advance"
        if funding_method == FundingMethod.PER_DIEM:
            return "per_diem"
        return "out_of_pocket"

    def _sync_status_from_approval(self, claim: ExpenseClaim, approval) -> None:
        """Align claim status/metadata with approval state."""
        if approval is None:
            return
        if approval.status == ApprovalStatus.APPROVED:
            claim.status = ExpenseClaimStatus.APPROVED
            claim.approval_status = "approved"
            claim.approved_by_id = approval.approved_by_id
            claim.approved_at = approval.approved_at
        elif approval.status == ApprovalStatus.PENDING:
            claim.status = ExpenseClaimStatus.PENDING_APPROVAL
            claim.approval_status = "pending"
        elif approval.status == ApprovalStatus.REJECTED:
            claim.status = ExpenseClaimStatus.REJECTED
            claim.approval_status = "rejected"
