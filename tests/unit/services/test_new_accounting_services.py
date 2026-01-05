"""
Unit Tests for New Accounting Services.

Tests the new accounting service layer including:
- PaymentTermsService: Payment terms templates and schedules
- PaymentModeService: Payment modes (cash, bank, etc.)
- CreditNoteService: AR credit notes
- DebitNoteService: AP debit notes
- DocumentAttachmentService: Document attachments
- ReportExportService: Report exports

Target coverage: 90%
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
from typing import Optional, List, Any
import enum
import os

from tests.unit.conftest import MockSession, MockQuery


# =============================================================================
# MOCK ENUMS
# =============================================================================


class MockCreditNoteStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class MockDebitNoteStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class MockPaymentModeType(str, enum.Enum):
    CASH = "cash"
    BANK = "bank"
    GENERAL = "general"


# =============================================================================
# MOCK DATA CLASSES
# =============================================================================


@dataclass
class MockPrincipal:
    """Mock Principal for testing."""
    id: int = 1
    company_id: Optional[int] = None


@dataclass
class MockPaymentTermsTemplate:
    """Mock PaymentTermsTemplate for testing."""
    id: int
    template_name: str = "Net 30"
    description: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True
    schedules: List["MockPaymentTermsSchedule"] = field(default_factory=list)
    created_by_id: Optional[int] = None


@dataclass
class MockPaymentTermsSchedule:
    """Mock PaymentTermsSchedule for testing."""
    id: int
    template_id: int
    credit_days: int = 30
    credit_months: int = 0
    day_of_month: Optional[int] = None
    payment_percentage: Decimal = Decimal("100")
    discount_percentage: Decimal = Decimal("0")
    discount_days: int = 0
    description: Optional[str] = None
    idx: int = 0


@dataclass
class MockModeOfPayment:
    """Mock ModeOfPayment for testing."""
    id: int
    mode_of_payment: str = "Cash"
    type: MockPaymentModeType = MockPaymentModeType.CASH
    enabled: bool = True


@dataclass
class MockCreditNote:
    """Mock CreditNote for testing."""
    id: int
    credit_number: str = "CN-001"
    customer_account_id: int = 1
    invoice_id: Optional[int] = None
    description: Optional[str] = None
    issue_date: Optional[date] = None
    posting_date: Optional[date] = None
    amount: Decimal = Decimal("1000.00")
    tax_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("1000.00")
    base_amount: Decimal = Decimal("1000.00")
    base_tax_amount: Decimal = Decimal("0.00")
    currency: str = "NGN"
    base_currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    status: MockCreditNoteStatus = MockCreditNoteStatus.DRAFT
    workflow_status: Optional[str] = "draft"
    docstatus: int = 0
    company: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    lines: List["MockCreditNoteLine"] = field(default_factory=list)

    def __post_init__(self):
        if self.issue_date is None:
            self.issue_date = date.today()
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class MockCreditNoteLine:
    """Mock CreditNoteLine for testing."""
    id: int
    credit_note_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal = Decimal("1")
    rate: Decimal = Decimal("1000.00")
    amount: Decimal = Decimal("1000.00")
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    account: Optional[str] = None
    cost_center: Optional[str] = None
    return_reason: Optional[str] = None
    idx: int = 0


@dataclass
class MockDebitNote:
    """Mock DebitNote for testing."""
    id: int
    debit_note_number: str = "DN-001"
    supplier_id: int = 1
    supplier_name: Optional[str] = "Test Supplier"
    purchase_invoice_id: Optional[int] = None
    remarks: Optional[str] = None
    posting_date: Optional[date] = None
    total_amount: Decimal = Decimal("1000.00")
    outstanding_amount: Decimal = Decimal("1000.00")
    base_amount: Decimal = Decimal("1000.00")
    currency: str = "NGN"
    base_currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    status: MockDebitNoteStatus = MockDebitNoteStatus.DRAFT
    workflow_status: Optional[str] = "draft"
    docstatus: int = 0
    company: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    lines: List["MockDebitNoteLine"] = field(default_factory=list)

    def __post_init__(self):
        if self.posting_date is None:
            self.posting_date = date.today()
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class MockDebitNoteLine:
    """Mock DebitNoteLine for testing."""
    id: int
    debit_note_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal = Decimal("1")
    rate: Decimal = Decimal("1000.00")
    amount: Decimal = Decimal("1000.00")
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    account: Optional[str] = None
    cost_center: Optional[str] = None
    return_reason: Optional[str] = None
    idx: int = 0


@dataclass
class MockDocumentAttachment:
    """Mock DocumentAttachment for testing."""
    id: int
    doctype: str = "invoice"
    document_id: int = 1
    file_name: str = "invoice.pdf"
    file_path: str = "/uploads/invoice/1/invoice.pdf"
    file_type: str = "application/pdf"
    file_size: int = 1024
    attachment_type: Optional[str] = None
    is_primary: bool = False
    description: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    uploaded_by_id: Optional[int] = None

    def __post_init__(self):
        if self.uploaded_at is None:
            self.uploaded_at = datetime.now(timezone.utc)


@dataclass
class MockAccountingControl:
    """Mock AccountingControl for testing."""
    id: int = 1
    require_attachment_supplier_payment: bool = False
    require_attachment_journal_entry: bool = False
    require_attachment_purchase_invoice: bool = True


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MockSession()


@pytest.fixture
def mock_principal():
    """Create mock principal."""
    return MockPrincipal(id=1)


@pytest.fixture
def sample_payment_terms():
    """Sample payment terms template."""
    template = MockPaymentTermsTemplate(
        id=1,
        template_name="Net 30",
        description="Payment due in 30 days",
        is_active=True,
    )
    template.schedules = [
        MockPaymentTermsSchedule(
            id=1,
            template_id=1,
            credit_days=30,
            payment_percentage=Decimal("100"),
            idx=0,
        )
    ]
    return template


@pytest.fixture
def sample_split_payment_terms():
    """Sample payment terms with split payments."""
    template = MockPaymentTermsTemplate(
        id=2,
        template_name="50/50 Split",
        description="50% upfront, 50% in 30 days",
    )
    template.schedules = [
        MockPaymentTermsSchedule(
            id=2,
            template_id=2,
            credit_days=0,
            payment_percentage=Decimal("50"),
            idx=0,
        ),
        MockPaymentTermsSchedule(
            id=3,
            template_id=2,
            credit_days=30,
            payment_percentage=Decimal("50"),
            idx=1,
        ),
    ]
    return template


@pytest.fixture
def sample_payment_mode():
    """Sample payment mode."""
    return MockModeOfPayment(
        id=1,
        mode_of_payment="Cash",
        type=MockPaymentModeType.CASH,
        enabled=True,
    )


@pytest.fixture
def sample_credit_note():
    """Sample credit note."""
    note = MockCreditNote(
        id=1,
        credit_number="CN-001",
        customer_account_id=1,
        amount=Decimal("1000.00"),
        status=MockCreditNoteStatus.DRAFT,
    )
    note.lines = [
        MockCreditNoteLine(
            id=1,
            credit_note_id=1,
            item_name="Return Item",
            amount=Decimal("1000.00"),
        )
    ]
    return note


@pytest.fixture
def sample_issued_credit_note():
    """Sample issued credit note."""
    return MockCreditNote(
        id=2,
        credit_number="CN-002",
        customer_account_id=1,
        status=MockCreditNoteStatus.ISSUED,
        docstatus=1,
    )


@pytest.fixture
def sample_debit_note():
    """Sample debit note."""
    note = MockDebitNote(
        id=1,
        debit_note_number="DN-001",
        supplier_id=1,
        supplier_name="Test Supplier",
        total_amount=Decimal("500.00"),
        outstanding_amount=Decimal("500.00"),
        status=MockDebitNoteStatus.DRAFT,
    )
    note.lines = [
        MockDebitNoteLine(
            id=1,
            debit_note_id=1,
            item_name="Returned Item",
            amount=Decimal("500.00"),
        )
    ]
    return note


@pytest.fixture
def sample_attachment():
    """Sample document attachment."""
    return MockDocumentAttachment(
        id=1,
        doctype="invoice",
        document_id=1,
        file_name="invoice_001.pdf",
        file_path="/uploads/invoice/1/abc123_invoice_001.pdf",
        file_size=2048,
        is_primary=True,
    )


# =============================================================================
# PAYMENT TERMS SERVICE TESTS
# =============================================================================


class TestPaymentTermsServiceList:
    """Tests for PaymentTermsService.list_payment_terms."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_returns_paginated_result(self, mock_db, mock_principal, sample_payment_terms):
        """List returns PaginatedResult with items and total."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsFilters
        from app.services.types import PaginationParams

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = [sample_payment_terms]
            mock_q.count.return_value = 1
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            result = service.list_payment_terms(
                PaymentTermsFilters(),
                PaginationParams(limit=10, offset=0),
            )

            assert result.total == 1
            assert len(result.items) == 1

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_filters_by_active(self, mock_db, mock_principal):
        """Active filter is applied to query."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            service.list_payment_terms(PaymentTermsFilters(is_active=True))

            # Verify filter was called
            assert mock_q.filter.called

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_filters_by_search(self, mock_db, mock_principal):
        """Search filter uses ILIKE pattern."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            service.list_payment_terms(PaymentTermsFilters(search="Net"))

            assert mock_q.filter.called


class TestPaymentTermsServiceGet:
    """Tests for PaymentTermsService.get_payment_terms."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_returns_terms(self, mock_db, mock_principal, sample_payment_terms):
        """Get returns payment terms when found."""
        from app.services.accounting.payment_terms import PaymentTermsService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_terms
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            result = service.get_payment_terms(1)

            assert result.id == 1
            assert result.template_name == "Net 30"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_raises_not_found(self, mock_db, mock_principal):
        """Get raises NotFoundError when not found."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.errors import NotFoundError

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)

            with pytest.raises(NotFoundError) as exc_info:
                service.get_payment_terms(999)

            assert "999" in str(exc_info.value)


class TestPaymentTermsServiceValidation:
    """Tests for PaymentTermsService schedule validation."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_schedules_sum_to_100(self, mock_db, mock_principal):
        """Schedules summing to 100% pass validation."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import ScheduleData

        service = PaymentTermsService(mock_db, mock_principal)
        schedules = [
            ScheduleData(credit_days=0, payment_percentage=Decimal("50")),
            ScheduleData(credit_days=30, payment_percentage=Decimal("50")),
        ]

        # Should not raise
        service.validate_schedules(schedules)

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_schedules_rejects_not_100(self, mock_db, mock_principal):
        """Schedules not summing to 100% raise ValidationError."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import ScheduleData
        from app.services.errors import ValidationError

        service = PaymentTermsService(mock_db, mock_principal)
        schedules = [
            ScheduleData(credit_days=0, payment_percentage=Decimal("50")),
            ScheduleData(credit_days=30, payment_percentage=Decimal("40")),
        ]

        with pytest.raises(ValidationError) as exc_info:
            service.validate_schedules(schedules)

        assert "100%" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_schedules_allows_empty(self, mock_db, mock_principal):
        """Empty schedules pass validation."""
        from app.services.accounting.payment_terms import PaymentTermsService

        service = PaymentTermsService(mock_db, mock_principal)

        # Should not raise
        service.validate_schedules([])

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_schedules_tolerance(self, mock_db, mock_principal):
        """Schedules within 0.01% tolerance pass."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import ScheduleData

        service = PaymentTermsService(mock_db, mock_principal)
        schedules = [
            ScheduleData(credit_days=0, payment_percentage=Decimal("33.33")),
            ScheduleData(credit_days=30, payment_percentage=Decimal("33.33")),
            ScheduleData(credit_days=60, payment_percentage=Decimal("33.34")),
        ]

        # Should not raise (100.00)
        service.validate_schedules(schedules)


class TestPaymentTermsServiceCreate:
    """Tests for PaymentTermsService.create_payment_terms."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_success(self, mock_db, mock_principal):
        """Create payment terms successfully."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsCreateData, ScheduleData

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None  # No duplicate
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            data = PaymentTermsCreateData(
                template_name="Net 45",
                description="45 days",
                schedules=[
                    ScheduleData(credit_days=45, payment_percentage=Decimal("100")),
                ],
            )
            result = service.create_payment_terms(data)

            assert len(mock_db._added) > 0

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_duplicate(self, mock_db, mock_principal, sample_payment_terms):
        """Create rejects duplicate template name."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsCreateData
        from app.services.errors import ValidationError

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_terms  # Duplicate exists
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            data = PaymentTermsCreateData(
                template_name="Net 30",
                schedules=[],
            )

            with pytest.raises(ValidationError) as exc_info:
                service.create_payment_terms(data)

            assert "already exists" in str(exc_info.value)


class TestPaymentTermsServiceUpdate:
    """Tests for PaymentTermsService.update_payment_terms."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_update_success(self, mock_db, mock_principal, sample_payment_terms):
        """Update payment terms successfully."""
        from app.services.accounting.payment_terms import PaymentTermsService
        from app.services.accounting.payment_terms_types import PaymentTermsUpdateData

        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return sample_payment_terms  # Get by ID
            return None  # No duplicate

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.side_effect = mock_first
            mock_q.delete.return_value = None
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            data = PaymentTermsUpdateData(
                description="Updated description",
            )
            result = service.update_payment_terms(1, data)

            assert result.description == "Updated description"


class TestPaymentTermsServiceDelete:
    """Tests for PaymentTermsService.delete_payment_terms."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_delete_success(self, mock_db, mock_principal, sample_payment_terms):
        """Delete payment terms successfully."""
        from app.services.accounting.payment_terms import PaymentTermsService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_terms
            mock_query.return_value = mock_q

            service = PaymentTermsService(mock_db, mock_principal)
            service.delete_payment_terms(1)

            assert sample_payment_terms in mock_db._deleted


# =============================================================================
# PAYMENT MODE SERVICE TESTS
# =============================================================================


class TestPaymentModeServiceList:
    """Tests for PaymentModeService.list_payment_modes."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_excludes_disabled_by_default(self, mock_db, mock_principal):
        """List excludes disabled modes by default."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.services.accounting.payment_modes_types import PaymentModeFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            service.list_payment_modes(PaymentModeFilters(include_disabled=False))

            # Verify enabled filter was applied
            assert mock_q.filter.called

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_includes_disabled_when_requested(self, mock_db, mock_principal):
        """List includes disabled modes when include_disabled=True."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.services.accounting.payment_modes_types import PaymentModeFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            service.list_payment_modes(PaymentModeFilters(include_disabled=True))

            # Filter still called for other reasons but not enabled
            assert mock_q.order_by.called


class TestPaymentModeServiceValidation:
    """Tests for PaymentModeService validation."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_mode_type_success(self, mock_db, mock_principal):
        """Valid mode type strings are accepted."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.models.accounting import PaymentModeType

        service = PaymentModeService(mock_db, mock_principal)

        result = service.validate_mode_type("cash")
        assert result == PaymentModeType.CASH

        result = service.validate_mode_type("BANK")
        assert result == PaymentModeType.BANK

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_mode_type_invalid(self, mock_db, mock_principal):
        """Invalid mode type raises ValidationError."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.services.errors import ValidationError

        service = PaymentModeService(mock_db, mock_principal)

        with pytest.raises(ValidationError) as exc_info:
            service.validate_mode_type("invalid_type")

        assert "Invalid payment mode type" in str(exc_info.value)


class TestPaymentModeServiceCreate:
    """Tests for PaymentModeService.create_payment_mode."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_success(self, mock_db, mock_principal):
        """Create payment mode successfully."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.services.accounting.payment_modes_types import PaymentModeCreateData
        from app.models.accounting import PaymentModeType

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None  # No duplicate
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            data = PaymentModeCreateData(
                mode_of_payment="Wire Transfer",
                mode_type=PaymentModeType.BANK,
            )
            service.create_payment_mode(data)

            assert len(mock_db._added) > 0

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_duplicate(self, mock_db, mock_principal, sample_payment_mode):
        """Create rejects duplicate mode name."""
        from app.services.accounting.payment_modes import PaymentModeService
        from app.services.accounting.payment_modes_types import PaymentModeCreateData
        from app.services.errors import ValidationError
        from app.models.accounting import PaymentModeType

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_mode
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            data = PaymentModeCreateData(
                mode_of_payment="Cash",
                mode_type=PaymentModeType.CASH,
            )

            with pytest.raises(ValidationError) as exc_info:
                service.create_payment_mode(data)

            assert "already exists" in str(exc_info.value)


class TestPaymentModeServiceDisable:
    """Tests for PaymentModeService enable/disable."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_disable_success(self, mock_db, mock_principal, sample_payment_mode):
        """Disable payment mode sets enabled=False."""
        from app.services.accounting.payment_modes import PaymentModeService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_mode
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            result = service.disable_payment_mode(1)

            assert result.enabled is False

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_enable_success(self, mock_db, mock_principal, sample_payment_mode):
        """Enable payment mode sets enabled=True."""
        from app.services.accounting.payment_modes import PaymentModeService

        sample_payment_mode.enabled = False

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_payment_mode
            mock_query.return_value = mock_q

            service = PaymentModeService(mock_db, mock_principal)
            result = service.enable_payment_mode(1)

            assert result.enabled is True


# =============================================================================
# CREDIT NOTE SERVICE TESTS
# =============================================================================


class TestCreditNoteServiceList:
    """Tests for CreditNoteService.list_credit_notes."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_filters_by_customer(self, mock_db, mock_principal):
        """List filters by customer_account_id."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.accounting.credit_notes_types import CreditNoteFilters

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            service.list_credit_notes(CreditNoteFilters(customer_account_id=1))

            assert mock_q.filter.called

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_filters_by_status(self, mock_db, mock_principal):
        """List filters by status."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.accounting.credit_notes_types import CreditNoteFilters
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.offset.return_value = mock_q
            mock_q.limit.return_value = mock_q
            mock_q.all.return_value = []
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            service.list_credit_notes(CreditNoteFilters(status=CreditNoteStatus.DRAFT))

            assert mock_q.filter.called


class TestCreditNoteServiceCreate:
    """Tests for CreditNoteService.create_credit_note."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_success(self, mock_db, mock_principal):
        """Create credit note successfully."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.accounting.credit_notes_types import CreditNoteCreateData, CreditNoteLineData

        with patch('app.services.accounting.credit_notes.generate_voucher_number') as mock_gen:
            mock_gen.return_value = "CN-001"

            service = CreditNoteService(mock_db, mock_principal)
            data = CreditNoteCreateData(
                customer_account_id=1,
                issue_date=datetime.now(timezone.utc),
                currency="NGN",
                conversion_rate=Decimal("1"),
                lines=[
                    CreditNoteLineData(
                        item_name="Return",
                        quantity=Decimal("1"),
                        rate=Decimal("1000"),
                        amount=Decimal("1000"),
                        tax_rate=Decimal("0"),
                        tax_amount=Decimal("0"),
                    ),
                ],
            )
            service.create_credit_note(data)

            assert len(mock_db._added) > 0

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_zero_conversion_rate(self, mock_db, mock_principal):
        """Create rejects zero conversion rate."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.accounting.credit_notes_types import CreditNoteCreateData
        from app.services.errors import ValidationError

        service = CreditNoteService(mock_db, mock_principal)
        data = CreditNoteCreateData(
            customer_account_id=1,
            issue_date=datetime.now(timezone.utc),
            currency="NGN",
            conversion_rate=Decimal("0"),
            lines=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            service.create_credit_note(data)

        assert "positive" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_missing_customer(self, mock_db, mock_principal):
        """Create requires customer_account_id."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.accounting.credit_notes_types import CreditNoteCreateData
        from app.services.errors import ValidationError

        service = CreditNoteService(mock_db, mock_principal)
        data = CreditNoteCreateData(
            customer_account_id=None,
            issue_date=datetime.now(timezone.utc),
            currency="NGN",
            conversion_rate=Decimal("1"),
            lines=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            service.create_credit_note(data)

        assert "customer_account_id" in str(exc_info.value)


class TestCreditNoteServiceWorkflow:
    """Tests for CreditNoteService workflow transitions."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_submit_success(self, mock_db, mock_principal, sample_credit_note):
        """Submit draft credit note to issued."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_credit_note
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            # Need to set correct status type for comparison
            sample_credit_note.status = CreditNoteStatus.DRAFT
            result = service.submit_credit_note(1)

            assert result.status == CreditNoteStatus.ISSUED
            assert result.docstatus == 1

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_submit_rejects_non_draft(self, mock_db, mock_principal, sample_issued_credit_note):
        """Submit rejects non-draft credit note."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.errors import ValidationError
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            sample_issued_credit_note.status = CreditNoteStatus.ISSUED
            mock_q.first.return_value = sample_issued_credit_note
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)

            with pytest.raises(ValidationError) as exc_info:
                service.submit_credit_note(2)

            assert "draft" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_cancel_success(self, mock_db, mock_principal, sample_issued_credit_note):
        """Cancel issued credit note."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            sample_issued_credit_note.status = CreditNoteStatus.ISSUED
            mock_q.first.return_value = sample_issued_credit_note
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            result = service.cancel_credit_note(2)

            assert result.status == CreditNoteStatus.CANCELLED
            assert result.docstatus == 2

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_cancel_rejects_applied(self, mock_db, mock_principal, sample_issued_credit_note):
        """Cancel rejects applied credit note."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.services.errors import ValidationError
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            sample_issued_credit_note.status = CreditNoteStatus.APPLIED
            mock_q.first.return_value = sample_issued_credit_note
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)

            with pytest.raises(ValidationError) as exc_info:
                service.cancel_credit_note(2)

            assert "applied" in str(exc_info.value).lower()


class TestCreditNoteServiceStats:
    """Tests for CreditNoteService.get_credit_note_stats."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_stats_includes_all_statuses(self, mock_db, mock_principal):
        """Stats returns counts for all statuses."""
        from app.services.accounting.credit_notes import CreditNoteService
        from app.models.credit_note import CreditNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.with_entities.return_value = mock_q
            mock_q.group_by.return_value = mock_q
            mock_q.all.return_value = [
                (CreditNoteStatus.DRAFT, 5),
                (CreditNoteStatus.ISSUED, 10),
            ]
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            stats = service.get_credit_note_stats()

            assert stats["draft"] == 5
            assert stats["issued"] == 10
            assert stats["total"] == 15

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_stats_uses_scoped_query(self, mock_db, mock_principal):
        """Stats applies tenant scoping."""
        from app.services.accounting.credit_notes import CreditNoteService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.with_entities.return_value = mock_q
            mock_q.group_by.return_value = mock_q
            mock_q.all.return_value = []
            mock_query.return_value = mock_q

            service = CreditNoteService(mock_db, mock_principal)
            service.get_credit_note_stats()

            # scoped_query applies filter
            assert mock_query.called


# =============================================================================
# DEBIT NOTE SERVICE TESTS
# =============================================================================


class TestDebitNoteServiceCreate:
    """Tests for DebitNoteService.create_debit_note."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_success(self, mock_db, mock_principal):
        """Create debit note successfully."""
        from app.services.accounting.debit_notes import DebitNoteService
        from app.services.accounting.debit_notes_types import DebitNoteCreateData, DebitNoteLineData

        with patch('app.services.accounting.debit_notes.generate_voucher_number') as mock_gen:
            mock_gen.return_value = "DN-001"

            service = DebitNoteService(mock_db, mock_principal)
            data = DebitNoteCreateData(
                supplier_id=1,
                supplier_name="Test Supplier",
                issue_date=datetime.now(timezone.utc),
                currency="NGN",
                conversion_rate=Decimal("1"),
                lines=[
                    DebitNoteLineData(
                        item_name="Return",
                        quantity=Decimal("1"),
                        rate=Decimal("500"),
                        amount=Decimal("500"),
                        tax_rate=Decimal("0"),
                        tax_amount=Decimal("0"),
                    ),
                ],
            )
            service.create_debit_note(data)

            assert len(mock_db._added) > 0

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_zero_conversion_rate(self, mock_db, mock_principal):
        """Create rejects zero conversion rate."""
        from app.services.accounting.debit_notes import DebitNoteService
        from app.services.accounting.debit_notes_types import DebitNoteCreateData
        from app.services.errors import ValidationError

        service = DebitNoteService(mock_db, mock_principal)
        data = DebitNoteCreateData(
            supplier_id=1,
            issue_date=datetime.now(timezone.utc),
            currency="NGN",
            conversion_rate=Decimal("0"),
            lines=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            service.create_debit_note(data)

        assert "positive" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_create_rejects_missing_supplier(self, mock_db, mock_principal):
        """Create requires supplier_id."""
        from app.services.accounting.debit_notes import DebitNoteService
        from app.services.accounting.debit_notes_types import DebitNoteCreateData
        from app.services.errors import ValidationError

        service = DebitNoteService(mock_db, mock_principal)
        data = DebitNoteCreateData(
            supplier_id=None,
            issue_date=datetime.now(timezone.utc),
            currency="NGN",
            conversion_rate=Decimal("1"),
            lines=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            service.create_debit_note(data)

        assert "supplier_id" in str(exc_info.value)


class TestDebitNoteServiceWorkflow:
    """Tests for DebitNoteService workflow transitions."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_submit_success(self, mock_db, mock_principal, sample_debit_note):
        """Submit draft debit note to issued."""
        from app.services.accounting.debit_notes import DebitNoteService
        from app.models.books_settings import DebitNoteStatus

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            sample_debit_note.status = DebitNoteStatus.DRAFT
            mock_q.first.return_value = sample_debit_note
            mock_query.return_value = mock_q

            service = DebitNoteService(mock_db, mock_principal)
            result = service.submit_debit_note(1)

            assert result.status == DebitNoteStatus.ISSUED
            assert result.docstatus == 1


class TestDebitNoteServiceStats:
    """Tests for DebitNoteService.get_debit_note_stats."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_stats_uses_scoped_query(self, mock_db, mock_principal):
        """Stats applies tenant scoping."""
        from app.services.accounting.debit_notes import DebitNoteService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.with_entities.return_value = mock_q
            mock_q.group_by.return_value = mock_q
            mock_q.all.return_value = []
            mock_query.return_value = mock_q

            service = DebitNoteService(mock_db, mock_principal)
            service.get_debit_note_stats()

            assert mock_query.called


# =============================================================================
# DOCUMENT ATTACHMENT SERVICE TESTS
# =============================================================================


class TestDocumentAttachmentServiceValidation:
    """Tests for DocumentAttachmentService file validation."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_file_success(self, mock_db, mock_principal):
        """Valid file passes validation."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.validate_file("invoice.pdf", 1024 * 1024)

        assert result.is_valid is True
        assert result.file_extension == ".pdf"
        assert result.sanitized_filename is not None

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_file_rejects_invalid_extension(self, mock_db, mock_principal):
        """Invalid file extension fails validation."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.validate_file("malware.exe", 1024)

        assert result.is_valid is False
        assert "not allowed" in result.error

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_file_rejects_oversized(self, mock_db, mock_principal):
        """Oversized file fails validation."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.validate_file("large.pdf", 20 * 1024 * 1024)  # 20MB

        assert result.is_valid is False
        assert "too large" in result.error.lower()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_file_rejects_empty_name(self, mock_db, mock_principal):
        """Empty filename fails validation."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.validate_file("", 1024)

        assert result.is_valid is False
        assert "required" in result.error.lower()


class TestDocumentAttachmentServiceSanitize:
    """Tests for DocumentAttachmentService filename sanitization."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_sanitize_removes_path_components(self, mock_db, mock_principal):
        """Sanitize removes path traversal attempts."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.sanitize_filename("../../../etc/passwd")

        assert ".." not in result
        assert "/" not in result

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_sanitize_removes_special_chars(self, mock_db, mock_principal):
        """Sanitize removes special characters."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.sanitize_filename("file<>:name.pdf")

        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_sanitize_prevents_double_extension(self, mock_db, mock_principal):
        """Sanitize prevents double extensions like .pdf.exe."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result = service.sanitize_filename("invoice.pdf.exe")

        # Should only have one dot before extension
        parts = result.split("_", 1)[1]  # Remove unique prefix
        assert parts.count(".") == 1

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_sanitize_adds_unique_prefix(self, mock_db, mock_principal):
        """Sanitize adds unique prefix."""
        from app.services.accounting.attachments import DocumentAttachmentService

        service = DocumentAttachmentService(mock_db, mock_principal)
        result1 = service.sanitize_filename("invoice.pdf")
        result2 = service.sanitize_filename("invoice.pdf")

        assert result1 != result2


class TestDocumentAttachmentServiceCRUD:
    """Tests for DocumentAttachmentService CRUD operations."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_list_attachments(self, mock_db, mock_principal, sample_attachment):
        """List returns attachments for document."""
        from app.services.accounting.attachments import DocumentAttachmentService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.all.return_value = [sample_attachment]
            mock_query.return_value = mock_q

            service = DocumentAttachmentService(mock_db, mock_principal)
            result = service.list_attachments("invoice", 1)

            assert len(result) == 1

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_attachment_not_found(self, mock_db, mock_principal):
        """Get raises NotFoundError when not found."""
        from app.services.accounting.attachments import DocumentAttachmentService
        from app.services.errors import NotFoundError

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None
            mock_query.return_value = mock_q

            service = DocumentAttachmentService(mock_db, mock_principal)

            with pytest.raises(NotFoundError):
                service.get_attachment(999)

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_set_primary_unsets_others(self, mock_db, mock_principal, sample_attachment):
        """Set primary unsets other primary attachments."""
        from app.services.accounting.attachments import DocumentAttachmentService

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = sample_attachment
            mock_q.update.return_value = None
            mock_query.return_value = mock_q

            service = DocumentAttachmentService(mock_db, mock_principal)
            result = service.set_primary(1)

            assert result.is_primary is True
            # Update was called to unset others
            assert mock_q.update.called


class TestDocumentAttachmentServiceRequirements:
    """Tests for DocumentAttachmentService requirement checking."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_check_requirements_met(self, mock_db, mock_principal, sample_attachment):
        """Requirement is met when attachment exists."""
        from app.services.accounting.attachments import DocumentAttachmentService

        control = MockAccountingControl(require_attachment_purchase_invoice=True)

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.first.return_value = control
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 1
            mock_query.return_value = mock_q

            service = DocumentAttachmentService(mock_db, mock_principal)
            result = service.check_requirements("purchase_invoice", 1)

            assert result.requirement_met is True
            assert result.has_attachment is True

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_check_requirements_not_met(self, mock_db, mock_principal):
        """Requirement is not met when attachment missing."""
        from app.services.accounting.attachments import DocumentAttachmentService

        control = MockAccountingControl(require_attachment_purchase_invoice=True)

        with patch.object(mock_db, 'query') as mock_query:
            mock_q = MagicMock()
            mock_q.first.return_value = control
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 0
            mock_query.return_value = mock_q

            service = DocumentAttachmentService(mock_db, mock_principal)
            result = service.check_requirements("purchase_invoice", 1)

            assert result.requirement_met is False
            assert result.has_attachment is False


# =============================================================================
# REPORT EXPORT SERVICE TESTS
# =============================================================================


class TestReportExportServiceValidation:
    """Tests for ReportExportService format validation."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_format_csv(self, mock_db, mock_principal):
        """CSV format is accepted."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        service = ReportExportService(mock_db, mock_principal)
        result = service.validate_format("csv")

        assert result == ExportFormat.CSV

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_format_pdf(self, mock_db, mock_principal):
        """PDF format is accepted."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        service = ReportExportService(mock_db, mock_principal)
        result = service.validate_format("PDF")

        assert result == ExportFormat.PDF

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_validate_format_invalid(self, mock_db, mock_principal):
        """Invalid format raises ValidationError."""
        from app.services.accounting.exports import ReportExportService
        from app.services.errors import ValidationError

        service = ReportExportService(mock_db, mock_principal)

        with pytest.raises(ValidationError) as exc_info:
            service.validate_format("xlsx")

        assert "Invalid export format" in str(exc_info.value)


class TestReportExportServiceStatus:
    """Tests for ReportExportService status checking."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_export_status(self, mock_db, mock_principal):
        """Get export status returns availability."""
        from app.services.accounting.exports import ReportExportService

        with patch('app.services.accounting.exports.WEASYPRINT_AVAILABLE', True):
            service = ReportExportService(mock_db, mock_principal)
            status = service.get_export_status()

            assert status.csv_available is True
            assert status.pdf_available is True

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_is_pdf_available_false(self, mock_db, mock_principal):
        """PDF not available when weasyprint missing."""
        from app.services.accounting.exports import ReportExportService

        with patch('app.services.accounting.exports.WEASYPRINT_AVAILABLE', False):
            service = ReportExportService(mock_db, mock_principal)
            result = service.is_pdf_available()

            assert result is False


class TestReportExportServiceExport:
    """Tests for ReportExportService export operations."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_export_to_csv(self, mock_db, mock_principal):
        """Export to CSV calls ExportService."""
        from app.services.accounting.exports import ReportExportService

        with patch('app.services.accounting.exports.ExportService') as MockExportService:
            mock_export = MagicMock()
            mock_export.export_csv.return_value = b"col1,col2\nval1,val2"
            MockExportService.return_value = mock_export

            service = ReportExportService(mock_db, mock_principal)
            result = service.export_to_csv({"data": []}, "trial_balance")

            assert result == b"col1,col2\nval1,val2"
            mock_export.export_csv.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_export_to_pdf_not_available(self, mock_db, mock_principal):
        """Export to PDF fails when not available."""
        from app.services.accounting.exports import ReportExportService
        from app.services.errors import ValidationError

        with patch('app.services.accounting.exports.WEASYPRINT_AVAILABLE', False):
            service = ReportExportService(mock_db, mock_principal)

            with pytest.raises(ValidationError) as exc_info:
                service.export_to_pdf({"data": []}, "balance_sheet")

            assert "not available" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_content_type_csv(self, mock_db, mock_principal):
        """CSV content type is text/csv."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        service = ReportExportService(mock_db, mock_principal)
        result = service.get_content_type(ExportFormat.CSV)

        assert result == "text/csv"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_content_type_pdf(self, mock_db, mock_principal):
        """PDF content type is application/pdf."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        service = ReportExportService(mock_db, mock_principal)
        result = service.get_content_type(ExportFormat.PDF)

        assert result == "application/pdf"

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_get_file_extension(self, mock_db, mock_principal):
        """File extension matches format."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        service = ReportExportService(mock_db, mock_principal)

        assert service.get_file_extension(ExportFormat.CSV) == "csv"
        assert service.get_file_extension(ExportFormat.PDF) == "pdf"


class TestReportExportServiceAuditLogging:
    """Tests for ReportExportService audit logging."""

    @pytest.mark.unit
    @pytest.mark.accounting
    def test_log_export(self, mock_db, mock_principal):
        """Log export creates audit entry."""
        from app.services.accounting.exports import ReportExportService
        from app.services.accounting.exports_types import ExportFormat

        with patch('app.services.accounting.exports.AuditLogger') as MockAuditLogger:
            mock_audit = MagicMock()
            MockAuditLogger.return_value = mock_audit

            service = ReportExportService(mock_db, mock_principal)
            service.log_export(
                report_type="trial_balance",
                format=ExportFormat.CSV,
                description="Trial Balance Export",
                record_count=100,
            )

            mock_audit.log_export.assert_called_once()
            call_args = mock_audit.log_export.call_args
            assert "100 records" in call_args.kwargs.get("remarks", "")
