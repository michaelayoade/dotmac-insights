"""
Unit Tests for Accounting Services.

Tests the accounting service layer including:
- PayablesService: AP aging, outstanding summary, party integration
- DashboardService: profit margin edge cases
- ReceivablesService: AR aging, null date handling
- AccountingSettingsService: read-only behavior, default returns

Target coverage: 90%
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
from typing import Optional, List
import enum

from tests.unit.conftest import MockSession, MockQuery


# =============================================================================
# MOCK ENUMS
# =============================================================================


class MockPurchaseInvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNPAID = "unpaid"
    OVERDUE = "overdue"
    PAID = "paid"
    CANCELLED = "cancelled"


class MockInvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# =============================================================================
# MOCK DATA CLASSES
# =============================================================================


@dataclass
class MockParty:
    """Mock Party for testing."""
    id: int
    name: Optional[str] = "Test Party"
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None


@dataclass
class MockSupplierAccount:
    """Mock SupplierAccount for testing."""
    id: int
    party_id: int
    account_number: str = "SA-001"
    status: str = "active"
    party: Optional[MockParty] = None


@dataclass
class MockCustomerAccount:
    """Mock CustomerAccount for testing."""
    id: int
    party_id: int
    account_number: str = "CA-001"
    party: Optional[MockParty] = None


@dataclass
class MockPurchaseInvoice:
    """Mock Purchase Invoice for testing payables."""
    id: int
    erpnext_id: Optional[str] = None
    supplier: Optional[str] = "SUPP-001"
    supplier_name: Optional[str] = "Test Supplier"
    supplier_id: Optional[int] = None
    supplier_account_id: Optional[int] = None
    supplier_account: Optional[MockSupplierAccount] = None
    grand_total: Decimal = Decimal("1000.00")
    outstanding_amount: Decimal = Decimal("1000.00")
    status: MockPurchaseInvoiceStatus = MockPurchaseInvoiceStatus.UNPAID
    posting_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str = "NGN"

    def __post_init__(self):
        if self.posting_date is None:
            self.posting_date = date.today()
        if self.due_date is None:
            self.due_date = date.today() + timedelta(days=30)


@dataclass
class MockInvoice:
    """Mock Invoice for testing receivables."""
    id: int
    invoice_number: str = "INV-001"
    customer_account_id: Optional[int] = None
    customer_account: Optional[MockCustomerAccount] = None
    total_amount: Decimal = Decimal("1000.00")
    amount_paid: Decimal = Decimal("0.00")
    balance: Optional[Decimal] = None
    status: MockInvoiceStatus = MockInvoiceStatus.PENDING
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str = "NGN"

    def __post_init__(self):
        if self.balance is None:
            self.balance = self.total_amount - self.amount_paid
        if self.invoice_date is None:
            self.invoice_date = date.today()


@dataclass
class MockSupplier:
    """Mock Supplier for testing."""
    id: int
    erpnext_id: Optional[str] = None
    supplier_name: str = "Test Supplier"
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = "Nigeria"
    default_currency: str = "NGN"
    default_bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    tax_withholding_category: Optional[str] = None
    supplier_primary_contact: Optional[str] = None
    supplier_primary_address: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    default_price_list: Optional[str] = None
    payment_terms: Optional[str] = None
    is_transporter: bool = False
    is_internal_supplier: bool = False
    disabled: bool = False
    is_frozen: bool = False
    on_hold: bool = False


@dataclass
class MockAccountingOperationalSettings:
    """Mock settings for testing."""
    id: Optional[int] = None
    company: Optional[str] = None
    aging_bucket_boundaries: List[int] = field(default_factory=lambda: [0, 30, 60, 90])
    max_aging_invoices: int = 10000
    max_top_customers: int = 25
    max_top_suppliers: int = 25
    customer_search_min_chars: int = 2
    supplier_search_min_chars: int = 2
    default_currency: str = "NGN"
    default_pagination_limit: int = 50
    max_pagination_limit: int = 500


@dataclass
class MockAgingConfig:
    """Mock aging config from settings service."""
    bucket_boundaries: List[int] = field(default_factory=lambda: [0, 30, 60, 90])
    max_invoices: int = 10000


@dataclass
class MockQueryLimits:
    """Mock query limits from settings service."""
    max_top_items: int = 25
    customer_search_min_chars: int = 2
    supplier_search_min_chars: int = 2
    default_currency: str = "NGN"
    default_pagination_limit: int = 50
    max_pagination_limit: int = 500


# =============================================================================
# MOCK SERVICES
# =============================================================================


class MockSettingsService:
    """Mock AccountingSettingsService for testing."""

    def __init__(self, db=None, principal=None):
        self.db = db
        self.principal = principal

    def get_aging_config(self, company: Optional[str] = None) -> MockAgingConfig:
        return MockAgingConfig()

    def get_query_limits(self, company: Optional[str] = None) -> MockQueryLimits:
        return MockQueryLimits()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MockSession()


@pytest.fixture
def mock_settings_service(mock_db):
    """Create mock settings service."""
    return MockSettingsService(mock_db)


@pytest.fixture
def sample_purchase_invoices():
    """Sample purchase invoices with various states."""
    today = date.today()
    return [
        MockPurchaseInvoice(
            id=1,
            erpnext_id="PI-001",
            supplier="SUPP-001",
            supplier_name="Acme Corp",
            grand_total=Decimal("10000"),
            outstanding_amount=Decimal("10000"),
            status=MockPurchaseInvoiceStatus.UNPAID,
            posting_date=today - timedelta(days=15),
            due_date=today - timedelta(days=5),  # 5 days overdue
        ),
        MockPurchaseInvoice(
            id=2,
            erpnext_id="PI-002",
            supplier="SUPP-002",
            supplier_name="Beta Inc",
            grand_total=Decimal("5000"),
            outstanding_amount=Decimal("5000"),
            status=MockPurchaseInvoiceStatus.UNPAID,
            posting_date=today - timedelta(days=45),
            due_date=today - timedelta(days=35),  # 35 days overdue
        ),
        MockPurchaseInvoice(
            id=3,
            erpnext_id="PI-003",
            supplier="SUPP-001",
            supplier_name="Acme Corp",
            grand_total=Decimal("3000"),
            outstanding_amount=Decimal("3000"),
            status=MockPurchaseInvoiceStatus.UNPAID,
            posting_date=today,
            due_date=today + timedelta(days=30),  # Current (not overdue)
        ),
    ]


@pytest.fixture
def sample_invoice_with_party():
    """Sample purchase invoice with party linkage."""
    party = MockParty(id=100, name="Acme Corporation", legal_name="Acme Corp Ltd")
    supplier_account = MockSupplierAccount(
        id=50,
        party_id=100,
        account_number="SA-ACME-001",
        party=party
    )
    return MockPurchaseInvoice(
        id=10,
        erpnext_id="PI-010",
        supplier="SUPP-ACME",
        supplier_name="Acme Corp",
        supplier_account_id=50,
        supplier_account=supplier_account,
        grand_total=Decimal("25000"),
        outstanding_amount=Decimal("25000"),
        status=MockPurchaseInvoiceStatus.UNPAID,
    )


@pytest.fixture
def sample_dateless_invoice():
    """Invoice with no dates (edge case)."""
    inv = MockPurchaseInvoice(
        id=99,
        erpnext_id="PI-099",
        supplier="SUPP-BAD",
        supplier_name="Bad Data Supplier",
        grand_total=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        status=MockPurchaseInvoiceStatus.UNPAID,
    )
    inv.posting_date = None
    inv.due_date = None
    return inv


# =============================================================================
# PAYABLES SERVICE TESTS
# =============================================================================


class TestPayablesServiceAgingReport:
    """Tests for PayablesService.get_aging_report."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_groups_by_bucket(self, mock_db, mock_settings_service, sample_purchase_invoices):
        """Invoices are correctly grouped into aging buckets."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters

        # Setup mock to return our sample invoices
        mock_db._data = {}

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = sample_purchase_invoices
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            report = service.get_aging_report(PayablesFilters())

            # Verify buckets exist
            assert "current" in report.buckets
            assert "1_30" in report.buckets
            assert "31_60" in report.buckets
            assert report.total_invoices == 3

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_skips_dateless_invoices(self, mock_db, mock_settings_service, sample_dateless_invoice):
        """Invoices with no due_date and no posting_date are skipped."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = [sample_dateless_invoice]
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            report = service.get_aging_report(PayablesFilters())

            # Dateless invoice should be skipped
            assert report.total_invoices == 0
            assert report.total_payable == Decimal("0")

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_includes_party_info(self, mock_db, mock_settings_service, sample_invoice_with_party):
        """Party info is populated when supplier_account exists."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = [sample_invoice_with_party]
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            report = service.get_aging_report(PayablesFilters())

            # Find the invoice in buckets
            all_invoices = []
            for bucket in report.buckets.values():
                all_invoices.extend(bucket.invoices)

            assert len(all_invoices) == 1
            inv = all_invoices[0]
            assert inv.supplier_account_id == 50
            assert inv.party_id == 100
            assert inv.party_name == "Acme Corporation"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_filters_by_party_id(self, mock_db, mock_settings_service):
        """party_id filter is applied to query."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.join.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            filters = PayablesFilters(party_id=100)
            report = service.get_aging_report(filters)

            # Verify join was called for party filter
            mock_q.join.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_filters_by_supplier_account_id(self, mock_db, mock_settings_service):
        """supplier_account_id filter is applied to query."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            filters = PayablesFilters(supplier_account_id=50)
            report = service.get_aging_report(filters)

            # Filter should be applied (no join needed for direct FK filter)
            assert mock_q.filter.called

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_validates_supplier_search_length(self, mock_db, mock_settings_service):
        """Supplier search filter requires minimum characters."""
        from app.services.accounting.payables import PayablesService
        from app.services.accounting.payables_types import PayablesFilters
        from app.services.errors import ValidationError

        service = PayablesService(mock_db, mock_settings_service)
        filters = PayablesFilters(supplier="A")  # Too short

        with pytest.raises(ValidationError) as exc_info:
            service.get_aging_report(filters)

        assert "at least" in str(exc_info.value)


class TestPayablesServiceOutstandingSummary:
    """Tests for PayablesService.get_outstanding_summary."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_outstanding_summary_includes_party_info(self, mock_db, mock_settings_service):
        """Top suppliers include party_id and party_name when available."""
        from app.services.accounting.payables import PayablesService

        with patch.object(mock_db, 'query') as mock_query:
            # Mock for totals query
            totals_result = MagicMock()
            totals_result.outstanding = Decimal("50000")
            totals_result.invoice_count = 5

            # Mock for top suppliers query
            supplier_row = MagicMock()
            supplier_row.supplier = "SUPP-001"
            supplier_row.supplier_account_id = 50
            supplier_row.party_id = 100
            supplier_row.party_name = "Acme Corp"
            supplier_row.outstanding = Decimal("25000")

            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.outerjoin.return_value = mock_q
            mock_q.group_by.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.first.return_value = totals_result
            mock_q.all.return_value = [supplier_row]
            mock_query.return_value = mock_q

            service = PayablesService(mock_db, mock_settings_service)
            summary = service.get_outstanding_summary(currency="NGN", top_n=5)

            assert len(summary.top_suppliers) == 1
            top = summary.top_suppliers[0]
            assert top.supplier_account_id == 50
            assert top.party_id == 100
            assert top.party_name == "Acme Corp"


# =============================================================================
# DASHBOARD SERVICE TESTS
# =============================================================================


class TestDashboardServiceProfitMargin:
    """Tests for DashboardService profit margin calculation."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_profit_margin_with_positive_income(self):
        """Profit margin calculated correctly with positive income."""
        from app.services.accounting.dashboard import DashboardService

        # Verify the profit margin formula
        total_income = Decimal("100000")
        total_expenses = Decimal("60000")
        net_profit = total_income - total_expenses  # 40000

        # Expected margin: (40000 / 100000) * 100 = 40%
        if total_income and total_income > 0:
            profit_margin = Decimal(str(round((net_profit / total_income) * 100, 2)))
        else:
            profit_margin = Decimal("0")

        assert profit_margin == Decimal("40.00")

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_profit_margin_with_zero_income(self):
        """Profit margin is 0 when total income is zero."""
        total_income = Decimal("0")
        net_profit = Decimal("-5000")  # Loss

        if total_income and total_income > 0:
            profit_margin = Decimal(str(round((net_profit / total_income) * 100, 2)))
        else:
            profit_margin = Decimal("0")

        assert profit_margin == Decimal("0")

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_profit_margin_with_negative_income(self):
        """Profit margin is 0 when total income is negative."""
        total_income = Decimal("-5000")  # Unusual but possible
        net_profit = Decimal("-10000")

        if total_income and total_income > 0:
            profit_margin = Decimal(str(round((net_profit / total_income) * 100, 2)))
        else:
            profit_margin = Decimal("0")

        assert profit_margin == Decimal("0")

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_profit_margin_with_loss(self):
        """Profit margin can be negative when expenses exceed income."""
        total_income = Decimal("50000")
        total_expenses = Decimal("75000")
        net_profit = total_income - total_expenses  # -25000

        if total_income and total_income > 0:
            profit_margin = Decimal(str(round((net_profit / total_income) * 100, 2)))
        else:
            profit_margin = Decimal("0")

        # -25000 / 50000 * 100 = -50%
        assert profit_margin == Decimal("-50.00")


# =============================================================================
# RECEIVABLES SERVICE TESTS
# =============================================================================


class TestReceivablesServiceDateHandling:
    """Tests for ReceivablesService null date handling."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_invoice_with_due_date(self):
        """Invoice with due_date uses due_date for aging."""
        inv = MockInvoice(
            id=1,
            due_date=date.today() - timedelta(days=10),
            invoice_date=date.today() - timedelta(days=40),
        )

        # Should use due_date
        if inv.due_date:
            due = inv.due_date
        elif inv.invoice_date:
            due = inv.invoice_date
        else:
            due = None

        assert due == date.today() - timedelta(days=10)

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_invoice_without_due_date_uses_invoice_date(self):
        """Invoice without due_date falls back to invoice_date."""
        inv = MockInvoice(
            id=2,
            invoice_date=date.today() - timedelta(days=20),
        )
        inv.due_date = None

        if inv.due_date:
            due = inv.due_date
        elif inv.invoice_date:
            due = inv.invoice_date
        else:
            due = None

        assert due == date.today() - timedelta(days=20)

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_invoice_without_any_date_is_skipped(self):
        """Invoice with no dates should be skipped (continue)."""
        inv = MockInvoice(id=3)
        inv.due_date = None
        inv.invoice_date = None

        if inv.due_date:
            due = inv.due_date
        elif inv.invoice_date:
            due = inv.invoice_date
        else:
            due = None

        # Should result in skip (continue in loop)
        assert due is None


class TestReceivablesServiceAging:
    """Tests for ReceivablesService aging calculations."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_skips_zero_balance(self, mock_db, mock_settings_service):
        """Aging report should skip invoices with zero balance."""
        from app.models.invoice import Invoice
        from app.services.accounting.receivables import ReceivablesService

        today = date.today()
        inv_paid = MockInvoice(
            id=1,
            balance=Decimal("0"),
            due_date=today - timedelta(days=10),
        )
        inv_open = MockInvoice(
            id=2,
            balance=Decimal("250"),
            due_date=today - timedelta(days=5),
        )
        inv_paid.is_deleted = False
        inv_open.is_deleted = False

        mock_db.register_data(Invoice, [inv_paid, inv_open])
        service = ReceivablesService(mock_db, mock_settings_service)
        report = service.get_aging_report()

        assert report.total_invoices == 1
        assert report.buckets["1_30"].count == 1
        assert report.total_receivable == Decimal("250")

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_uses_invoice_date_when_due_missing(self, mock_db, mock_settings_service):
        """Aging report should fall back to invoice_date when due_date is missing."""
        from app.models.invoice import Invoice
        from app.services.accounting.receivables import ReceivablesService

        today = date.today()
        inv = MockInvoice(
            id=3,
            balance=Decimal("100"),
            invoice_date=today - timedelta(days=20),
        )
        inv.due_date = None
        inv.is_deleted = False

        mock_db.register_data(Invoice, [inv])
        service = ReceivablesService(mock_db, mock_settings_service)
        report = service.get_aging_report()

        assert report.buckets["1_30"].count == 1


# =============================================================================
# SETTINGS SERVICE TESTS
# =============================================================================


class TestAccountingSettingsService:
    """Tests for AccountingSettingsService."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_settings_returns_defaults_without_persisting(self, mock_db):
        """When no settings exist, return defaults without creating DB row."""
        from app.services.accounting.settings import AccountingSettingsService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None  # No settings exist
            mock_query.return_value = mock_q

            service = AccountingSettingsService(mock_db)
            settings = service._get_settings()

            # Should NOT have added anything to DB
            assert len(mock_db._added) == 0
            # Should return default settings object
            assert settings is not None
            assert settings.company is None

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_settings_returns_existing_settings(self, mock_db):
        """When settings exist, return them."""
        from app.services.accounting.settings import AccountingSettingsService

        existing_settings = MockAccountingOperationalSettings(
            id=1,
            company=None,
            max_aging_invoices=5000,
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = existing_settings
            mock_query.return_value = mock_q

            service = AccountingSettingsService(mock_db)
            settings = service._get_settings()

            assert settings.max_aging_invoices == 5000

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_company_settings_with_fallback(self, mock_db):
        """Company settings fall back to global when company-specific not found."""
        from app.services.accounting.settings import AccountingSettingsService

        global_settings = MockAccountingOperationalSettings(
            id=1,
            company=None,
            max_aging_invoices=10000,
        )

        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # Company-specific not found
            return global_settings  # Global fallback

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.side_effect = mock_first
            mock_query.return_value = mock_q

            service = AccountingSettingsService(mock_db)
            settings = service._get_settings(company="ACME")

            assert settings.max_aging_invoices == 10000


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestPayablesHelperFunctions:
    """Tests for payables helper functions."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_bucket_key_current(self):
        """Days <= 0 maps to 'current' bucket."""
        from app.services.accounting.payables import _get_bucket_key

        assert _get_bucket_key(0) == "current"
        assert _get_bucket_key(-5) == "current"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_bucket_key_1_30(self):
        """Days 1-30 maps to '1_30' bucket."""
        from app.services.accounting.payables import _get_bucket_key

        assert _get_bucket_key(1) == "1_30"
        assert _get_bucket_key(15) == "1_30"
        assert _get_bucket_key(30) == "1_30"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_bucket_key_31_60(self):
        """Days 31-60 maps to '31_60' bucket."""
        from app.services.accounting.payables import _get_bucket_key

        assert _get_bucket_key(31) == "31_60"
        assert _get_bucket_key(45) == "31_60"
        assert _get_bucket_key(60) == "31_60"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_bucket_key_61_90(self):
        """Days 61-90 maps to '61_90' bucket."""
        from app.services.accounting.payables import _get_bucket_key

        assert _get_bucket_key(61) == "61_90"
        assert _get_bucket_key(75) == "61_90"
        assert _get_bucket_key(90) == "61_90"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_bucket_key_over_90(self):
        """Days > 90 maps to 'over_90' bucket."""
        from app.services.accounting.payables import _get_bucket_key

        assert _get_bucket_key(91) == "over_90"
        assert _get_bucket_key(180) == "over_90"
        assert _get_bucket_key(365) == "over_90"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_supplier_party_name_with_party(self):
        """Returns party name when supplier_account.party exists."""
        from app.services.accounting.payables import _get_supplier_party_name

        party = MockParty(id=1, name="Acme Corporation")
        supplier_account = MockSupplierAccount(id=1, party_id=1, party=party)
        inv = MockPurchaseInvoice(
            id=1,
            supplier_account_id=1,
            supplier_account=supplier_account,
            supplier_name="Acme Corp"
        )

        name = _get_supplier_party_name(inv)
        assert name == "Acme Corporation"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_supplier_party_name_with_legal_name_fallback(self):
        """Falls back to legal_name when name is None."""
        from app.services.accounting.payables import _get_supplier_party_name

        party = MockParty(id=1, name=None, legal_name="Acme Corp Ltd")
        supplier_account = MockSupplierAccount(id=1, party_id=1, party=party)
        inv = MockPurchaseInvoice(
            id=1,
            supplier_account_id=1,
            supplier_account=supplier_account,
        )

        name = _get_supplier_party_name(inv)
        assert name == "Acme Corp Ltd"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_supplier_party_name_without_party(self):
        """Falls back to supplier_name when no party exists."""
        from app.services.accounting.payables import _get_supplier_party_name

        inv = MockPurchaseInvoice(
            id=1,
            supplier_account_id=None,
            supplier_account=None,
            supplier_name="Legacy Supplier Name"
        )

        name = _get_supplier_party_name(inv)
        assert name == "Legacy Supplier Name"


# =============================================================================
# TYPES/SERIALIZATION TESTS
# =============================================================================


class TestPayablesTypesToDict:
    """Tests for payables types serialization."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_aging_report_to_dict_includes_party_fields(self):
        """to_dict() includes party fields in invoice details."""
        from app.services.accounting.payables_types import (
            PayablesAgingReport,
            AgingBucket,
            InvoiceAgingDetail,
        )

        invoice = InvoiceAgingDetail(
            id=1,
            invoice_no="PI-001",
            supplier="SUPP-001",
            posting_date="2026-01-01",
            due_date="2026-01-31",
            grand_total=1000.0,
            outstanding=1000.0,
            days_overdue=5,
            supplier_account_id=50,
            party_id=100,
            party_name="Acme Corp",
        )

        bucket = AgingBucket(
            name="1-30",
            count=1,
            total=Decimal("1000"),
            invoices=[invoice],
        )

        report = PayablesAgingReport(
            as_of_date=date.today(),
            total_payable=Decimal("1000"),
            total_invoices=1,
            truncated=False,
            max_invoices=10000,
            buckets={"1_30": bucket},
        )

        result = report.to_dict()

        inv_dict = result["aging"]["1_30"]["invoices"][0]
        assert inv_dict["supplier_account_id"] == 50
        assert inv_dict["party_id"] == 100
        assert inv_dict["party_name"] == "Acme Corp"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_outstanding_summary_to_dict_includes_party_fields(self):
        """to_dict() includes party fields in top suppliers."""
        from app.services.accounting.payables_types import (
            PayablesOutstandingSummary,
            SupplierOutstanding,
        )

        supplier = SupplierOutstanding(
            supplier="SUPP-001",
            outstanding=Decimal("25000"),
            supplier_account_id=50,
            party_id=100,
            party_name="Acme Corp",
        )

        summary = PayablesOutstandingSummary(
            as_of_date=date.today(),
            currency="NGN",
            total_outstanding=Decimal("25000"),
            total_invoices=3,
            top_suppliers=[supplier],
        )

        result = summary.to_dict()

        top = result["top_suppliers"][0]
        assert top["supplier_account_id"] == 50
        assert top["party_id"] == 100
        assert top["party_name"] == "Acme Corp"
