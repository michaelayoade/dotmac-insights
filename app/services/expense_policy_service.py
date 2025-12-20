"""Expense policy resolution and validation service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.expense_management import ExpensePolicy, FundingMethod


class PolicyViolation(Exception):
    """Raised when an expense violates policy rules."""


class ExpensePolicyService:
    """Resolves and validates expense policies for a claim or line."""

    def __init__(self, db: Session):
        self.db = db

    def get_applicable_policy(
        self,
        category_id: int,
        employee: Optional[Employee],
        as_of: Optional[date],
        company: Optional[str],
    ) -> Optional[ExpensePolicy]:
        """Return the highest priority active policy for a category/employee."""
        today = as_of or date.today()
        query = (
            self.db.query(ExpensePolicy)
            .filter(
                ExpensePolicy.is_active.is_(True),
                or_(ExpensePolicy.effective_from.is_(None), ExpensePolicy.effective_from <= today),
                or_(ExpensePolicy.effective_to.is_(None), ExpensePolicy.effective_to >= today),
                or_(ExpensePolicy.company.is_(None), ExpensePolicy.company == company),
                or_(ExpensePolicy.category_id.is_(None), ExpensePolicy.category_id == category_id),
            )
            .order_by(ExpensePolicy.priority.desc(), ExpensePolicy.category_id.desc())
        )

        if employee:
            query = query.filter(
                or_(ExpensePolicy.department_id.is_(None), ExpensePolicy.department_id == employee.department_id),
                or_(ExpensePolicy.designation_id.is_(None), ExpensePolicy.designation_id == employee.designation_id),
                or_(ExpensePolicy.employment_type.is_(None), ExpensePolicy.employment_type == employee.employment_type),
                # Note: Employee model doesn't have grade_level, always match on None
                ExpensePolicy.grade_level.is_(None),
            )

        return query.first()

    def ensure_funding_allowed(self, policy: Optional[ExpensePolicy], funding_method: FundingMethod) -> None:
        """Check if funding method is allowed."""
        if not policy:
            return

        if funding_method == FundingMethod.OUT_OF_POCKET and not policy.allow_out_of_pocket:
            raise PolicyViolation("Out-of-pocket expenses are not allowed by policy")
        if funding_method == FundingMethod.CASH_ADVANCE and not policy.allow_cash_advance:
            raise PolicyViolation("Cash advance funding is not allowed by policy")
        if funding_method == FundingMethod.CORPORATE_CARD and not policy.allow_corporate_card:
            raise PolicyViolation("Corporate card funding is not allowed by policy")
        if funding_method == FundingMethod.PER_DIEM and not policy.allow_per_diem:
            raise PolicyViolation("Per-diem funding is not allowed by policy")

    def ensure_receipt_compliance(
        self,
        policy: Optional[ExpensePolicy],
        amount: Decimal,
        has_receipt: bool,
        receipt_missing_reason: Optional[str],
    ) -> None:
        """Validate receipt presence vs. policy thresholds."""
        if not policy:
            return

        if policy.receipt_required and not has_receipt:
            if policy.receipt_threshold is None or amount >= policy.receipt_threshold:
                raise PolicyViolation("Receipt is required for this expense")
            if not receipt_missing_reason:
                raise PolicyViolation("Receipt missing reason is required when receipt is absent")

    def ensure_amount_within_limits(self, policy: Optional[ExpensePolicy], amount: Decimal) -> None:
        """Validate monetary limits."""
        if not policy:
            return

        if policy.max_single_expense and amount > policy.max_single_expense:
            raise PolicyViolation("Amount exceeds single expense limit")
