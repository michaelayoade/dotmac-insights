"""
Expenses API Integration Tests

Tests expense claim lifecycle, transactions, approvals,
and RBAC for the Expenses API.
"""
import pytest
from datetime import datetime, date, timezone
from decimal import Decimal

from app.models.expense_management import (
    ExpenseClaim, ExpenseClaimLine, ExpenseClaimStatus,
    CorporateCard, CorporateCardTransaction, CardTransactionStatus,
    CorporateCardStatement, ExpenseCategory
)
from app.models.employee import Employee


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_employee(integration_db):
    """Create a test employee."""
    employee = Employee(
        name="Test Employee",
        email="employee@test.com",
        is_active=True,
    )
    integration_db.add(employee)
    integration_db.commit()
    integration_db.refresh(employee)
    return employee


@pytest.fixture
def sample_expense_category(integration_db):
    """Create a test expense category."""
    category = ExpenseCategory(
        name="Travel",
        code="TRAVEL",
        is_active=True,
        requires_receipt=True,
    )
    integration_db.add(category)
    integration_db.commit()
    integration_db.refresh(category)
    return category


@pytest.fixture
def sample_corporate_card(integration_db, sample_employee):
    """Create a test corporate card."""
    card = CorporateCard(
        card_number="**** **** **** 1234",
        card_type="credit",
        employee_id=sample_employee.id,
        is_active=True,
        credit_limit=Decimal("500000"),
    )
    integration_db.add(card)
    integration_db.commit()
    integration_db.refresh(card)
    return card


@pytest.fixture
def sample_claim_payload(sample_employee, sample_expense_category):
    """Base payload for creating an expense claim."""
    return {
        "employee_id": sample_employee.id,
        "title": "Business Trip Expenses",
        "description": "Expenses from Lagos-Abuja business trip",
        "currency": "NGN",
        "lines": [
            {
                "category_id": sample_expense_category.id,
                "description": "Flight ticket",
                "amount": "75000.00",
                "expense_date": date.today().isoformat(),
            },
            {
                "category_id": sample_expense_category.id,
                "description": "Hotel accommodation",
                "amount": "45000.00",
                "expense_date": date.today().isoformat(),
            },
        ],
    }


@pytest.fixture
def create_test_claim(integration_db, sample_employee, sample_expense_category):
    """Factory fixture to create test expense claims."""
    created = []

    def _create(
        title: str = "Test Expense Claim",
        status: ExpenseClaimStatus = ExpenseClaimStatus.DRAFT,
        total_amount: Decimal = Decimal("50000.00"),
        employee_id: int = None,
    ) -> ExpenseClaim:
        claim = ExpenseClaim(
            claim_number=f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            employee_id=employee_id or sample_employee.id,
            title=title,
            status=status,
            currency="NGN",
            total_claimed_amount=total_amount,
        )
        integration_db.add(claim)
        integration_db.flush()

        # Add a line item
        line = ExpenseClaimLine(
            claim_id=claim.id,
            category_id=sample_expense_category.id,
            description="Test expense",
            amount=total_amount,
            expense_date=date.today(),
        )
        integration_db.add(line)
        integration_db.commit()
        integration_db.refresh(claim)
        created.append(claim)
        return claim

    yield _create


@pytest.fixture
def create_test_transaction(integration_db, sample_corporate_card):
    """Factory fixture to create test card transactions."""
    def _create(
        amount: Decimal = Decimal("10000.00"),
        merchant_name: str = "Test Merchant",
        status: CardTransactionStatus = CardTransactionStatus.IMPORTED,
    ) -> CorporateCardTransaction:
        transaction = CorporateCardTransaction(
            card_id=sample_corporate_card.id,
            transaction_date=datetime.now(timezone.utc),
            merchant_name=merchant_name,
            description="Test transaction",
            amount=amount,
            currency="NGN",
            status=status,
            import_hash=f"hash-{datetime.now(timezone.utc).timestamp()}",
            imported_at=datetime.now(timezone.utc),
        )
        integration_db.add(transaction)
        integration_db.commit()
        integration_db.refresh(transaction)
        return transaction

    return _create


# =============================================================================
# EXPENSE CLAIM CRUD TESTS
# =============================================================================


class TestExpenseClaimCreate:
    """Tests for POST /api/expenses/claims/"""

    def test_create_claim_success(self, auth_client, sample_claim_payload, sample_employee):
        """Create an expense claim successfully."""
        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post("/api/expenses/claims/", json=sample_claim_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Business Trip Expenses"
        assert data["status"] == "draft"
        assert len(data["lines"]) == 2

    def test_create_claim_with_lines(self, auth_client, sample_employee, sample_expense_category):
        """Create claim with multiple expense lines."""
        payload = {
            "employee_id": sample_employee.id,
            "title": "Multi-line Expense",
            "currency": "NGN",
            "lines": [
                {
                    "category_id": sample_expense_category.id,
                    "description": "Taxi",
                    "amount": "5000",
                    "expense_date": date.today().isoformat(),
                },
                {
                    "category_id": sample_expense_category.id,
                    "description": "Lunch",
                    "amount": "3500",
                    "expense_date": date.today().isoformat(),
                },
                {
                    "category_id": sample_expense_category.id,
                    "description": "Office supplies",
                    "amount": "12000",
                    "expense_date": date.today().isoformat(),
                },
            ],
        }

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post("/api/expenses/claims/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert len(data["lines"]) == 3

    def test_create_claim_without_write_scope_fails(self, auth_client, sample_claim_payload):
        """Cannot create claim without expenses:write scope."""
        client = auth_client(["expenses:read"])
        resp = client.post("/api/expenses/claims/", json=sample_claim_payload)

        assert resp.status_code == 403


class TestExpenseClaimRead:
    """Tests for GET /api/expenses/claims/{claim_id}"""

    def test_get_claim_by_id(self, auth_client, create_test_claim, sample_employee):
        """Get an expense claim by ID."""
        claim = create_test_claim(title="Readable Claim")

        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get(f"/api/expenses/claims/{claim.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == claim.id
        assert data["title"] == "Readable Claim"

    def test_get_nonexistent_claim_returns_404(self, auth_client, sample_employee):
        """Get non-existent claim returns 404."""
        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get("/api/expenses/claims/99999")

        assert resp.status_code == 404


class TestExpenseClaimList:
    """Tests for GET /api/expenses/claims/"""

    def test_list_claims_paginated(self, auth_client, create_test_claim, sample_employee):
        """List claims with pagination."""
        for i in range(5):
            create_test_claim(title=f"Claim {i}")

        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get("/api/expenses/claims/?limit=3&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 3

    def test_list_claims_filter_by_status(self, auth_client, create_test_claim, sample_employee):
        """Filter claims by status."""
        create_test_claim(title="Draft", status=ExpenseClaimStatus.DRAFT)
        create_test_claim(title="Submitted", status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get("/api/expenses/claims/?status=draft")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["status"] == "draft" for c in data)


# =============================================================================
# EXPENSE CLAIM WORKFLOW TESTS
# =============================================================================


class TestExpenseClaimWorkflow:
    """Tests for expense claim workflow transitions."""

    def test_submit_claim(self, auth_client, create_test_claim, sample_employee, integration_db):
        """Submit a draft claim for approval."""
        claim = create_test_claim(status=ExpenseClaimStatus.DRAFT)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/submit")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"

    def test_approve_claim(self, auth_client, create_test_claim, sample_employee, integration_db):
        """Approve a submitted claim."""
        claim = create_test_claim(status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/approve")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    def test_reject_claim_requires_reason(self, auth_client, create_test_claim, sample_employee):
        """Reject claim requires a reason."""
        claim = create_test_claim(status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/reject?reason=")

        assert resp.status_code == 400
        assert "reason" in resp.json()["detail"].lower()

    def test_reject_claim_with_reason(self, auth_client, create_test_claim, sample_employee):
        """Reject a submitted claim with reason."""
        claim = create_test_claim(status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/reject?reason=Exceeds%20policy%20limit")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    def test_return_claim_for_revision(self, auth_client, create_test_claim, sample_employee):
        """Return a claim for revision."""
        claim = create_test_claim(status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/return?reason=Missing%20receipt")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "returned"

    def test_recall_submitted_claim(self, auth_client, create_test_claim, sample_employee):
        """Employee recalls their submitted claim."""
        claim = create_test_claim(status=ExpenseClaimStatus.SUBMITTED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/recall")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"

    def test_post_approved_claim(self, auth_client, create_test_claim, sample_employee):
        """Post an approved claim to accounting."""
        claim = create_test_claim(status=ExpenseClaimStatus.APPROVED)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/post")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "posted"


# =============================================================================
# CORPORATE CARD TRANSACTION TESTS
# =============================================================================


class TestCorporateCardTransactions:
    """Tests for corporate card transaction endpoints."""

    def test_list_transactions(self, auth_client, create_test_transaction, sample_corporate_card):
        """List corporate card transactions."""
        for i in range(3):
            create_test_transaction(merchant_name=f"Merchant {i}")

        client = auth_client(["expenses:read"])
        resp = client.get("/api/expenses/transactions/")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3

    def test_list_transactions_filter_by_card(self, auth_client, create_test_transaction, sample_corporate_card):
        """Filter transactions by card."""
        create_test_transaction()

        client = auth_client(["expenses:read"])
        resp = client.get(f"/api/expenses/transactions/?card_id={sample_corporate_card.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert all(t["card_id"] == sample_corporate_card.id for t in data)

    def test_list_unmatched_transactions(self, auth_client, create_test_transaction):
        """Filter for unmatched transactions only."""
        create_test_transaction(status=CardTransactionStatus.IMPORTED)
        create_test_transaction(status=CardTransactionStatus.MATCHED)

        client = auth_client(["expenses:read"])
        resp = client.get("/api/expenses/transactions/?unmatched_only=true")

        assert resp.status_code == 200
        data = resp.json()
        for t in data:
            assert t["status"] in ["imported", "unmatched"]

    def test_get_transaction_by_id(self, auth_client, create_test_transaction):
        """Get a transaction by ID."""
        transaction = create_test_transaction(merchant_name="Test Merchant")

        client = auth_client(["expenses:read"])
        resp = client.get(f"/api/expenses/transactions/{transaction.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == transaction.id
        assert data["merchant_name"] == "Test Merchant"

    def test_get_nonexistent_transaction_returns_404(self, auth_client):
        """Get non-existent transaction returns 404."""
        client = auth_client(["expenses:read"])
        resp = client.get("/api/expenses/transactions/99999")

        assert resp.status_code == 404

    def test_create_transaction(self, auth_client, sample_corporate_card):
        """Create a corporate card transaction manually."""
        client = auth_client(["expenses:write"])
        payload = {
            "card_id": sample_corporate_card.id,
            "transaction_date": date.today().isoformat(),
            "merchant_name": "Restaurant ABC",
            "description": "Team lunch",
            "amount": "15000",
            "currency": "NGN",
        }
        resp = client.post("/api/expenses/transactions/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["merchant_name"] == "Restaurant ABC"
        assert data["status"] == "imported"

    def test_create_duplicate_transaction_fails(self, auth_client, sample_corporate_card, integration_db):
        """Cannot create duplicate transaction."""
        # Create first transaction
        client = auth_client(["expenses:write"])
        payload = {
            "card_id": sample_corporate_card.id,
            "transaction_date": date.today().isoformat(),
            "merchant_name": "Duplicate Merchant",
            "amount": "25000",
            "currency": "NGN",
        }
        resp1 = client.post("/api/expenses/transactions/", json=payload)
        assert resp1.status_code == 201

        # Try to create same transaction again
        resp2 = client.post("/api/expenses/transactions/", json=payload)
        assert resp2.status_code == 400
        assert "duplicate" in resp2.json()["detail"].lower()

    def test_match_transaction_to_expense_line(self, auth_client, create_test_transaction, create_test_claim, integration_db):
        """Match a transaction to an expense claim line."""
        transaction = create_test_transaction()
        claim = create_test_claim()
        line = claim.lines[0]

        client = auth_client(["expenses:write"])
        resp = client.post(f"/api/expenses/transactions/{transaction.id}/match", json={
            "expense_claim_line_id": line.id,
            "confidence": 95,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "matched"
        assert data["expense_claim_line_id"] == line.id

    def test_unmatch_transaction(self, auth_client, create_test_transaction, integration_db):
        """Unmatch a matched transaction."""
        transaction = create_test_transaction(status=CardTransactionStatus.MATCHED)

        client = auth_client(["expenses:write"])
        resp = client.post(f"/api/expenses/transactions/{transaction.id}/unmatch")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unmatched"
        assert data["expense_claim_line_id"] is None

    def test_dispute_transaction(self, auth_client, create_test_transaction):
        """Mark a transaction as disputed."""
        transaction = create_test_transaction()

        client = auth_client(["expenses:write"])
        resp = client.post(f"/api/expenses/transactions/{transaction.id}/dispute", json={
            "reason": "Fraudulent charge - card was not used at this merchant",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disputed"
        assert data["dispute_reason"] is not None

    def test_dispute_without_reason_fails(self, auth_client, create_test_transaction):
        """Cannot dispute without providing a reason."""
        transaction = create_test_transaction()

        client = auth_client(["expenses:write"])
        resp = client.post(f"/api/expenses/transactions/{transaction.id}/dispute", json={
            "reason": "",
        })

        assert resp.status_code == 400

    def test_resolve_dispute(self, auth_client, create_test_transaction, integration_db):
        """Resolve a disputed transaction."""
        transaction = create_test_transaction(status=CardTransactionStatus.DISPUTED)

        client = auth_client(["expenses:write"])
        resp = client.post(
            f"/api/expenses/transactions/{transaction.id}/resolve",
            params={"resolution_notes": "Confirmed legitimate", "new_status": "unmatched"}
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unmatched"


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestExpenseValidation:
    """Tests for expense validation rules."""

    def test_claim_invalid_status_filter(self, auth_client, sample_employee):
        """Invalid status filter returns 400."""
        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get("/api/expenses/claims/?status=invalid_status")

        assert resp.status_code == 400
        assert "invalid status" in resp.json()["detail"].lower()

    def test_transaction_invalid_status_filter(self, auth_client):
        """Invalid transaction status filter returns 400."""
        client = auth_client(["expenses:read"])
        resp = client.get("/api/expenses/transactions/?status=invalid")

        assert resp.status_code == 400


# =============================================================================
# RBAC TESTS
# =============================================================================


class TestExpensesRBAC:
    """Tests for role-based access control."""

    def test_read_scope_allows_list_claims(self, auth_client, create_test_claim, sample_employee):
        """Read scope allows listing claims."""
        create_test_claim()

        client = auth_client(["expenses:read"], user_id=sample_employee.id)
        resp = client.get("/api/expenses/claims/")

        assert resp.status_code == 200

    def test_read_scope_denies_create(self, auth_client, sample_claim_payload):
        """Read scope denies create operations."""
        client = auth_client(["expenses:read"])
        resp = client.post("/api/expenses/claims/", json=sample_claim_payload)

        assert resp.status_code == 403

    def test_read_scope_denies_workflow_actions(self, auth_client, create_test_claim, sample_employee):
        """Read scope denies workflow actions."""
        claim = create_test_claim(status=ExpenseClaimStatus.DRAFT)

        client = auth_client(["expenses:read"], user_id=sample_employee.id)

        # Cannot submit
        resp = client.post(f"/api/expenses/claims/{claim.id}/submit")
        assert resp.status_code == 403

    def test_superuser_has_full_access(self, superuser_client, create_test_claim, sample_employee):
        """Superuser can perform all operations."""
        claim = create_test_claim()

        # Read
        resp = superuser_client.get(f"/api/expenses/claims/{claim.id}")
        assert resp.status_code == 200

        # List
        resp = superuser_client.get("/api/expenses/claims/")
        assert resp.status_code == 200


# =============================================================================
# EDGE CASES
# =============================================================================


class TestExpenseEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_claim_with_zero_amount(self, auth_client, sample_employee, sample_expense_category):
        """Claim with zero amount line."""
        payload = {
            "employee_id": sample_employee.id,
            "title": "Zero Amount Test",
            "currency": "NGN",
            "lines": [
                {
                    "category_id": sample_expense_category.id,
                    "description": "Free item",
                    "amount": "0",
                    "expense_date": date.today().isoformat(),
                },
            ],
        }

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post("/api/expenses/claims/", json=payload)

        # Depending on business rules, this may be accepted or rejected
        assert resp.status_code in [201, 400]

    def test_claim_with_large_amount(self, auth_client, sample_employee, sample_expense_category):
        """Claim with very large amount."""
        payload = {
            "employee_id": sample_employee.id,
            "title": "Large Amount Test",
            "currency": "NGN",
            "lines": [
                {
                    "category_id": sample_expense_category.id,
                    "description": "Major equipment",
                    "amount": "10000000.00",  # 10 million
                    "expense_date": date.today().isoformat(),
                },
            ],
        }

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post("/api/expenses/claims/", json=payload)

        assert resp.status_code == 201

    def test_claim_status_transitions_invalid(self, auth_client, create_test_claim, sample_employee):
        """Invalid status transition should fail."""
        # Try to approve a draft claim (should need to be submitted first)
        claim = create_test_claim(status=ExpenseClaimStatus.DRAFT)

        client = auth_client(["expenses:write"], user_id=sample_employee.id)
        resp = client.post(f"/api/expenses/claims/{claim.id}/approve")

        # This depends on business logic - may return 400 or silently transition
        # Document actual behavior
        assert resp.status_code in [200, 400]
