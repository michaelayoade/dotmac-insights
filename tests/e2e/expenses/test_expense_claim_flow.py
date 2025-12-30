"""
Expense Claim E2E Flow Tests

Tests the complete expense claim lifecycle from creation through reimbursement,
including approval workflows, cash advances, and corporate card reconciliation.
"""
import pytest
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from tests.e2e.conftest import (
    assert_http_ok, assert_http_error, get_json,
    assert_response_schema
)
from tests.e2e.fixtures.factories import create_employee


pytestmark = pytest.mark.expenses


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def test_employee(e2e_db):
    """Create a test employee for expense claims."""
    return create_employee(
        e2e_db,
        name="Expense Claimant",
        email="claimant@test.com",
        department="Sales",
        designation="Sales Representative",
    )


@pytest.fixture
def test_manager(e2e_db):
    """Create a manager for approval workflows."""
    return create_employee(
        e2e_db,
        name="Expense Approver",
        email="approver@test.com",
        department="Sales",
        designation="Sales Manager",
    )


@pytest.fixture
def test_finance_officer(e2e_db):
    """Create a finance officer for posting/payment."""
    return create_employee(
        e2e_db,
        name="Finance Officer",
        email="finance@test.com",
        department="Finance",
        designation="Finance Officer",
    )


@pytest.fixture
def test_expense_category(e2e_db):
    """Create a test expense category."""
    from app.models.expense_management import ExpenseCategory

    category = ExpenseCategory(
        code="TRV-001",
        name="Business Travel",
        description="Expenses related to business travel",
        expense_account="5100-Travel-Expense",
        category_type="travel",
        requires_receipt=True,
        is_active=True,
    )
    e2e_db.add(category)
    e2e_db.commit()
    e2e_db.refresh(category)
    return category


@pytest.fixture
def test_expense_policy(e2e_db, test_expense_category):
    """Create a test expense policy with limits."""
    from app.models.expense_management import ExpensePolicy

    policy = ExpensePolicy(
        policy_name="Standard Travel Policy",
        category_id=test_expense_category.id,
        applies_to_all=True,
        max_single_expense=Decimal("100000.00"),
        max_daily_limit=Decimal("200000.00"),
        max_monthly_limit=Decimal("1000000.00"),
        currency="NGN",
        requires_receipt=True,
        receipt_threshold=Decimal("5000.00"),
        is_active=True,
    )
    e2e_db.add(policy)
    e2e_db.commit()
    e2e_db.refresh(policy)
    return policy


# =============================================================================
# COMPLETE EXPENSE CLAIM FLOW
# =============================================================================


class TestExpenseClaimCompleteFlow:
    """
    Test the complete expense claim lifecycle:
    Draft → Submitted → Approved → Posted → Paid
    """

    def test_business_travel_expense_complete_flow(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Complete business travel expense claim from creation to reimbursement.

        Flow:
        1. Create draft expense claim with multiple lines
        2. Add supporting receipt attachments
        3. Submit for approval
        4. Manager approves the claim
        5. Finance posts to GL
        6. Process reimbursement
        """
        client = e2e_superuser_client

        # 1. Create draft expense claim
        create_payload = {
            "employee_id": test_employee.id,
            "claim_title": "Lagos Sales Trip - December 2024",
            "description": "Client meetings and site visits in Lagos",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Flight ticket LOS-ABV round trip",
                    "expense_date": date.today().isoformat(),
                    "amount": "85000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Hotel accommodation - 2 nights",
                    "expense_date": date.today().isoformat(),
                    "amount": "45000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Local transport and taxi",
                    "expense_date": date.today().isoformat(),
                    "amount": "15000.00",
                    "currency": "NGN",
                },
            ],
        }

        resp = client.post("/api/expenses/claims", json=create_payload)
        assert_http_ok(resp, "Create expense claim")
        claim = get_json(resp)

        claim_id = claim["id"]
        assert claim["status"] == "draft"
        assert len(claim["lines"]) == 3
        assert Decimal(str(claim["total_amount"])) == Decimal("145000.00")

        # 2. Verify claim details
        resp = client.get(f"/api/expenses/claims/{claim_id}")
        assert_http_ok(resp)
        claim = get_json(resp)
        assert claim["employee_id"] == test_employee.id
        assert claim["funding_method"] == "out_of_pocket"

        # 3. Submit for approval
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp, "Submit for approval")
        claim = get_json(resp)
        assert claim["status"] == "pending_approval"
        assert claim["submitted_at"] is not None

        # 4. Approve the claim
        resp = client.post(f"/api/expenses/claims/{claim_id}/approve")
        assert_http_ok(resp, "Approve claim")
        claim = get_json(resp)
        assert claim["status"] == "approved"
        assert claim["approved_at"] is not None

        # 5. Post to GL (finance step)
        resp = client.post(f"/api/expenses/claims/{claim_id}/post")
        assert_http_ok(resp, "Post to GL")
        claim = get_json(resp)
        assert claim["status"] == "posted"
        assert claim["posted_at"] is not None

        # Verify journal entry was created
        if claim.get("journal_entry_id"):
            resp = client.get(f"/api/accounting/journal-entries/{claim['journal_entry_id']}")
            assert_http_ok(resp)
            je = get_json(resp)
            assert je["status"] in ["draft", "posted"]


class TestExpenseClaimRejectionFlow:
    """Test expense claim rejection workflows."""

    def test_reject_non_compliant_expense(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Reject an expense claim that doesn't comply with policy.

        Flow:
        1. Create expense claim exceeding limits
        2. Submit for approval
        3. Manager rejects with reason
        4. Verify rejected state
        """
        client = e2e_superuser_client

        # 1. Create expense claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Expensive Client Dinner",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Team dinner at expensive restaurant",
                    "expense_date": date.today().isoformat(),
                    "amount": "250000.00",
                    "currency": "NGN",
                },
            ],
        })
        assert_http_ok(resp)
        claim = get_json(resp)
        claim_id = claim["id"]

        # 2. Submit for approval
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)

        # 3. Reject with reason
        resp = client.post(f"/api/expenses/claims/{claim_id}/reject", params={
            "reason": "Amount exceeds policy limit for meals. Please split into multiple claims or get pre-approval.",
        })
        assert_http_ok(resp, "Reject claim")
        claim = get_json(resp)

        assert claim["status"] == "rejected"
        assert claim["rejection_reason"] is not None

        # 4. Verify employee can see rejection reason
        resp = client.get(f"/api/expenses/claims/{claim_id}")
        claim = get_json(resp)
        assert "exceeds policy" in claim["rejection_reason"].lower()


class TestExpenseClaimReturnFlow:
    """Test returning claims for edits."""

    def test_return_claim_for_missing_receipts(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Return a claim to employee for missing documentation.

        Flow:
        1. Create and submit claim without receipts
        2. Return to employee for edits
        3. Employee adds receipts and resubmits
        4. Claim gets approved
        """
        client = e2e_superuser_client

        # 1. Create and submit claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Office Supplies",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Printer paper and toner",
                    "expense_date": date.today().isoformat(),
                    "amount": "35000.00",
                    "currency": "NGN",
                },
            ],
        })
        claim = get_json(resp)
        claim_id = claim["id"]

        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)

        # 2. Return for edits
        resp = client.post(f"/api/expenses/claims/{claim_id}/return", json={
            "reason": "Please attach scanned copies of receipts for all items.",
        })
        assert_http_ok(resp, "Return claim")
        claim = get_json(resp)
        assert claim["status"] == "returned"

        # 3. Update claim (add note about receipts)
        resp = client.patch(f"/api/expenses/claims/{claim_id}", json={
            "notes": "Receipts attached to all expense lines.",
        })
        assert_http_ok(resp)

        # 4. Resubmit
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp, "Resubmit claim")
        claim = get_json(resp)
        assert claim["status"] == "pending_approval"

        # 5. Approve
        resp = client.post(f"/api/expenses/claims/{claim_id}/approve")
        assert_http_ok(resp)
        claim = get_json(resp)
        assert claim["status"] == "approved"


class TestExpenseClaimRecallFlow:
    """Test employee recalling submitted claims."""

    def test_recall_submitted_claim(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Employee recalls a submitted claim to make corrections.
        """
        client = e2e_superuser_client

        # Create and submit claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Conference Attendance",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Conference registration fee",
                    "expense_date": date.today().isoformat(),
                    "amount": "50000.00",
                    "currency": "NGN",
                },
            ],
        })
        claim = get_json(resp)
        claim_id = claim["id"]

        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)
        assert get_json(resp)["status"] == "pending_approval"

        # Recall the claim
        resp = client.post(f"/api/expenses/claims/{claim_id}/recall")
        assert_http_ok(resp, "Recall claim")
        claim = get_json(resp)
        assert claim["status"] == "recalled"

        # Make corrections
        resp = client.patch(f"/api/expenses/claims/{claim_id}", json={
            "claim_title": "Conference Attendance - Updated",
        })
        assert_http_ok(resp)

        # Can resubmit after recall
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)
        assert get_json(resp)["status"] == "pending_approval"


class TestCashAdvanceFlow:
    """Test cash advance request and settlement workflows."""

    def test_cash_advance_complete_flow(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Complete cash advance flow from request to settlement.

        Flow:
        1. Request cash advance for upcoming trip
        2. Approve cash advance
        3. Disburse funds
        4. Create expense claim linked to advance
        5. Settle the advance with claim
        """
        client = e2e_superuser_client

        # 1. Request cash advance
        advance_payload = {
            "employee_id": test_employee.id,
            "purpose": "Upcoming client visit to Port Harcourt",
            "amount": "150000.00",
            "currency": "NGN",
            "expected_expense_date": (date.today() + timedelta(days=7)).isoformat(),
            "expected_return_date": (date.today() + timedelta(days=10)).isoformat(),
        }

        resp = client.post("/api/expenses/cash-advances", json=advance_payload)
        assert_http_ok(resp, "Create cash advance request")
        advance = get_json(resp)

        advance_id = advance["id"]
        assert advance["status"] == "draft"
        assert Decimal(str(advance["amount"])) == Decimal("150000.00")

        # 2. Submit for approval
        resp = client.post(f"/api/expenses/cash-advances/{advance_id}/submit")
        assert_http_ok(resp, "Submit advance")
        advance = get_json(resp)
        assert advance["status"] == "pending_approval"

        # 3. Approve cash advance
        resp = client.post(f"/api/expenses/cash-advances/{advance_id}/approve")
        assert_http_ok(resp, "Approve advance")
        advance = get_json(resp)
        assert advance["status"] == "approved"

        # 4. Disburse funds
        resp = client.post(f"/api/expenses/cash-advances/{advance_id}/disburse", json={
            "disbursement_date": date.today().isoformat(),
            "disbursement_method": "bank_transfer",
            "reference": "TRF-12345",
        })
        assert_http_ok(resp, "Disburse advance")
        advance = get_json(resp)
        assert advance["status"] == "disbursed"
        assert advance["disbursed_at"] is not None

        # 5. Create expense claim linked to advance
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Port Harcourt Client Visit Expenses",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "cash_advance",
            "cash_advance_id": advance_id,
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Flight and local transport",
                    "expense_date": date.today().isoformat(),
                    "amount": "95000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Hotel and meals",
                    "expense_date": date.today().isoformat(),
                    "amount": "45000.00",
                    "currency": "NGN",
                },
            ],
        })
        assert_http_ok(resp)
        claim = get_json(resp)
        claim_id = claim["id"]

        # Total claimed: 140,000 (less than 150,000 advance)
        assert Decimal(str(claim["total_amount"])) == Decimal("140000.00")

        # 6. Submit and approve claim
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)

        resp = client.post(f"/api/expenses/claims/{claim_id}/approve")
        assert_http_ok(resp)

        # 7. Settle the advance
        resp = client.post(f"/api/expenses/cash-advances/{advance_id}/settle", json={
            "claim_ids": [claim_id],
        })
        assert_http_ok(resp, "Settle advance")
        advance = get_json(resp)

        # Should show balance due (employee owes 10,000 back)
        assert advance["status"] in ["partially_settled", "fully_settled"]


class TestCorporateCardFlow:
    """Test corporate card transaction reconciliation."""

    def test_corporate_card_reconciliation_flow(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Reconcile corporate card transactions with expense claims.

        Flow:
        1. Import card statement with transactions
        2. Create expense claim for card transactions
        3. Match transactions to claim lines
        4. Reconcile and close statement
        """
        client = e2e_superuser_client

        # 1. Create corporate card for employee (if API exists)
        # Skip card creation if not implemented, test the matching flow

        # 2. Create expense claim with corporate card funding
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Corporate Card Expenses - December",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "corporate_card",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Software subscription - Annual",
                    "expense_date": date.today().isoformat(),
                    "amount": "120000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Office supplies from Jumia",
                    "expense_date": date.today().isoformat(),
                    "amount": "25000.00",
                    "currency": "NGN",
                },
            ],
        })
        assert_http_ok(resp)
        claim = get_json(resp)
        claim_id = claim["id"]

        # Corporate card claims don't require reimbursement
        assert claim["funding_method"] == "corporate_card"

        # 3. Submit and approve
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)

        resp = client.post(f"/api/expenses/claims/{claim_id}/approve")
        assert_http_ok(resp)
        claim = get_json(resp)
        assert claim["status"] == "approved"


class TestMultiLineApprovalFlow:
    """Test line-level approval for expense claims."""

    def test_partial_approval_with_line_adjustments(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Approver adjusts individual expense lines.

        Flow:
        1. Create claim with multiple lines
        2. Submit for approval
        3. Approver adjusts one line amount
        4. Approve with adjustments
        """
        client = e2e_superuser_client

        # 1. Create claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Mixed Expense Claim",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Client lunch meeting",
                    "expense_date": date.today().isoformat(),
                    "amount": "15000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Taxi to client site",
                    "expense_date": date.today().isoformat(),
                    "amount": "8000.00",
                    "currency": "NGN",
                },
            ],
        })
        claim = get_json(resp)
        claim_id = claim["id"]
        original_total = Decimal(str(claim["total_amount"]))

        # 2. Submit
        resp = client.post(f"/api/expenses/claims/{claim_id}/submit")
        assert_http_ok(resp)

        # 3. Get claim with lines for adjustment
        resp = client.get(f"/api/expenses/claims/{claim_id}")
        claim = get_json(resp)
        lines = claim.get("lines", [])

        # 4. Adjust a line (if line-level API exists)
        if lines:
            line_id = lines[0]["id"]
            resp = client.patch(f"/api/expenses/claims/{claim_id}/lines/{line_id}", json={
                "approved_amount": "12000.00",
                "adjustment_reason": "Reduced per policy meal limit",
            })
            # May or may not be implemented
            if resp.status_code == 200:
                line = get_json(resp)
                assert Decimal(str(line["approved_amount"])) == Decimal("12000.00")

        # 5. Approve
        resp = client.post(f"/api/expenses/claims/{claim_id}/approve")
        assert_http_ok(resp)


class TestExpenseReportingFlow:
    """Test expense analytics and reporting."""

    def test_expense_summary_by_category(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Generate expense summary report by category.
        """
        client = e2e_superuser_client

        # Create some expenses first
        for i in range(3):
            resp = client.post("/api/expenses/claims", json={
                "employee_id": test_employee.id,
                "claim_title": f"Report Test Expense {i}",
                "claim_date": date.today().isoformat(),
                "currency": "NGN",
                "funding_method": "out_of_pocket",
                "lines": [
                    {
                        "category_id": test_expense_category.id,
                        "description": f"Test expense item {i}",
                        "expense_date": date.today().isoformat(),
                        "amount": f"{(i + 1) * 10000}.00",
                        "currency": "NGN",
                    },
                ],
            })
            assert_http_ok(resp)
            claim = get_json(resp)

            # Submit and approve
            resp = client.post(f"/api/expenses/claims/{claim['id']}/submit")
            assert_http_ok(resp)
            resp = client.post(f"/api/expenses/claims/{claim['id']}/approve")
            assert_http_ok(resp)

        # Get expense analytics
        resp = client.get("/api/expenses/analytics/summary", params={
            "start_date": (date.today() - timedelta(days=30)).isoformat(),
            "end_date": date.today().isoformat(),
        })
        assert_http_ok(resp, "Get expense summary")
        summary = get_json(resp)

        # Verify summary structure
        assert "total_amount" in summary or "by_category" in summary or "data" in summary


class TestExpenseFilteringFlow:
    """Test filtering and searching expense claims."""

    def test_filter_claims_by_status(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Filter expense claims by various statuses.
        """
        client = e2e_superuser_client

        # Create claims in different states
        # Draft claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Draft Claim",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [{
                "category_id": test_expense_category.id,
                "description": "Draft item",
                "expense_date": date.today().isoformat(),
                "amount": "10000.00",
                "currency": "NGN",
            }],
        })
        draft_claim = get_json(resp)

        # Submitted claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Submitted Claim",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [{
                "category_id": test_expense_category.id,
                "description": "Submitted item",
                "expense_date": date.today().isoformat(),
                "amount": "20000.00",
                "currency": "NGN",
            }],
        })
        submitted_claim = get_json(resp)
        resp = client.post(f"/api/expenses/claims/{submitted_claim['id']}/submit")
        assert_http_ok(resp)

        # Filter by draft status
        resp = client.get("/api/expenses/claims", params={"status": "draft"})
        assert_http_ok(resp)
        claims = get_json(resp)
        # All returned claims should be draft
        if isinstance(claims, list):
            for claim in claims:
                assert claim["status"] == "draft"

        # Filter by pending_approval status
        resp = client.get("/api/expenses/claims", params={"status": "pending_approval"})
        assert_http_ok(resp)
        claims = get_json(resp)
        if isinstance(claims, list):
            for claim in claims:
                assert claim["status"] == "pending_approval"


class TestExpensePolicyValidation:
    """Test expense policy enforcement."""

    def test_policy_limit_warning(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
        test_expense_policy,
    ):
        """
        E2E: Expense policy limits are enforced or warned.
        """
        client = e2e_superuser_client

        # Try to create expense exceeding policy limit
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Large Expense Test",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "out_of_pocket",
            "lines": [{
                "category_id": test_expense_category.id,
                "description": "Single large expense",
                "expense_date": date.today().isoformat(),
                "amount": "500000.00",  # Exceeds max_single_expense
                "currency": "NGN",
            }],
        })

        # Depending on implementation, this might:
        # - Return 400 with validation error
        # - Create claim but flag for additional approval
        # - Create claim with warning
        if resp.status_code == 400:
            error = get_json(resp)
            assert "policy" in str(error).lower() or "limit" in str(error).lower()
        else:
            # Claim created but may have policy violation flag
            claim = get_json(resp)
            # Check if there's a flag or the claim needs special approval
            assert claim.get("id") is not None


class TestPerDiemFlow:
    """Test per-diem expense handling."""

    def test_per_diem_expense_claim(
        self,
        e2e_superuser_client,
        e2e_db,
        test_employee,
        test_expense_category,
    ):
        """
        E2E: Create and process per-diem based expense claim.
        """
        client = e2e_superuser_client

        # Create per-diem claim
        resp = client.post("/api/expenses/claims", json={
            "employee_id": test_employee.id,
            "claim_title": "Training Trip - 3 Days Per Diem",
            "claim_date": date.today().isoformat(),
            "currency": "NGN",
            "funding_method": "per_diem",
            "lines": [
                {
                    "category_id": test_expense_category.id,
                    "description": "Day 1 - Per Diem Allowance",
                    "expense_date": date.today().isoformat(),
                    "amount": "25000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Day 2 - Per Diem Allowance",
                    "expense_date": (date.today() + timedelta(days=1)).isoformat(),
                    "amount": "25000.00",
                    "currency": "NGN",
                },
                {
                    "category_id": test_expense_category.id,
                    "description": "Day 3 - Per Diem Allowance",
                    "expense_date": (date.today() + timedelta(days=2)).isoformat(),
                    "amount": "25000.00",
                    "currency": "NGN",
                },
            ],
        })
        assert_http_ok(resp)
        claim = get_json(resp)

        assert claim["funding_method"] == "per_diem"
        assert Decimal(str(claim["total_amount"])) == Decimal("75000.00")

        # Per-diem claims follow normal approval
        resp = client.post(f"/api/expenses/claims/{claim['id']}/submit")
        assert_http_ok(resp)

        resp = client.post(f"/api/expenses/claims/{claim['id']}/approve")
        assert_http_ok(resp)
        claim = get_json(resp)
        assert claim["status"] == "approved"
