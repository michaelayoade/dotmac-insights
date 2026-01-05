"""Expense claim service for creation and submission."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, Type, List

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session, selectinload

from dataclasses import dataclass, field

from app.models.expense_management import (
    ExpenseClaim,
    ExpenseClaimLine,
    ExpenseClaimStatus,
    ExpenseCategory,
    FundingMethod,
)
from app.models.employee import Employee
from app.services.expense_policy_service import ExpensePolicyService, PolicyViolation
from app.services.activity_logger import ActivityLogger
from app.services.number_generator import NumberGenerator, FormatNotFoundError
from app.services.errors import ValidationError, NotFoundError
from app.services.types import PaginatedResult, PaginationParams
from app.services.approval_engine import (
    ApprovalEngine,
    WorkflowNotFoundError,
    ApprovalNotFoundError,
    UnauthorizedApprovalError,
    InvalidStateError,
)
from app.models.accounting_ext import ApprovalStatus
from app.services.expenses.types import ExpenseClaimFilters

if TYPE_CHECKING:
    from app.models.books_settings import DocumentType as BooksDocumentTypeType

BooksDocumentType: Optional[Type["BooksDocumentTypeType"]]
try:
    from app.models.books_settings import DocumentType as BooksDocumentType
except Exception:  # pragma: no cover - defensive for environments without books settings
    BooksDocumentType = None


@dataclass
class ExpenseFormOptions:
    """Options for expense claim form dropdowns."""

    employees: List[Employee] = field(default_factory=list)
    categories: List["ExpenseCategory"] = field(default_factory=list)


class ExpenseService:
    """Handles expense claim lifecycle and totals calculation."""

    def __init__(self, db: Session):
        self.db = db
        self.policy_service = ExpensePolicyService(db)

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_claims(
        self,
        filters: Optional[ExpenseClaimFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ExpenseClaim]:
        """List expense claims with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing claims and total count.
        """
        filters = filters or ExpenseClaimFilters()
        pagination = pagination or PaginationParams()

        query = self.db.query(ExpenseClaim)

        # Search
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                or_(
                    ExpenseClaim.title.ilike(search),
                    ExpenseClaim.claim_number.ilike(search),
                    ExpenseClaim.description.ilike(search),
                )
            )

        # Filters
        if filters.status:
            # Convert string status to enum if needed
            if isinstance(filters.status, str):
                try:
                    status_enum = ExpenseClaimStatus(filters.status)
                    query = query.filter(ExpenseClaim.status == status_enum)
                except ValueError:
                    pass
            else:
                query = query.filter(ExpenseClaim.status == filters.status)
        if filters.employee_id:
            query = query.filter(ExpenseClaim.employee_id == filters.employee_id)
        if filters.department_id:
            query = query.filter(ExpenseClaim.department_id == filters.department_id)
        if filters.project_id:
            query = query.filter(ExpenseClaim.project_id == filters.project_id)
        if filters.from_date:
            query = query.filter(ExpenseClaim.claim_date >= filters.from_date)
        if filters.to_date:
            query = query.filter(ExpenseClaim.claim_date <= filters.to_date)
        if filters.company:
            query = query.filter(ExpenseClaim.company == filters.company)

        # Count total
        total = query.count()

        # Sorting
        sort_col = getattr(ExpenseClaim, filters.sort_by, ExpenseClaim.claim_date)
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

    def get_claim(self, claim_id: int, include_lines: bool = True) -> ExpenseClaim:
        """Get a single expense claim by ID.

        Args:
            claim_id: The expense claim ID.
            include_lines: Whether to eagerly load line items.

        Returns:
            The ExpenseClaim object.

        Raises:
            NotFoundError: If claim not found.
        """
        query = self.db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id)

        if include_lines:
            query = query.options(selectinload(ExpenseClaim.lines))

        claim = query.first()
        if not claim:
            raise NotFoundError(f"Expense claim {claim_id} not found")
        return claim

    def get_form_options(self) -> "ExpenseFormOptions":
        """Get dropdown options for expense claim forms.

        Returns employees and categories for form dropdowns in a single call.
        This avoids duplicate queries across form routes.

        Returns:
            ExpenseFormOptions with employees and categories.
        """
        employees = (
            self.db.query(Employee)
            .filter(Employee.status == "Active")
            .order_by(Employee.name)
            .all()
        )

        categories = (
            self.db.query(ExpenseCategory)
            .filter(ExpenseCategory.is_active == True)
            .order_by(ExpenseCategory.name)
            .all()
        )

        return ExpenseFormOptions(
            employees=employees,
            categories=categories,
        )


    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_draft_claim(
        self,
        employee_id: int,
        title: str,
        claim_date,
        description: Optional[str] = None,
        project_id: Optional[int] = None,
        cost_center: Optional[str] = None,
        company: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> ExpenseClaim:
        """Create a minimal draft claim (no lines required).

        Use this for web forms that create a claim shell first,
        then add lines later.

        Args:
            employee_id: The employee making the claim.
            title: Claim title.
            claim_date: Date of the claim.
            description: Optional description.
            project_id: Optional project reference.
            cost_center: Optional cost center.
            company: Optional company scope.
            created_by_id: ID of user creating the claim.

        Returns:
            The created ExpenseClaim in draft status.
        """
        employee = self._get_employee(employee_id)

        claim = ExpenseClaim(
            title=title,
            description=description,
            employee_id=employee_id,
            department_id=employee.department_id if employee else None,
            claim_date=claim_date,
            project_id=project_id,
            cost_center=cost_center,
            company=company,
            status=ExpenseClaimStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self.db.add(claim)
        self.db.flush()

        return claim

    def create_claim(self, payload) -> ExpenseClaim:
        """Create a draft claim with lines and calculated totals."""
        if not payload.lines:
            raise ValidationError("At least one line is required")

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
                raise ValidationError(str(exc)) from exc

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

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.create",
            user_id=payload.created_by_id if hasattr(payload, "created_by_id") else None,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Created expense claim {claim.claim_number or claim.id}",
            metadata={"employee_id": claim.employee_id, "total_claimed": float(claim.total_claimed_amount)},
        )
        return claim

    def submit_claim(
        self,
        claim: ExpenseClaim,
        user_id: int,
        company_code: Optional[str] = None,
    ) -> ExpenseClaim:
        """Submit claim for approval and assign claim number."""
        if claim.status not in {ExpenseClaimStatus.DRAFT, ExpenseClaimStatus.RECALLED, ExpenseClaimStatus.RETURNED}:
            raise ValidationError("Only draft/returned claims can be submitted")

        claim.status = ExpenseClaimStatus.PENDING_APPROVAL
        claim.docstatus = 1
        claim.submitted_at = datetime.now(timezone.utc)
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
            claim.approved_at = datetime.now(timezone.utc)
            claim.approved_by_id = user_id
            approval = None

        self._sync_status_from_approval(claim, approval)
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.submit",
            user_id=user_id,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Submitted expense claim {claim.claim_number or claim.id}",
            metadata={"total_claimed": float(claim.total_claimed_amount)},
        )
        return claim

    def approve_claim(self, claim: ExpenseClaim, user_id: int) -> ExpenseClaim:
        """Approve a claim via approval engine and sync status."""
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.approve_document("expense_claim", claim.id, user_id=user_id)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise ValidationError(str(exc)) from exc

        self._sync_status_from_approval(claim, approval)
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.approve",
            user_id=user_id,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Approved expense claim {claim.claim_number or claim.id}",
        )
        return claim

    def reject_claim(self, claim: ExpenseClaim, user_id: int, reason: str) -> ExpenseClaim:
        """Reject a claim and sync status."""
        engine = ApprovalEngine(self.db)
        try:
            approval = engine.reject_document("expense_claim", claim.id, user_id=user_id, reason=reason)
        except (ApprovalNotFoundError, UnauthorizedApprovalError, InvalidStateError) as exc:
            raise ValidationError(str(exc)) from exc

        self._sync_status_from_approval(claim, approval)
        claim.rejection_reason = reason
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.reject",
            user_id=user_id,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Rejected expense claim {claim.claim_number or claim.id}",
            metadata={"reason": reason},
        )
        return claim

    def return_claim(self, claim: ExpenseClaim, reason: str) -> ExpenseClaim:
        """Return a claim to drafter for edits."""
        if claim.status not in {ExpenseClaimStatus.PENDING_APPROVAL, ExpenseClaimStatus.REJECTED, ExpenseClaimStatus.RETURNED}:
            raise ValidationError("Only pending/rejected claims can be returned")

        claim.status = ExpenseClaimStatus.RETURNED
        claim.approval_status = "returned"
        claim.return_reason = reason
        claim.docstatus = 0
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.return",
            user_id=claim.updated_by_id,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Returned expense claim {claim.claim_number or claim.id}",
            metadata={"reason": reason},
        )
        return claim

    def recall_claim(self, claim: ExpenseClaim, user_id: int) -> ExpenseClaim:
        """Recall a pending claim before approval decision."""
        if claim.status not in {ExpenseClaimStatus.PENDING_APPROVAL, ExpenseClaimStatus.RETURNED}:
            raise ValidationError("Only pending/returned claims can be recalled")

        claim.status = ExpenseClaimStatus.RECALLED
        claim.approval_status = "recalled"
        claim.docstatus = 0
        claim.return_reason = None
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.expense_claim.recall",
            user_id=user_id,
            entity_type="expense_claim",
            entity_id=str(claim.id),
            summary=f"Recalled expense claim {claim.claim_number or claim.id}",
        )
        return claim

    def _generate_claim_number(self, claim: ExpenseClaim, company_code: Optional[str]) -> str:
        """Generate a claim number using number formats if available."""
        if BooksDocumentType is None:
            return f"EXP-{claim.claim_date:%Y%m%d}-{claim.id}"

        document_type = getattr(BooksDocumentType, "EXPENSE_CLAIM", None)
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
