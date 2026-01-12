"""
Unit tests for PaymentAllocationService.

Tests payment allocation, auto-allocation, removal, and FX calculations.
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Any
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
import enum

import pytest

# Import the service and related classes
from app.services.payment_allocation_service import (
    PaymentAllocationService,
    PaymentAllocationError,
    AllocationRequest,
    OutstandingDocument,
)

# Import mock fixtures from conftest
from tests.unit.conftest import (
    MockSession,
    MockQuery,
    MockInvoice,
    MockInvoiceStatus,
    MockPurchaseInvoice,
    MockPurchaseInvoiceStatus,
    MockPayment,
    MockSupplierPayment,
    MockPaymentAllocation,
    MockContact,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session with custom query behavior."""
    return MockSession()


@pytest.fixture
def service(mock_db):
    """Create PaymentAllocationService with mock db."""
    return PaymentAllocationService(mock_db)


@pytest.fixture
def invoice_unpaid():
    """Unpaid invoice with full balance."""
    return MockInvoice(
        id=1,
        invoice_number="INV-001",
        customer_id=1,
        total_amount=Decimal("1000.00"),
        amount_paid=Decimal("0.00"),
        balance=Decimal("1000.00"),
        status=MockInvoiceStatus.PENDING,
        invoice_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        due_date=datetime(2024, 2, 15, tzinfo=timezone.utc),
        currency="NGN",
        conversion_rate=Decimal("1"),
    )


@pytest.fixture
def invoice_partially_paid():
    """Partially paid invoice."""
    return MockInvoice(
        id=2,
        invoice_number="INV-002",
        customer_id=1,
        total_amount=Decimal("1000.00"),
        amount_paid=Decimal("400.00"),
        balance=Decimal("600.00"),
        status=MockInvoiceStatus.PARTIALLY_PAID,
        invoice_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
        due_date=datetime(2024, 2, 10, tzinfo=timezone.utc),
        currency="NGN",
    )


@pytest.fixture
def invoice_usd():
    """Invoice in USD with conversion rate."""
    return MockInvoice(
        id=3,
        invoice_number="INV-003",
        customer_id=1,
        total_amount=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        balance=Decimal("500.00"),
        status=MockInvoiceStatus.PENDING,
        currency="USD",
        conversion_rate=Decimal("1500.00"),  # 1 USD = 1500 NGN
    )


@pytest.fixture
def payment_500():
    """Payment for 500."""
    return MockPayment(
        id=1,
        customer_id=1,
        customer_account_id=1,
        receipt_number="REC-001",
        amount=Decimal("500.00"),
        total_allocated=Decimal("0.00"),
        unallocated_amount=Decimal("500.00"),
        currency="NGN",
        conversion_rate=Decimal("1"),
    )


@pytest.fixture
def payment_1000():
    """Payment for 1000."""
    return MockPayment(
        id=2,
        customer_id=1,
        customer_account_id=1,
        receipt_number="REC-002",
        amount=Decimal("1000.00"),
        total_allocated=Decimal("0.00"),
        unallocated_amount=Decimal("1000.00"),
        currency="NGN",
    )


@pytest.fixture
def payment_1500():
    """Payment for 1500 - enough for multiple invoices."""
    return MockPayment(
        id=3,
        customer_id=1,
        customer_account_id=1,
        receipt_number="REC-003",
        amount=Decimal("1500.00"),
        total_allocated=Decimal("0.00"),
        unallocated_amount=Decimal("1500.00"),
        currency="NGN",
    )


@pytest.fixture
def payment_usd():
    """Payment in USD with different rate."""
    return MockPayment(
        id=4,
        customer_id=1,
        customer_account_id=1,
        receipt_number="REC-USD",
        amount=Decimal("500.00"),
        total_allocated=Decimal("0.00"),
        unallocated_amount=Decimal("500.00"),
        currency="USD",
        conversion_rate=Decimal("1550.00"),  # Different rate than invoice
    )


@pytest.fixture
def bill_unpaid():
    """Unpaid purchase invoice (bill)."""
    return MockPurchaseInvoice(
        id=1,
        bill_number="BILL-001",
        supplier="1",
        supplier_name="Test Supplier",
        grand_total=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        outstanding_amount=Decimal("500.00"),
        status=MockPurchaseInvoiceStatus.UNPAID,
        posting_date=date(2024, 1, 15),
        currency="NGN",
    )


@pytest.fixture
def supplier_payment():
    """Supplier payment."""
    return MockSupplierPayment(
        id=1,
        supplier_id=1,
        payment_number="PAY-001",
        paid_amount=Decimal("500.00"),
        total_allocated=Decimal("0.00"),
        unallocated_amount=Decimal("500.00"),
        currency="NGN",
    )


@pytest.fixture
def existing_allocation():
    """Existing allocation to be removed."""
    return MockPaymentAllocation(
        id=1,
        payment_id=1,
        allocation_type="invoice",
        document_id=1,
        allocated_amount=Decimal("500.00"),
        discount_amount=Decimal("0.00"),
        write_off_amount=Decimal("0.00"),
    )


# =============================================================================
# ALLOCATION TESTS
# =============================================================================


class TestAllocatePayment:
    """Tests for allocate_payment method."""

    def test_allocate_full_payment_to_single_invoice(
        self, service, mock_db, invoice_unpaid, payment_1000
    ):
        """Test full payment allocation marks invoice as paid."""
        # Setup mock queries
        mock_db._data = {}

        # Mock the payment query
        with patch.object(service, '_get_payment_for_update', return_value=payment_1000):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=2,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("1000.00"),
                                )
                            ],
                            user_id=1,
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("1000.00")
        # Verify payment was updated
        assert payment_1000.total_allocated == Decimal("1000.00")
        assert payment_1000.unallocated_amount == Decimal("0.00")

    def test_allocate_partial_payment(
        self, service, mock_db, invoice_unpaid, payment_500
    ):
        """Test partial payment allocation."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("500.00"),
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("500.00")
        # Invoice should be partially paid
        assert invoice_unpaid.status.value == MockInvoiceStatus.PARTIALLY_PAID.value
        assert invoice_unpaid.amount_paid == Decimal("500.00")
        assert invoice_unpaid.balance == Decimal("500.00")

    def test_allocate_to_multiple_invoices(
        self, service, mock_db, invoice_unpaid, invoice_partially_paid, payment_1500
    ):
        """Test allocation to multiple invoices."""
        call_count = [0]
        docs = [invoice_unpaid, invoice_partially_paid]

        def mock_get_doc(doc_type, doc_id):
            result = docs[call_count[0] % len(docs)]
            call_count[0] += 1
            return result

        outstanding = [Decimal("1000.00"), Decimal("600.00")]
        out_count = [0]

        def mock_get_outstanding(doc_type, doc):
            result = outstanding[out_count[0] % len(outstanding)]
            out_count[0] += 1
            return result

        with patch.object(service, '_get_payment_for_update', return_value=payment_1500):
            with patch.object(service, '_get_document_for_update', side_effect=mock_get_doc):
                with patch.object(service, '_get_outstanding_from_doc', side_effect=mock_get_outstanding):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=3,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("1000.00"),
                                ),
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=2,
                                    allocated_amount=Decimal("500.00"),
                                ),
                            ],
                        )

        assert len(allocations) == 2
        assert payment_1500.total_allocated == Decimal("1500.00")
        assert payment_1500.unallocated_amount == Decimal("0.00")

    def test_allocate_exceeds_available_raises_error(
        self, service, mock_db, invoice_unpaid, payment_500
    ):
        """Test allocation exceeding available amount raises error."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with pytest.raises(PaymentAllocationError) as exc_info:
                service.allocate_payment(
                    payment_id=1,
                    allocations=[
                        AllocationRequest(
                            document_type="invoice",
                            document_id=1,
                            allocated_amount=Decimal("600.00"),  # More than 500 available
                        )
                    ],
                )

        assert "exceeds available amount" in str(exc_info.value)

    def test_allocate_payment_not_found_raises_error(self, service, mock_db):
        """Test allocation with non-existent payment raises error."""
        with patch.object(service, '_get_payment_for_update', return_value=None):
            with pytest.raises(PaymentAllocationError) as exc_info:
                service.allocate_payment(
                    payment_id=999,
                    allocations=[
                        AllocationRequest(
                            document_type="invoice",
                            document_id=1,
                            allocated_amount=Decimal("100.00"),
                        )
                    ],
                )

        assert "Payment not found" in str(exc_info.value)

    def test_allocate_document_not_found_raises_error(
        self, service, mock_db, payment_500
    ):
        """Test allocation to non-existent document raises error."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=None):
                with pytest.raises(PaymentAllocationError) as exc_info:
                    service.allocate_payment(
                        payment_id=1,
                        allocations=[
                            AllocationRequest(
                                document_type="invoice",
                                document_id=999,
                                allocated_amount=Decimal("100.00"),
                            )
                        ],
                    )

        assert "Document not found" in str(exc_info.value)

    def test_allocate_invalid_document_type_raises_error(
        self, service, mock_db, payment_500
    ):
        """Test allocation with invalid document type raises error."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with pytest.raises(PaymentAllocationError) as exc_info:
                service.allocate_payment(
                    payment_id=1,
                    allocations=[
                        AllocationRequest(
                            document_type="invalid_type",
                            document_id=1,
                            allocated_amount=Decimal("100.00"),
                        )
                    ],
                )

        assert "Invalid document type" in str(exc_info.value)

    def test_allocate_exceeds_outstanding_raises_error(
        self, service, mock_db, invoice_unpaid, payment_1500
    ):
        """Test allocation exceeding document outstanding raises error."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_1500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with pytest.raises(PaymentAllocationError) as exc_info:
                        service.allocate_payment(
                            payment_id=3,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("1200.00"),  # More than 1000 outstanding
                                )
                            ],
                        )

        assert "exceeds outstanding" in str(exc_info.value)

    def test_allocate_with_discount(
        self, service, mock_db, invoice_unpaid, payment_500
    ):
        """Test allocation with discount amount."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("450.00"),
                                    discount_amount=Decimal("50.00"),
                                    discount_type="early_payment",
                                    discount_account="6200-Discounts Given",
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("450.00")
        assert allocations[0].discount_amount == Decimal("50.00")
        # Total settling = 450 + 50 = 500
        assert invoice_unpaid.amount_paid == Decimal("500.00")

    def test_allocate_with_write_off(
        self, service, mock_db, invoice_unpaid, payment_500
    ):
        """Test allocation with write-off amount."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("480.00"),
                                    write_off_amount=Decimal("20.00"),
                                    write_off_account="6300-Bad Debt",
                                    write_off_reason="Small balance write-off",
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].write_off_amount == Decimal("20.00")
        assert allocations[0].write_off_reason == "Small balance write-off"

    def test_allocate_with_discount_and_write_off_exceeds_outstanding(
        self, service, mock_db, invoice_unpaid, payment_1000
    ):
        """Test that discount + write-off + allocation cannot exceed outstanding."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_1000):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with pytest.raises(PaymentAllocationError) as exc_info:
                        service.allocate_payment(
                            payment_id=2,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("900.00"),
                                    discount_amount=Decimal("100.00"),
                                    write_off_amount=Decimal("50.00"),  # Total = 1050 > 1000
                                )
                            ],
                        )

        assert "exceeds outstanding" in str(exc_info.value)


class TestAllocateSupplierPayment:
    """Tests for supplier payment allocation."""

    def test_allocate_supplier_payment_to_bill(
        self, service, mock_db, bill_unpaid, supplier_payment
    ):
        """Test allocation of supplier payment to bill."""
        with patch.object(service, '_get_payment_for_update', return_value=supplier_payment):
            with patch.object(service, '_get_document_for_update', return_value=bill_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("500.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="bill",
                                    document_id=1,
                                    allocated_amount=Decimal("500.00"),
                                )
                            ],
                            is_supplier_payment=True,
                        )

        assert len(allocations) == 1
        assert allocations[0].supplier_payment_id == 1
        assert allocations[0].payment_id is None
        assert supplier_payment.total_allocated == Decimal("500.00")
        assert supplier_payment.unallocated_amount == Decimal("0.00")


# =============================================================================
# AUTO-ALLOCATION TESTS
# =============================================================================


class TestAutoAllocate:
    """Tests for auto_allocate method."""

    def test_auto_allocate_fifo_order(
        self, service, mock_db, invoice_unpaid, invoice_partially_paid, payment_1500
    ):
        """Test auto-allocation allocates in FIFO order (oldest first)."""
        # Create outstanding docs - partially_paid is older
        outstanding_docs = [
            OutstandingDocument(
                document_type="invoice",
                document_id=2,  # Older invoice
                document_number="INV-002",
                document_date="2024-01-10",
                due_date="2024-02-10",
                currency="NGN",
                total_amount=Decimal("1000.00"),
                outstanding_amount=Decimal("600.00"),
                party_name=None,
            ),
            OutstandingDocument(
                document_type="invoice",
                document_id=1,  # Newer invoice
                document_number="INV-001",
                document_date="2024-01-15",
                due_date="2024-02-15",
                currency="NGN",
                total_amount=Decimal("1000.00"),
                outstanding_amount=Decimal("1000.00"),
                party_name=None,
            ),
        ]

        with patch.object(mock_db, 'query') as mock_query:
            # Mock payment query
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = payment_1500
            mock_query.return_value = mock_payment_query

            with patch.object(service, 'get_outstanding_documents', return_value=outstanding_docs):
                with patch.object(service, 'allocate_payment') as mock_allocate:
                    mock_allocate.return_value = []
                    service.auto_allocate(payment_id=3, user_id=1)

                    # Verify allocate_payment was called with FIFO order
                    call_args = mock_allocate.call_args
                    allocations = call_args[1]['allocations']

                    # First allocation should be to older invoice (INV-002)
                    assert allocations[0].document_id == 2
                    assert allocations[0].allocated_amount == Decimal("600.00")
                    # Second allocation to newer invoice
                    assert allocations[1].document_id == 1
                    assert allocations[1].allocated_amount == Decimal("900.00")

    def test_auto_allocate_no_outstanding_docs(
        self, service, mock_db, payment_500
    ):
        """Test auto-allocation with no outstanding documents returns empty."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = payment_500
            mock_query.return_value = mock_payment_query

            with patch.object(service, 'get_outstanding_documents', return_value=[]):
                result = service.auto_allocate(payment_id=1)

        assert result == []

    def test_auto_allocate_payment_not_found_raises_error(self, service, mock_db):
        """Test auto-allocation with non-existent payment raises error."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = None
            mock_query.return_value = mock_payment_query

            with pytest.raises(PaymentAllocationError) as exc_info:
                service.auto_allocate(payment_id=999)

        assert "Payment not found" in str(exc_info.value)

    def test_auto_allocate_zero_available_returns_empty(
        self, service, mock_db
    ):
        """Test auto-allocation with zero available amount returns empty."""
        payment = MockPayment(
            id=1,
            customer_id=1,
            customer_account_id=1,
            amount=Decimal("500.00"),
            total_allocated=Decimal("500.00"),
            unallocated_amount=Decimal("0.00"),
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = payment
            mock_query.return_value = mock_payment_query

            result = service.auto_allocate(payment_id=1)

        assert result == []

    def test_auto_allocate_partial_coverage(
        self, service, mock_db, payment_500
    ):
        """Test auto-allocation that only partially covers documents."""
        outstanding_docs = [
            OutstandingDocument(
                document_type="invoice",
                document_id=1,
                document_number="INV-001",
                document_date="2024-01-15",
                due_date="2024-02-15",
                currency="NGN",
                total_amount=Decimal("1000.00"),
                outstanding_amount=Decimal("1000.00"),
                party_name=None,
            ),
        ]

        with patch.object(mock_db, 'query') as mock_query:
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = payment_500
            mock_query.return_value = mock_payment_query

            with patch.object(service, 'get_outstanding_documents', return_value=outstanding_docs):
                with patch.object(service, 'allocate_payment') as mock_allocate:
                    mock_allocate.return_value = []
                    service.auto_allocate(payment_id=1)

                    # Should only allocate 500 of the 1000 outstanding
                    call_args = mock_allocate.call_args
                    allocations = call_args[1]['allocations']
                    assert len(allocations) == 1
                    assert allocations[0].allocated_amount == Decimal("500.00")

    def test_auto_allocate_supplier_payment(
        self, service, mock_db, supplier_payment
    ):
        """Test auto-allocation of supplier payment."""
        outstanding_docs = [
            OutstandingDocument(
                document_type="bill",
                document_id=1,
                document_number="BILL-001",
                document_date="2024-01-15",
                due_date="2024-02-15",
                currency="NGN",
                total_amount=Decimal("500.00"),
                outstanding_amount=Decimal("500.00"),
                party_name="Test Supplier",
            ),
        ]

        with patch.object(mock_db, 'query') as mock_query:
            mock_payment_query = MagicMock()
            mock_payment_query.filter.return_value.first.return_value = supplier_payment
            mock_query.return_value = mock_payment_query

            with patch.object(service, 'get_outstanding_documents', return_value=outstanding_docs):
                with patch.object(service, 'allocate_payment') as mock_allocate:
                    mock_allocate.return_value = []
                    service.auto_allocate(
                        payment_id=1,
                        is_supplier_payment=True,
                    )

                    call_args = mock_allocate.call_args
                    assert call_args[1]['is_supplier_payment'] is True


# =============================================================================
# REMOVE ALLOCATION TESTS
# =============================================================================


class TestRemoveAllocation:
    """Tests for remove_allocation method."""

    def test_remove_allocation_restores_document_balance(
        self, service, mock_db, existing_allocation, invoice_unpaid, payment_500
    ):
        """Test removing allocation restores document and payment balances."""
        # Set up invoice as if it was already allocated
        invoice_unpaid.amount_paid = Decimal("500.00")
        invoice_unpaid.balance = Decimal("500.00")
        invoice_unpaid.status = MockInvoiceStatus.PARTIALLY_PAID

        # Set up payment as already allocated
        payment_500.total_allocated = Decimal("500.00")
        payment_500.unallocated_amount = Decimal("0.00")

        # Mock the allocation type value
        existing_allocation.allocation_type = MagicMock()
        existing_allocation.allocation_type.value = "invoice"

        with patch.object(mock_db, 'query') as mock_query:
            mock_alloc_query = MagicMock()
            mock_alloc_query.filter.return_value.with_for_update.return_value.first.return_value = existing_allocation
            mock_query.return_value = mock_alloc_query

            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_payment_for_update', return_value=payment_500):
                    service.remove_allocation(allocation_id=1)

        # Document balance should be restored
        assert invoice_unpaid.amount_paid == Decimal("0.00")
        assert invoice_unpaid.balance == Decimal("1000.00")
        # Payment should be unallocated
        assert payment_500.total_allocated == Decimal("0.00")
        assert payment_500.unallocated_amount == Decimal("500.00")
        # Allocation should be deleted
        assert existing_allocation in mock_db._deleted

    def test_remove_allocation_not_found_raises_error(self, service, mock_db):
        """Test removing non-existent allocation raises error."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_alloc_query = MagicMock()
            mock_alloc_query.filter.return_value.with_for_update.return_value.first.return_value = None
            mock_query.return_value = mock_alloc_query

            with pytest.raises(PaymentAllocationError) as exc_info:
                service.remove_allocation(allocation_id=999)

        assert "Allocation not found" in str(exc_info.value)

    def test_remove_allocation_document_not_found_raises_error(
        self, service, mock_db, existing_allocation
    ):
        """Test removing allocation for non-existent document raises error."""
        existing_allocation.allocation_type = MagicMock()
        existing_allocation.allocation_type.value = "invoice"

        with patch.object(mock_db, 'query') as mock_query:
            mock_alloc_query = MagicMock()
            mock_alloc_query.filter.return_value.with_for_update.return_value.first.return_value = existing_allocation
            mock_query.return_value = mock_alloc_query

            with patch.object(service, '_get_document_for_update', return_value=None):
                with pytest.raises(PaymentAllocationError) as exc_info:
                    service.remove_allocation(allocation_id=1)

        assert "Document not found" in str(exc_info.value)

    def test_remove_supplier_allocation(
        self, service, mock_db, bill_unpaid, supplier_payment
    ):
        """Test removing supplier payment allocation."""
        allocation = MockPaymentAllocation(
            id=1,
            supplier_payment_id=1,
            payment_id=None,
            allocation_type="bill",
            document_id=1,
            allocated_amount=Decimal("500.00"),
        )
        allocation.allocation_type = MagicMock()
        allocation.allocation_type.value = "bill"

        bill_unpaid.paid_amount = Decimal("500.00")
        bill_unpaid.outstanding_amount = Decimal("0.00")
        supplier_payment.total_allocated = Decimal("500.00")
        supplier_payment.unallocated_amount = Decimal("0.00")

        with patch.object(mock_db, 'query') as mock_query:
            mock_alloc_query = MagicMock()
            mock_alloc_query.filter.return_value.with_for_update.return_value.first.return_value = allocation
            mock_query.return_value = mock_alloc_query

            with patch.object(service, '_get_document_for_update', return_value=bill_unpaid):
                with patch.object(service, '_get_payment_for_update', return_value=supplier_payment):
                    service.remove_allocation(allocation_id=1)

        assert supplier_payment.total_allocated == Decimal("0.00")
        assert supplier_payment.unallocated_amount == Decimal("500.00")


# =============================================================================
# GET OUTSTANDING DOCUMENTS TESTS
# =============================================================================


class TestGetOutstandingDocuments:
    """Tests for get_outstanding_documents method."""

    def test_get_outstanding_customer_invoices(
        self, service, mock_db, invoice_unpaid, invoice_partially_paid
    ):
        """Test getting outstanding invoices for customer."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            mock_inv_query.filter.return_value.order_by.return_value.all.return_value = [
                invoice_partially_paid,  # Older, returned first
                invoice_unpaid,
            ]
            mock_query.return_value = mock_inv_query

            docs = service.get_outstanding_documents(
                party_type="customer",
                party_id=1,
            )

        assert len(docs) == 2
        # First doc should be the older one (partially paid)
        assert docs[0].document_id == 2
        assert docs[0].outstanding_amount == Decimal("600.00")
        # Second doc is the newer one
        assert docs[1].document_id == 1
        assert docs[1].outstanding_amount == Decimal("1000.00")

    def test_get_outstanding_supplier_bills(
        self, service, mock_db, bill_unpaid
    ):
        """Test getting outstanding bills for supplier."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_bill_query = MagicMock()
            mock_bill_query.filter.return_value.order_by.return_value.all.return_value = [bill_unpaid]
            mock_query.return_value = mock_bill_query

            docs = service.get_outstanding_documents(
                party_type="supplier",
                party_id=1,
            )

        assert len(docs) == 1
        assert docs[0].document_type == "bill"
        assert docs[0].outstanding_amount == Decimal("500.00")
        assert docs[0].party_name == "Test Supplier"

    def test_get_outstanding_contact_invoices(
        self, service, mock_db, invoice_unpaid
    ):
        """Contact lookups are not supported for outstanding documents."""
        invoice_unpaid.contact_id = 100
        contact = MockContact(id=100, display_name="John Doe", email="john@example.com")

        with patch.object(mock_db, 'query') as mock_query:
            def query_side_effect(model):
                mock_q = MagicMock()
                if hasattr(model, '__name__') and 'Invoice' in str(model):
                    mock_q.filter.return_value.order_by.return_value.all.return_value = [invoice_unpaid]
                elif hasattr(model, '__name__') and 'Contact' in str(model):
                    mock_q.filter.return_value.first.return_value = contact
                return mock_q

            mock_query.side_effect = query_side_effect

            docs = service.get_outstanding_documents(
                party_type="contact",
                party_id=100,
            )

        assert len(docs) == 0

    def test_get_outstanding_with_currency_filter(
        self, service, mock_db, invoice_unpaid, invoice_usd
    ):
        """Test filtering outstanding documents by currency."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            # Only return NGN invoice when filtered
            mock_inv_query.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
                invoice_unpaid
            ]
            mock_query.return_value = mock_inv_query

            docs = service.get_outstanding_documents(
                party_type="customer",
                party_id=1,
                currency="NGN",
            )

        assert len(docs) == 1
        assert docs[0].currency == "NGN"

    def test_get_outstanding_excludes_paid_invoices(
        self, service, mock_db
    ):
        """Test that fully paid invoices are excluded."""
        paid_invoice = MockInvoice(
            id=10,
            invoice_number="INV-PAID",
            total_amount=Decimal("1000.00"),
            amount_paid=Decimal("1000.00"),
            balance=Decimal("0.00"),
            status=MockInvoiceStatus.PAID,
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            # Query filters should exclude paid invoices
            mock_inv_query.filter.return_value.order_by.return_value.all.return_value = []
            mock_query.return_value = mock_inv_query

            docs = service.get_outstanding_documents(
                party_type="customer",
                party_id=1,
            )

        assert len(docs) == 0


# =============================================================================
# FX GAIN/LOSS TESTS
# =============================================================================


class TestFXGainLoss:
    """Tests for FX gain/loss calculation."""

    def test_calculate_fx_gain(self, service, mock_db, invoice_usd, payment_usd):
        """Test FX gain calculation when payment rate > invoice rate."""
        allocation = MockPaymentAllocation(
            id=1,
            payment_id=4,
            document_id=3,
            allocated_amount=Decimal("500.00"),
            conversion_rate=Decimal("1550.00"),  # Payment rate
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            mock_inv_query.filter.return_value.first.return_value = invoice_usd
            mock_query.return_value = mock_inv_query

            fx_gain_loss = service._calculate_fx_gain_loss(
                allocation,
                doc_type="invoice",
                doc_id=3,
            )

        # FX gain = 500 * (1550 - 1500) = 500 * 50 = 25,000
        assert fx_gain_loss == Decimal("25000.00")

    def test_calculate_fx_loss(self, service, mock_db):
        """Test FX loss calculation when payment rate < invoice rate."""
        invoice = MockInvoice(
            id=5,
            invoice_number="INV-USD-2",
            total_amount=Decimal("500.00"),
            currency="USD",
            conversion_rate=Decimal("1550.00"),  # Invoice rate
        )

        allocation = MockPaymentAllocation(
            id=2,
            payment_id=5,
            document_id=5,
            allocated_amount=Decimal("500.00"),
            conversion_rate=Decimal("1500.00"),  # Payment rate < invoice rate
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            mock_inv_query.filter.return_value.first.return_value = invoice
            mock_query.return_value = mock_inv_query

            fx_gain_loss = service._calculate_fx_gain_loss(
                allocation,
                doc_type="invoice",
                doc_id=5,
            )

        # FX loss = 500 * (1500 - 1550) = 500 * (-50) = -25,000
        assert fx_gain_loss == Decimal("-25000.00")

    def test_calculate_fx_no_difference(self, service, mock_db, invoice_unpaid):
        """Test no FX gain/loss when rates are equal."""
        allocation = MockPaymentAllocation(
            id=3,
            payment_id=1,
            document_id=1,
            allocated_amount=Decimal("500.00"),
            conversion_rate=Decimal("1"),  # Same as invoice
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_inv_query = MagicMock()
            mock_inv_query.filter.return_value.first.return_value = invoice_unpaid
            mock_query.return_value = mock_inv_query

            fx_gain_loss = service._calculate_fx_gain_loss(
                allocation,
                doc_type="invoice",
                doc_id=1,
            )

        assert fx_gain_loss == Decimal("0")

    def test_calculate_fx_bill(self, service, mock_db, bill_unpaid):
        """Test FX calculation for bills (purchase invoices)."""
        bill_unpaid.conversion_rate = Decimal("1500.00")

        allocation = MockPaymentAllocation(
            id=4,
            supplier_payment_id=1,
            document_id=1,
            allocated_amount=Decimal("500.00"),
            conversion_rate=Decimal("1520.00"),
        )

        with patch.object(mock_db, 'query') as mock_query:
            mock_bill_query = MagicMock()
            mock_bill_query.filter.return_value.first.return_value = bill_unpaid
            mock_query.return_value = mock_bill_query

            fx_gain_loss = service._calculate_fx_gain_loss(
                allocation,
                doc_type="bill",
                doc_id=1,
            )

        # FX = 500 * (1520 - 1500) = 500 * 20 = 10,000
        assert fx_gain_loss == Decimal("10000.00")


# =============================================================================
# DOCUMENT STATUS UPDATE TESTS
# =============================================================================


class TestDocumentStatusUpdates:
    """Tests for document status transitions."""

    def test_invoice_status_paid_on_full_settlement(
        self, service, mock_db, invoice_unpaid, payment_1000
    ):
        """Test invoice status changes to PAID on full settlement."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_1000):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        service.allocate_payment(
                            payment_id=2,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("1000.00"),
                                )
                            ],
                        )

        assert invoice_unpaid.status.value == MockInvoiceStatus.PAID.value
        assert invoice_unpaid.balance == Decimal("0.00")

    def test_invoice_status_partially_paid(
        self, service, mock_db, invoice_unpaid, payment_500
    ):
        """Test invoice status changes to PARTIALLY_PAID."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("500.00"),
                                )
                            ],
                        )

        assert invoice_unpaid.status.value == MockInvoiceStatus.PARTIALLY_PAID.value
        assert invoice_unpaid.balance == Decimal("500.00")

    def test_bill_status_paid_on_full_settlement(
        self, service, mock_db, bill_unpaid, supplier_payment
    ):
        """Test bill status changes to PAID on full settlement."""
        with patch.object(service, '_get_payment_for_update', return_value=supplier_payment):
            with patch.object(service, '_get_document_for_update', return_value=bill_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("500.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="bill",
                                    document_id=1,
                                    allocated_amount=Decimal("500.00"),
                                )
                            ],
                            is_supplier_payment=True,
                        )

        assert bill_unpaid.status.value == MockPurchaseInvoiceStatus.PAID.value
        assert bill_unpaid.outstanding_amount == Decimal("0.00")


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_allocate_zero_amount(self, service, mock_db, invoice_unpaid, payment_500):
        """Test allocation with zero amount (only discount/write-off)."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            with patch.object(service, '_get_document_for_update', return_value=invoice_unpaid):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("1000.00")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=1,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=1,
                                    allocated_amount=Decimal("0.00"),
                                    discount_amount=Decimal("100.00"),
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("0.00")
        assert allocations[0].discount_amount == Decimal("100.00")
        # Payment total_allocated should reflect the actual payment amount (0)
        assert payment_500.total_allocated == Decimal("0.00")

    def test_allocate_empty_list(self, service, mock_db, payment_500):
        """Test allocation with empty allocation list."""
        with patch.object(service, '_get_payment_for_update', return_value=payment_500):
            allocations = service.allocate_payment(
                payment_id=1,
                allocations=[],
            )

        assert allocations == []
        assert payment_500.total_allocated == Decimal("0.00")

    def test_very_small_amounts(self, service, mock_db, payment_500):
        """Test allocation with very small decimal amounts."""
        invoice = MockInvoice(
            id=100,
            invoice_number="INV-SMALL",
            total_amount=Decimal("0.01"),
            amount_paid=Decimal("0.00"),
            balance=Decimal("0.01"),
            status=MockInvoiceStatus.PENDING,
        )

        payment = MockPayment(
            id=100,
            customer_account_id=1,
            amount=Decimal("0.01"),
            total_allocated=Decimal("0.00"),
            unallocated_amount=Decimal("0.01"),
        )

        with patch.object(service, '_get_payment_for_update', return_value=payment):
            with patch.object(service, '_get_document_for_update', return_value=invoice):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("0.01")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=100,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=100,
                                    allocated_amount=Decimal("0.01"),
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("0.01")
        assert invoice.status.value == MockInvoiceStatus.PAID.value

    def test_large_amounts(self, service, mock_db):
        """Test allocation with very large amounts."""
        invoice = MockInvoice(
            id=200,
            invoice_number="INV-LARGE",
            total_amount=Decimal("999999999.99"),
            amount_paid=Decimal("0.00"),
            balance=Decimal("999999999.99"),
            status=MockInvoiceStatus.PENDING,
        )

        payment = MockPayment(
            id=200,
            customer_account_id=1,
            amount=Decimal("999999999.99"),
            total_allocated=Decimal("0.00"),
            unallocated_amount=Decimal("999999999.99"),
        )

        with patch.object(service, '_get_payment_for_update', return_value=payment):
            with patch.object(service, '_get_document_for_update', return_value=invoice):
                with patch.object(service, '_get_outstanding_from_doc', return_value=Decimal("999999999.99")):
                    with patch.object(service, '_calculate_fx_gain_loss', return_value=Decimal("0")):
                        allocations = service.allocate_payment(
                            payment_id=200,
                            allocations=[
                                AllocationRequest(
                                    document_type="invoice",
                                    document_id=200,
                                    allocated_amount=Decimal("999999999.99"),
                                )
                            ],
                        )

        assert len(allocations) == 1
        assert allocations[0].allocated_amount == Decimal("999999999.99")

    def test_payment_without_unallocated_amount_attribute(self, service, mock_db):
        """Test handling payment that uses 'amount' instead of 'unallocated_amount'."""
        # Payment without unallocated_amount (uses amount as available)
        payment = MagicMock()
        payment.amount = Decimal("500.00")
        del payment.unallocated_amount  # Simulate missing attribute
        type(payment).unallocated_amount = PropertyMock(side_effect=AttributeError)

        # Should fall back to using 'amount'
        with patch.object(service, '_get_payment_for_update', return_value=payment):
            with pytest.raises(PaymentAllocationError):
                # This should work up until trying to allocate more than available
                service.allocate_payment(
                    payment_id=1,
                    allocations=[
                        AllocationRequest(
                            document_type="invoice",
                            document_id=1,
                            allocated_amount=Decimal("600.00"),  # More than 500
                        )
                    ],
                )
