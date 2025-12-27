"""
E2E Tests: Invoice-to-Cash Flow

Tests the complete revenue cycle from invoice creation through payment collection.

Flow:
1. Create Invoice (Draft)
2. Submit Invoice
3. Verify AR aging
4. Receive Payment
5. Allocate Payment to Invoice
6. Verify Invoice marked as Paid
7. Reconciliation
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json
from tests.e2e.fixtures.factories import create_customer, create_invoice, create_payment


class TestInvoiceCreation:
    """Test invoice creation and management."""

    def test_create_invoice_draft(self, e2e_superuser_client, e2e_db):
        """Test creating a draft invoice."""
        customer = create_customer(e2e_db, name="Invoice Test Customer")

        payload = {
            "customer_id": customer.id,
            "invoice_date": datetime.now().isoformat(),
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "amount": 500000,
            "tax_amount": 0,
            "currency": "NGN",
            "description": "Consulting Services",
            "status": "pending",
        }

        response = e2e_superuser_client.post("/api/sales/invoices", json=payload)
        assert_http_ok(response, "Create invoice")

        data = get_json(response)
        assert data["customer_id"] == customer.id
        assert "id" in data

    def test_list_invoices(self, e2e_superuser_client, e2e_db):
        """Test invoice listing."""
        customer = create_customer(e2e_db, name="List Test Customer")
        create_invoice(e2e_db, customer_id=customer.id, amount=Decimal("100000"))
        create_invoice(e2e_db, customer_id=customer.id, amount=Decimal("200000"))

        response = e2e_superuser_client.get("/api/sales/invoices")
        assert_http_ok(response, "List invoices")

        data = get_json(response)
        assert "items" in data
        assert len(data["items"]) >= 2

    def test_filter_invoices_by_status(self, e2e_superuser_client, e2e_db):
        """Test filtering invoices by status."""
        customer = create_customer(e2e_db, name="Filter Test Customer")
        create_invoice(e2e_db, customer_id=customer.id, status="pending")
        create_invoice(e2e_db, customer_id=customer.id, status="paid")

        # Filter pending only
        response = e2e_superuser_client.get("/api/sales/invoices", params={"status": "pending"})
        assert_http_ok(response, "Filter invoices by status")

        data = get_json(response)
        for inv in data["items"]:
            assert inv["status"] == "pending"


class TestAccountsReceivable:
    """Test accounts receivable aging and reporting."""

    def test_ar_aging_report(self, e2e_superuser_client, e2e_db):
        """Test AR aging report calculation."""
        customer = create_customer(e2e_db, name="AR Aging Customer")

        # Create invoices with different ages
        # Current invoice
        create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("100000"),
            invoice_date=date.today() - timedelta(days=10),
            due_date=date.today() + timedelta(days=20),
            status="pending",
        )

        # 30 days overdue
        create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("200000"),
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            status="overdue",
        )

        response = e2e_superuser_client.get("/api/accounting/accounts-receivable")
        assert_http_ok(response, "Get AR aging")

        data = get_json(response)
        assert "aging" in data
        assert "total_receivable" in data
        assert data["total_receivable"] > 0

        # Check aging buckets exist
        aging = data["aging"]
        assert "current" in aging
        assert "1_30" in aging
        assert "31_60" in aging

    def test_customer_ar_balance(self, e2e_superuser_client, e2e_db):
        """Test filtering AR by specific customer."""
        customer = create_customer(e2e_db, name="Customer AR Test")
        create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("150000"),
            status="pending",
        )

        response = e2e_superuser_client.get(
            "/api/accounting/accounts-receivable",
            params={"customer_id": customer.id},
        )
        assert_http_ok(response, "Get customer AR")

        data = get_json(response)
        assert data["total_invoices"] >= 1


class TestPaymentCreation:
    """Test payment receipt creation."""

    def test_create_payment(self, e2e_superuser_client, e2e_db):
        """Test creating a customer payment."""
        customer = create_customer(e2e_db, name="Payment Test Customer")

        payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": 100000.0,
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "transaction_reference": "TRF-123456",
        }

        response = e2e_superuser_client.post("/api/accounting/ar-payments", json=payload)
        assert_http_ok(response, "Create payment")

        data = get_json(response)
        assert data["id"] is not None

    def test_list_payments(self, e2e_superuser_client, e2e_db):
        """Test payment listing."""
        customer = create_customer(e2e_db, name="Payment List Customer")
        create_payment(e2e_db, customer_id=customer.id, amount=Decimal("50000"))
        create_payment(e2e_db, customer_id=customer.id, amount=Decimal("75000"))

        response = e2e_superuser_client.get("/api/accounting/ar-payments")
        assert_http_ok(response, "List payments")

        data = get_json(response)
        assert "payments" in data
        assert len(data["payments"]) >= 2


class TestPaymentAllocation:
    """Test payment allocation to invoices."""

    def test_allocate_payment_to_invoice(self, e2e_superuser_client, e2e_db):
        """Test allocating a payment to an invoice."""
        customer = create_customer(e2e_db, name="Allocation Test Customer")
        invoice = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("100000"),
            status="pending",
        )

        # Create payment with allocation
        payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": 100000.0,
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "allocations": [
                {
                    "document_type": "invoice",
                    "document_id": invoice.id,
                    "allocated_amount": 100000.0,
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/ar-payments", json=payload)
        assert_http_ok(response, "Create payment with allocation")

        # Verify invoice status
        e2e_db.refresh(invoice)
        from app.models.invoice import InvoiceStatus
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_paid == Decimal("100000")

    def test_partial_payment_allocation(self, e2e_superuser_client, e2e_db):
        """Test partial payment allocation."""
        customer = create_customer(e2e_db, name="Partial Payment Customer")
        invoice = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("200000"),
            status="pending",
        )

        # Create partial payment
        payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": 100000.0,
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "allocations": [
                {
                    "document_type": "invoice",
                    "document_id": invoice.id,
                    "allocated_amount": 100000.0,
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/ar-payments", json=payload)
        assert_http_ok(response, "Create partial payment")

        # Verify invoice status is partially paid
        e2e_db.refresh(invoice)
        from app.models.invoice import InvoiceStatus
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID
        assert invoice.amount_paid == Decimal("100000")
        assert invoice.balance == Decimal("100000")

    def test_overpayment_rejected(self, e2e_superuser_client, e2e_db):
        """Test that overpayment is rejected."""
        customer = create_customer(e2e_db, name="Overpayment Test Customer")
        invoice = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("50000"),
            status="pending",
        )

        # Attempt to allocate more than invoice amount
        payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": 100000.0,
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "allocations": [
                {
                    "document_type": "invoice",
                    "document_id": invoice.id,
                    "allocated_amount": 100000.0,  # More than invoice
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/ar-payments", json=payload)
        # Should fail with 400 error
        assert_http_error(response, 400, "Overpayment should be rejected")


class TestInvoiceToCashFlow:
    """Test complete invoice-to-cash flow."""

    def test_full_invoice_to_cash_cycle(self, e2e_superuser_client, e2e_db):
        """
        Test complete flow:
        1. Create customer
        2. Create invoice
        3. Verify AR shows outstanding
        4. Receive payment
        5. Allocate to invoice
        6. Verify invoice paid
        7. Verify AR cleared
        """
        # Step 1: Create customer
        customer = create_customer(e2e_db, name="Full Cycle Customer")

        # Step 2: Create invoice
        invoice_amount = Decimal("500000")
        invoice = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=invoice_amount,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status="pending",
        )

        # Step 3: Verify AR shows outstanding
        ar_resp = e2e_superuser_client.get(
            "/api/accounting/accounts-receivable",
            params={"customer_id": customer.id},
        )
        ar_data = get_json(ar_resp)
        assert ar_data["total_receivable"] >= float(invoice_amount)

        # Step 4 & 5: Create payment with allocation
        payment_payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": float(invoice_amount),
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "transaction_reference": "FULL-CYCLE-PAY-001",
            "allocations": [
                {
                    "document_type": "invoice",
                    "document_id": invoice.id,
                    "allocated_amount": float(invoice_amount),
                },
            ],
        }
        pay_resp = e2e_superuser_client.post("/api/accounting/ar-payments", json=payment_payload)
        assert_http_ok(pay_resp, "Create payment")

        # Step 6: Verify invoice marked as paid
        e2e_db.refresh(invoice)
        from app.models.invoice import InvoiceStatus
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_paid == invoice_amount
        assert invoice.balance == Decimal("0")

        # Step 7: Verify AR cleared for this customer
        ar_resp_after = e2e_superuser_client.get(
            "/api/accounting/accounts-receivable",
            params={"customer_id": customer.id},
        )
        ar_data_after = get_json(ar_resp_after)
        # Should have no outstanding after full payment
        assert ar_data_after["total_invoices"] == 0 or ar_data_after["total_receivable"] == 0

    def test_multiple_invoice_payment(self, e2e_superuser_client, e2e_db):
        """Test paying multiple invoices with one payment."""
        customer = create_customer(e2e_db, name="Multi Invoice Customer")

        # Create multiple invoices
        invoice1 = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("100000"),
            status="pending",
        )
        invoice2 = create_invoice(
            e2e_db,
            customer_id=customer.id,
            amount=Decimal("150000"),
            status="pending",
        )

        # Pay both with single payment
        payload = {
            "customer_id": customer.id,
            "payment_date": datetime.now().isoformat(),
            "amount": 250000.0,
            "currency": "NGN",
            "payment_method": "bank_transfer",
            "allocations": [
                {
                    "document_type": "invoice",
                    "document_id": invoice1.id,
                    "allocated_amount": 100000.0,
                },
                {
                    "document_type": "invoice",
                    "document_id": invoice2.id,
                    "allocated_amount": 150000.0,
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/ar-payments", json=payload)
        assert_http_ok(response, "Pay multiple invoices")

        # Verify both invoices are paid
        e2e_db.refresh(invoice1)
        e2e_db.refresh(invoice2)

        from app.models.invoice import InvoiceStatus
        assert invoice1.status == InvoiceStatus.PAID
        assert invoice2.status == InvoiceStatus.PAID


class TestJournalEntryWorkflow:
    """Test journal entry creation and posting."""

    def test_create_journal_entry(self, e2e_superuser_client, e2e_db, e2e_chart_of_accounts):
        """Test manual journal entry creation."""
        cash_account = e2e_chart_of_accounts.get("1000")
        revenue_account = e2e_chart_of_accounts.get("4000")

        if not cash_account or not revenue_account:
            pytest.skip("Chart of accounts not available")

        payload = {
            "posting_date": date.today().isoformat(),
            "description": "Manual adjustment entry",
            "lines": [
                {
                    "account_id": cash_account.id,
                    "debit": 50000.0,
                    "credit": 0,
                    "description": "Cash receipt",
                },
                {
                    "account_id": revenue_account.id,
                    "debit": 0,
                    "credit": 50000.0,
                    "description": "Revenue recognition",
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/journal-entries", json=payload)
        # May return 201 or 200 depending on implementation
        assert response.status_code in [200, 201], f"Create JE: {response.text}"

    def test_journal_entry_must_balance(self, e2e_superuser_client, e2e_db, e2e_chart_of_accounts):
        """Test that unbalanced journal entries are rejected."""
        cash_account = e2e_chart_of_accounts.get("1000")
        revenue_account = e2e_chart_of_accounts.get("4000")

        if not cash_account or not revenue_account:
            pytest.skip("Chart of accounts not available")

        # Unbalanced entry
        payload = {
            "posting_date": date.today().isoformat(),
            "description": "Unbalanced entry",
            "lines": [
                {
                    "account_id": cash_account.id,
                    "debit": 50000.0,
                    "credit": 0,
                },
                {
                    "account_id": revenue_account.id,
                    "debit": 0,
                    "credit": 30000.0,  # Not equal to debit
                },
            ],
        }

        response = e2e_superuser_client.post("/api/accounting/journal-entries", json=payload)
        # Should fail with 400
        assert_http_error(response, 400, "Unbalanced JE should be rejected")
