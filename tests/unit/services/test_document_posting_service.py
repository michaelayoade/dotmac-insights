"""
Unit tests for DocumentPostingService.

Tests GL posting for invoices, bills, payments, credit notes, and reversals.
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
import enum

import pytest

# Import the service and related classes
from app.services.document_posting import (
    DocumentPostingService,
    PostingError,
)
from app.models.accounting_ext import FiscalPeriodStatus

# Import mock fixtures
from tests.unit.conftest import (
    MockSession,
    MockInvoice,
    MockInvoiceStatus,
    MockPurchaseInvoice,
    MockPurchaseInvoiceStatus,
    MockPayment,
    MockSupplierPayment,
)


# =============================================================================
# MOCK ACCOUNTING CLASSES
# =============================================================================


class MockJournalEntryType(str, enum.Enum):
    JOURNAL_ENTRY = "Journal Entry"
    BANK_ENTRY = "Bank Entry"
    CREDIT_NOTE = "Credit Note"
    DEBIT_NOTE = "Debit Note"


@dataclass
class MockJournalEntry:
    """Mock Journal Entry for testing."""
    id: int = 1
    erpnext_id: str = "JE-00001"
    voucher_type: MockJournalEntryType = MockJournalEntryType.JOURNAL_ENTRY
    posting_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    company: Optional[str] = "Default Company"
    total_debit: Decimal = Decimal("0")
    total_credit: Decimal = Decimal("0")
    user_remark: Optional[str] = None
    docstatus: int = 1


@dataclass
class MockGLEntry:
    """Mock GL Entry for testing."""
    id: int = 1
    posting_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    account: str = "1100-Accounts Receivable"
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    debit_in_account_currency: Decimal = Decimal("0")
    credit_in_account_currency: Decimal = Decimal("0")
    voucher_type: str = "Journal Entry"
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = "Default Company"


@dataclass
class MockFiscalPeriod:
    """Mock Fiscal Period for testing."""
    id: int = 1
    period_name: str = "January 2024"
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2024, 1, 31)
    status: FiscalPeriodStatus = FiscalPeriodStatus.OPEN


@dataclass
class MockCreditNote:
    """Mock Credit Note for testing."""
    id: int = 1
    credit_number: str = "CN-001"
    customer_id: int = 1
    customer_account_id: Optional[int] = None
    amount: Decimal = Decimal("100.00")
    issue_date: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    posting_date: Optional[datetime] = None
    company: Optional[str] = "Default Company"
    docstatus: int = 0
    journal_entry_id: Optional[int] = None
    workflow_status: Optional[str] = None

    def __post_init__(self):
        if self.customer_account_id is None:
            self.customer_account_id = self.customer_id


@dataclass
class MockAccountResolver:
    """Mock AccountResolver for testing."""

    def resolve_receivable_account(self, company: Optional[str] = None) -> str:
        return "1100-Accounts Receivable"

    def resolve_payable_account(self, company: Optional[str] = None) -> str:
        return "2100-Accounts Payable"

    def resolve_income_account(self, company: Optional[str] = None) -> str:
        return "4000-Revenue"

    def resolve_expense_account(self, company: Optional[str] = None) -> str:
        return "5000-Expenses"

    def resolve_tax_liability_account(self, company: Optional[str] = None) -> str:
        return "2200-VAT Payable"

    def resolve_tax_asset_account(self, company: Optional[str] = None) -> str:
        return "1200-Input VAT"

    def resolve_bank_account(self, company: Optional[str] = None) -> str:
        return "1010-Bank Account"

    def resolve_sales_returns_account(self, company: Optional[str] = None) -> str:
        return "4100-Sales Returns"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MockSession()


@pytest.fixture
def mock_account_resolver():
    """Create mock account resolver."""
    return MockAccountResolver()


@pytest.fixture
def service(mock_db, mock_account_resolver):
    """Create DocumentPostingService with mocks."""
    return DocumentPostingService(mock_db, mock_account_resolver)


@pytest.fixture
def invoice_unpaid():
    """Unpaid invoice ready to post."""
    return MockInvoice(
        id=1,
        invoice_number="INV-001",
        customer_id=1,
        total_amount=Decimal("1180.00"),
        amount=Decimal("1000.00"),  # Net
        tax_amount=Decimal("180.00"),  # 18% VAT
        amount_paid=Decimal("0.00"),
        status=MockInvoiceStatus.PENDING,
        invoice_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        company="Default Company",
        docstatus=0,
    )


@pytest.fixture
def invoice_no_tax():
    """Invoice without tax."""
    return MockInvoice(
        id=2,
        invoice_number="INV-002",
        customer_id=1,
        total_amount=Decimal("500.00"),
        amount=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        docstatus=0,
        company="Default Company",
    )


@pytest.fixture
def invoice_already_posted():
    """Already posted invoice."""
    return MockInvoice(
        id=3,
        invoice_number="INV-003",
        docstatus=1,  # Already posted
    )


@pytest.fixture
def bill_unpaid():
    """Unpaid bill ready to post."""
    return MockPurchaseInvoice(
        id=1,
        bill_number="BILL-001",
        supplier="1",
        supplier_name="Test Supplier",
        grand_total=Decimal("590.00"),
        tax_amount=Decimal("90.00"),
        paid_amount=Decimal("0.00"),
        status=MockPurchaseInvoiceStatus.UNPAID,
        posting_date=date(2024, 1, 15),
        company="Default Company",
        docstatus=0,
    )


@pytest.fixture
def payment_unposted():
    """Unposted payment."""
    payment = MockPayment(
        id=1,
        customer_id=1,
        receipt_number="REC-001",
        amount=Decimal("500.00"),
        payment_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
        docstatus=0,
    )
    # Add mock invoice reference
    payment.invoice = MagicMock()
    payment.invoice.company = "Default Company"
    return payment


@pytest.fixture
def supplier_payment_unposted():
    """Unposted supplier payment."""
    return MockSupplierPayment(
        id=1,
        supplier_id=1,
        payment_number="PAY-001",
        paid_amount=Decimal("500.00"),
        posting_date=date(2024, 1, 20),
        company="Default Company",
        docstatus=0,
    )


@pytest.fixture
def credit_note():
    """Credit note for posting."""
    return MockCreditNote(
        id=1,
        credit_number="CN-001",
        customer_id=1,
        amount=Decimal("100.00"),
        issue_date=datetime(2024, 1, 25, tzinfo=timezone.utc),
        company="Default Company",
        docstatus=0,
    )


@pytest.fixture
def open_period():
    """Open fiscal period."""
    return MockFiscalPeriod(
        id=1,
        period_name="January 2024",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )


@pytest.fixture
def closed_period():
    """Closed fiscal period."""
    return MockFiscalPeriod(
        id=2,
        period_name="December 2023",
        start_date=date(2023, 12, 1),
        end_date=date(2023, 12, 31),
        status=FiscalPeriodStatus.HARD_CLOSED,
    )


@pytest.fixture
def posted_journal_entry():
    """Posted journal entry for reversal testing."""
    return MockJournalEntry(
        id=1,
        erpnext_id="JE-00001",
        voucher_type=MockJournalEntryType.JOURNAL_ENTRY,
        posting_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        company="Default Company",
        total_debit=Decimal("1000.00"),
        total_credit=Decimal("1000.00"),
        docstatus=1,
    )


# =============================================================================
# POST INVOICE TESTS
# =============================================================================


class TestPostInvoice:
    """Tests for post_invoice method."""

    def test_post_invoice_creates_journal_entry(
        self, service, mock_db, invoice_unpaid
    ):
        """Test posting invoice creates a journal entry."""
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                # Mock invoice query
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice_unpaid

                # Mock fiscal period query
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None

                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    result = service.post_invoice(invoice_id=1, user_id=1)

                    # Verify journal entry was created
                    mock_create_je.assert_called_once()
                    call_kwargs = mock_create_je.call_args[1]

                    # Check entries include AR debit, revenue credit, tax credit
                    entries = call_kwargs['entries']
                    assert len(entries) == 3

                    # AR debit
                    assert entries[0]['debit'] == Decimal("1180.00")
                    assert entries[0]['credit'] == Decimal("0")

                    # Revenue credit
                    assert entries[1]['debit'] == Decimal("0")
                    assert entries[1]['credit'] == Decimal("1000.00")

                    # Tax credit
                    assert entries[2]['debit'] == Decimal("0")
                    assert entries[2]['credit'] == Decimal("180.00")

        # Invoice should be marked as posted
        assert invoice_unpaid.docstatus == 1
        assert invoice_unpaid.workflow_status == "posted"

    def test_post_invoice_without_tax(
        self, service, mock_db, invoice_no_tax
    ):
        """Test posting invoice without tax creates only 2 entries."""
        created_je = MockJournalEntry(id=2)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice_no_tax
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_invoice(invoice_id=2, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    # No tax entry - only AR debit and Revenue credit
                    assert len(entries) == 2

    def test_post_invoice_not_found_raises_error(self, service, mock_db):
        """Test posting non-existent invoice raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_inv_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_invoice(invoice_id=999, user_id=1)

        assert "Invoice not found" in str(exc_info.value)

    def test_post_already_posted_invoice_raises_error(
        self, service, mock_db, invoice_already_posted
    ):
        """Test posting already posted invoice raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice_already_posted
                mock_query.return_value = mock_inv_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_invoice(invoice_id=3, user_id=1)

        assert "already posted" in str(exc_info.value)

    def test_post_invoice_closed_period_raises_error(
        self, service, mock_db, invoice_unpaid, closed_period
    ):
        """Test posting to closed fiscal period raises error."""
        invoice_unpaid.invoice_date = datetime(2023, 12, 15, tzinfo=timezone.utc)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice_unpaid
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = closed_period
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with pytest.raises(PostingError) as exc_info:
                    service.post_invoice(invoice_id=1, user_id=1)

        assert "not open" in str(exc_info.value)

    def test_post_invoice_with_custom_posting_date(
        self, service, mock_db, invoice_unpaid
    ):
        """Test posting invoice with custom posting date."""
        custom_date = datetime(2024, 1, 20, tzinfo=timezone.utc)
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice_unpaid
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_invoice(invoice_id=1, user_id=1, posting_date=custom_date)

                    call_kwargs = mock_create_je.call_args[1]
                    assert call_kwargs['posting_date'] == custom_date


# =============================================================================
# POST BILL TESTS
# =============================================================================


class TestPostBill:
    """Tests for post_bill method."""

    def test_post_bill_creates_journal_entry(
        self, service, mock_db, bill_unpaid
    ):
        """Test posting bill creates journal entry with AP credit, expense debit."""
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_bill_query = MagicMock()
                mock_bill_query.filter.return_value.first.return_value = bill_unpaid
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_bill_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_bill(bill_id=1, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    assert len(entries) == 3

                    # AP credit
                    assert entries[0]['credit'] == Decimal("590.00")
                    assert entries[0]['party_type'] == "Supplier"

                    # Expense debit (net = 590 - 90 = 500)
                    assert entries[1]['debit'] == Decimal("500.00")

                    # Tax asset debit
                    assert entries[2]['debit'] == Decimal("90.00")

        assert bill_unpaid.docstatus == 1

    def test_post_bill_not_found_raises_error(self, service, mock_db):
        """Test posting non-existent bill raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_bill_query = MagicMock()
                mock_bill_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_bill_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_bill(bill_id=999, user_id=1)

        assert "Bill not found" in str(exc_info.value)

    def test_post_bill_already_posted_raises_error(self, service, mock_db):
        """Test posting already posted bill raises error."""
        posted_bill = MockPurchaseInvoice(id=1, docstatus=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_bill_query = MagicMock()
                mock_bill_query.filter.return_value.first.return_value = posted_bill
                mock_query.return_value = mock_bill_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_bill(bill_id=1, user_id=1)

        assert "already posted" in str(exc_info.value)

    def test_post_bill_without_posting_date_raises_error(self, service, mock_db):
        """Test posting bill without posting date raises error."""
        bill = MockPurchaseInvoice(id=1, posting_date=None, docstatus=0)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_bill_query = MagicMock()
                mock_bill_query.filter.return_value.first.return_value = bill
                mock_query.return_value = mock_bill_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_bill(bill_id=1, user_id=1)

        assert "Posting date is required" in str(exc_info.value)


# =============================================================================
# POST PAYMENT TESTS
# =============================================================================


class TestPostPayment:
    """Tests for post_payment method."""

    def test_post_payment_creates_journal_entry(
        self, service, mock_db, payment_unposted
    ):
        """Test posting payment creates bank debit and AR credit."""
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_pay_query = MagicMock()
                mock_pay_query.filter.return_value.first.return_value = payment_unposted
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_pay_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_payment(payment_id=1, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    assert len(entries) == 2

                    # Bank debit
                    assert entries[0]['debit'] == Decimal("500.00")
                    assert entries[0]['account'] == "1010-Bank Account"

                    # AR credit
                    assert entries[1]['credit'] == Decimal("500.00")
                    assert entries[1]['party_type'] == "Customer"

        assert payment_unposted.docstatus == 1

    def test_post_payment_not_found_raises_error(self, service, mock_db):
        """Test posting non-existent payment raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_pay_query = MagicMock()
                mock_pay_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_pay_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_payment(payment_id=999, user_id=1)

        assert "Payment not found" in str(exc_info.value)

    def test_post_payment_already_posted_raises_error(self, service, mock_db):
        """Test posting already posted payment raises error."""
        posted_payment = MockPayment(id=1, docstatus=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_pay_query = MagicMock()
                mock_pay_query.filter.return_value.first.return_value = posted_payment
                mock_query.return_value = mock_pay_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_payment(payment_id=1, user_id=1)

        assert "already posted" in str(exc_info.value)


# =============================================================================
# POST SUPPLIER PAYMENT TESTS
# =============================================================================


class TestPostSupplierPayment:
    """Tests for post_supplier_payment method."""

    def test_post_supplier_payment_creates_journal_entry(
        self, service, mock_db, supplier_payment_unposted
    ):
        """Test posting supplier payment creates bank credit and AP debit."""
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_pay_query = MagicMock()
                mock_pay_query.filter.return_value.first.return_value = supplier_payment_unposted
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_pay_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_supplier_payment(payment_id=1, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    assert len(entries) == 2

                    # Bank credit
                    assert entries[0]['credit'] == Decimal("500.00")

                    # AP debit
                    assert entries[1]['debit'] == Decimal("500.00")
                    assert entries[1]['party_type'] == "Supplier"

        assert supplier_payment_unposted.docstatus == 1

    def test_post_supplier_payment_not_found_raises_error(self, service, mock_db):
        """Test posting non-existent supplier payment raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_pay_query = MagicMock()
                mock_pay_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_pay_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_supplier_payment(payment_id=999, user_id=1)

        assert "Supplier payment not found" in str(exc_info.value)


# =============================================================================
# POST CREDIT NOTE TESTS
# =============================================================================


class TestPostCreditNote:
    """Tests for post_credit_note method."""

    def test_post_credit_note_creates_journal_entry(
        self, service, mock_db, credit_note
    ):
        """Test posting credit note creates AR credit and sales returns debit."""
        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_cn_query = MagicMock()
                mock_cn_query.filter.return_value.first.return_value = credit_note
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_cn_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_credit_note(credit_note_id=1, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    assert len(entries) == 2

                    # AR credit
                    assert entries[0]['credit'] == Decimal("100.00")
                    assert entries[0]['party_type'] == "Customer"

                    # Sales returns debit
                    assert entries[1]['debit'] == Decimal("100.00")

        assert credit_note.docstatus == 1

    def test_post_credit_note_not_found_raises_error(self, service, mock_db):
        """Test posting non-existent credit note raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_cn_query = MagicMock()
                mock_cn_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_cn_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_credit_note(credit_note_id=999, user_id=1)

        assert "Credit note not found" in str(exc_info.value)

    def test_post_credit_note_without_date_raises_error(self, service, mock_db):
        """Test posting credit note without date raises error."""
        cn = MockCreditNote(id=1, issue_date=None, posting_date=None, docstatus=0)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_cn_query = MagicMock()
                mock_cn_query.filter.return_value.first.return_value = cn
                mock_query.return_value = mock_cn_query

                with pytest.raises(PostingError) as exc_info:
                    service.post_credit_note(credit_note_id=1, user_id=1)

        assert "Posting date is required" in str(exc_info.value)


# =============================================================================
# REVERSE POSTING TESTS
# =============================================================================


class TestReversePosting:
    """Tests for reverse_posting method."""

    def test_reverse_posting_swaps_debits_credits(
        self, service, mock_db, posted_journal_entry
    ):
        """Test reversal swaps debits and credits."""
        original_gl_entries = [
            MockGLEntry(
                account="1100-Accounts Receivable",
                debit=Decimal("1000.00"),
                credit=Decimal("0"),
            ),
            MockGLEntry(
                account="4000-Revenue",
                debit=Decimal("0"),
                credit=Decimal("1000.00"),
            ),
        ]

        reversal_je = MockJournalEntry(id=2, erpnext_id="JE-00002")

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                # Mock JE query
                mock_je_query = MagicMock()
                mock_je_query.filter.return_value.first.return_value = posted_journal_entry

                # Mock GL entries query
                mock_gl_query = MagicMock()
                mock_gl_query.filter.return_value.all.return_value = original_gl_entries

                mock_query.side_effect = [mock_je_query, mock_gl_query]

                with patch.object(service, '_create_journal_entry', return_value=reversal_je) as mock_create_je:
                    result = service.reverse_posting(
                        journal_entry_id=1,
                        user_id=1,
                        reason="Error correction",
                    )

                    entries = mock_create_je.call_args[1]['entries']

                    # First entry: original debit becomes credit
                    assert entries[0]['debit'] == Decimal("0")
                    assert entries[0]['credit'] == Decimal("1000.00")

                    # Second entry: original credit becomes debit
                    assert entries[1]['debit'] == Decimal("1000.00")
                    assert entries[1]['credit'] == Decimal("0")

        # Original should be cancelled
        assert posted_journal_entry.docstatus == 2

    def test_reverse_posting_not_found_raises_error(self, service, mock_db):
        """Test reversing non-existent entry raises error."""
        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_je_query = MagicMock()
                mock_je_query.filter.return_value.first.return_value = None
                mock_query.return_value = mock_je_query

                with pytest.raises(PostingError) as exc_info:
                    service.reverse_posting(
                        journal_entry_id=999,
                        user_id=1,
                        reason="Test",
                    )

        assert "Journal entry not found" in str(exc_info.value)

    def test_reverse_unposted_entry_raises_error(self, service, mock_db):
        """Test reversing unposted entry raises error."""
        unposted_je = MockJournalEntry(id=1, docstatus=0)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_je_query = MagicMock()
                mock_je_query.filter.return_value.first.return_value = unposted_je
                mock_query.return_value = mock_je_query

                with pytest.raises(PostingError) as exc_info:
                    service.reverse_posting(
                        journal_entry_id=1,
                        user_id=1,
                        reason="Test",
                    )

        assert "only reverse posted entries" in str(exc_info.value)


# =============================================================================
# JOURNAL ENTRY CREATION TESTS
# =============================================================================


class TestCreateJournalEntry:
    """Tests for _create_journal_entry method."""

    def test_create_journal_entry_validates_balance(self, service, mock_db):
        """Test journal entry must be balanced."""
        unbalanced_entries = [
            {"account": "1100-AR", "debit": Decimal("1000.00"), "credit": Decimal("0")},
            {"account": "4000-Revenue", "debit": Decimal("0"), "credit": Decimal("900.00")},
            # Missing 100 - not balanced
        ]

        with pytest.raises(PostingError) as exc_info:
            service._create_journal_entry(
                voucher_type=MockJournalEntryType.JOURNAL_ENTRY,
                posting_date=datetime.now(timezone.utc),
                entries=unbalanced_entries,
            )

        assert "not balanced" in str(exc_info.value)

    def test_create_journal_entry_allows_small_difference(self, service, mock_db):
        """Test journal entry allows rounding difference <= 0.01."""
        entries = [
            {"account": "1100-AR", "debit": Decimal("100.00"), "credit": Decimal("0")},
            {"account": "4000-Revenue", "debit": Decimal("0"), "credit": Decimal("99.995")},
            # Difference is 0.005, which rounds to < 0.01
        ]

        # Should not raise - small difference is acceptable
        # Note: This test verifies the 0.01 tolerance
        try:
            service._create_journal_entry(
                voucher_type=MockJournalEntryType.JOURNAL_ENTRY,
                posting_date=datetime.now(timezone.utc),
                entries=entries,
            )
        except PostingError as e:
            if "not balanced" in str(e):
                pytest.fail("Should allow small rounding difference")

    def test_create_journal_entry_calculates_totals(self, service, mock_db):
        """Test journal entry calculates total debits and credits."""
        entries = [
            {"account": "1100-AR", "debit": Decimal("500.00"), "credit": Decimal("0")},
            {"account": "1100-AR", "debit": Decimal("500.00"), "credit": Decimal("0")},
            {"account": "4000-Revenue", "debit": Decimal("0"), "credit": Decimal("1000.00")},
        ]

        je = service._create_journal_entry(
            voucher_type=MockJournalEntryType.JOURNAL_ENTRY,
            posting_date=datetime.now(timezone.utc),
            entries=entries,
            company="Test Company",
        )

        assert je.total_debit == Decimal("1000.00")
        assert je.total_credit == Decimal("1000.00")
        assert je.company == "Test Company"


# =============================================================================
# FISCAL PERIOD VALIDATION TESTS
# =============================================================================


class TestValidateFiscalPeriod:
    """Tests for _validate_fiscal_period method."""

    def test_validate_open_period_passes(self, service, mock_db, open_period):
        """Test validation passes for open period."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_period_query = MagicMock()
            mock_period_query.filter.return_value.first.return_value = open_period
            mock_query.return_value = mock_period_query

            # Should not raise
            service._validate_fiscal_period(datetime(2024, 1, 15, tzinfo=timezone.utc))

    def test_validate_closed_period_raises_error(self, service, mock_db, closed_period):
        """Test validation raises for closed period."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_period_query = MagicMock()
            mock_period_query.filter.return_value.first.return_value = closed_period
            mock_query.return_value = mock_period_query

            with pytest.raises(PostingError) as exc_info:
                service._validate_fiscal_period(datetime(2023, 12, 15, tzinfo=timezone.utc))

        assert "not open" in str(exc_info.value)

    def test_validate_no_period_found_passes(self, service, mock_db):
        """Test validation passes when no period is defined."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_period_query = MagicMock()
            mock_period_query.filter.return_value.first.return_value = None
            mock_query.return_value = mock_period_query

            # Should not raise when no period is configured
            service._validate_fiscal_period(datetime(2024, 1, 15, tzinfo=timezone.utc))


# =============================================================================
# ACCOUNT RESOLUTION TESTS
# =============================================================================


class TestAccountResolution:
    """Tests for account resolution methods."""

    def test_get_ar_account_from_invoice(self, service, mock_account_resolver, invoice_unpaid):
        """Test AR account resolution from invoice."""
        account = service._get_ar_account(invoice_unpaid)
        assert account == "1100-Accounts Receivable"

    def test_get_ar_account_from_company(self, service, mock_account_resolver):
        """Test AR account resolution from company."""
        account = service._get_ar_account(None, company="Test Company")
        assert account == "1100-Accounts Receivable"

    def test_get_ap_account_from_bill(self, service, mock_account_resolver, bill_unpaid):
        """Test AP account resolution from bill."""
        account = service._get_ap_account(bill_unpaid)
        assert account == "2100-Accounts Payable"

    def test_get_revenue_account(self, service, mock_account_resolver, invoice_unpaid):
        """Test revenue account resolution."""
        account = service._get_revenue_account(invoice_unpaid)
        assert account == "4000-Revenue"

    def test_get_expense_account(self, service, mock_account_resolver, bill_unpaid):
        """Test expense account resolution."""
        account = service._get_expense_account(bill_unpaid)
        assert account == "5000-Expenses"

    def test_get_tax_liability_account(self, service, mock_account_resolver):
        """Test tax liability account resolution."""
        account = service._get_tax_liability_account()
        assert account == "2200-VAT Payable"

    def test_get_tax_asset_account(self, service, mock_account_resolver):
        """Test tax asset account resolution."""
        account = service._get_tax_asset_account()
        assert account == "1200-Input VAT"

    def test_get_bank_account(self, service, mock_account_resolver, payment_unposted):
        """Test bank account resolution."""
        account = service._get_bank_account_for_payment(payment_unposted, "Test Company")
        assert account == "1010-Bank Account"

    def test_get_sales_returns_account(self, service, mock_account_resolver):
        """Test sales returns account resolution."""
        account = service._get_sales_returns_account("Test Company")
        assert account == "4100-Sales Returns"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_post_invoice_zero_amount(self, service, mock_db):
        """Test posting zero amount invoice."""
        zero_invoice = MockInvoice(
            id=100,
            invoice_number="INV-ZERO",
            total_amount=Decimal("0.00"),
            amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            docstatus=0,
        )
        zero_invoice.customer_account_id = zero_invoice.customer_id

        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = zero_invoice
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_invoice(invoice_id=100, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    # Still creates entries with zero amounts
                    assert entries[0]['debit'] == Decimal("0.00")
                    assert entries[1]['credit'] == Decimal("0.00")

    def test_post_invoice_large_amounts(self, service, mock_db):
        """Test posting invoice with very large amounts."""
        large_invoice = MockInvoice(
            id=200,
            invoice_number="INV-LARGE",
            total_amount=Decimal("999999999999.99"),
            amount=Decimal("847457627118.63"),
            tax_amount=Decimal("152542372881.36"),
            docstatus=0,
        )
        large_invoice.customer_account_id = large_invoice.customer_id

        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = large_invoice
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je) as mock_create_je:
                    service.post_invoice(invoice_id=200, user_id=1)

                    entries = mock_create_je.call_args[1]['entries']
                    assert entries[0]['debit'] == Decimal("999999999999.99")

    def test_post_invoice_with_none_company(self, service, mock_db):
        """Test posting invoice with None company."""
        invoice = MockInvoice(
            id=300,
            total_amount=Decimal("100.00"),
            amount=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            company=None,
            docstatus=0,
        )
        invoice.customer_account_id = invoice.customer_id

        created_je = MockJournalEntry(id=1)

        with patch('app.services.document_posting.transactional_session'):
            with patch.object(mock_db, 'query') as mock_query:
                mock_inv_query = MagicMock()
                mock_inv_query.filter.return_value.first.return_value = invoice
                mock_period_query = MagicMock()
                mock_period_query.filter.return_value.first.return_value = None
                mock_query.side_effect = [mock_inv_query, mock_period_query]

                with patch.object(service, '_create_journal_entry', return_value=created_je):
                    service.post_invoice(invoice_id=300, user_id=1)

        assert invoice.docstatus == 1
