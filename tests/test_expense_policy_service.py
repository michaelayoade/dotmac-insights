import pytest
from decimal import Decimal

from app.services.expense_policy_service import ExpensePolicyService, PolicyViolation
from app.models.expense_management import ExpensePolicy, FundingMethod


class DummySession:
    """Minimal session stub to satisfy service signature."""

    def query(self, *_args, **_kwargs):
        raise NotImplementedError("Query not implemented for this unit test")


def test_receipt_required_raises_when_missing():
    service = ExpensePolicyService(DummySession())
    policy = ExpensePolicy(
        policy_name="Test",
        receipt_required=True,
        receipt_threshold=None,
    )

    with pytest.raises(PolicyViolation):
        service.ensure_receipt_compliance(policy, Decimal("100"), has_receipt=False, receipt_missing_reason=None)


def test_funding_not_allowed_raises():
    service = ExpensePolicyService(DummySession())
    policy = ExpensePolicy(
        policy_name="Test",
        allow_cash_advance=False,
    )

    with pytest.raises(PolicyViolation):
        service.ensure_funding_allowed(policy, FundingMethod.CASH_ADVANCE)


def test_amount_limit_raises_when_exceeded():
    service = ExpensePolicyService(DummySession())
    policy = ExpensePolicy(
        policy_name="Test",
        max_single_expense=Decimal("50"),
    )

    with pytest.raises(PolicyViolation):
        service.ensure_amount_within_limits(policy, Decimal("75"))
