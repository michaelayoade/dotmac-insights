"""AR Payment service - business logic for accounts receivable payments.

This service encapsulates all customer payment-related business logic:
- CRUD operations
- Payment allocation to invoices/credit notes
- Integration with PaymentAllocationService

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentMethod, PaymentSource, PaymentStatus
from app.models.payment_allocation import PaymentAllocation
from app.services.base import paginate, safe_filter, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.payment_allocation_service import (
    AllocationRequest,
    PaymentAllocationError,
    PaymentAllocationService,
)
from app.services.types import PaginatedResult, PaginationParams

from .ar_payment_types import AllocationData, PaymentCreateData, PaymentFilters, PaymentUpdateData

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ARPaymentService"]

# Allowed filter fields for safe_filter
ALLOWED_FILTERS = {"customer_account_id", "status"}


class ARPaymentService:
    """Service for AR payment business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_payments(
        self,
        filters: Optional[PaymentFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Payment]:
        """List payments with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing payments and total count.
        """
        if filters is None:
            filters = PaymentFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Payment)
        query = scoped_query(query, self.principal)

        # Apply simple equality filters
        filter_dict = {
            "customer_account_id": filters.customer_account_id,
            "status": filters.status,
        }
        query = safe_filter(query, Payment, filter_dict, ALLOWED_FILTERS)

        # Date range filters
        if filters.start_date:
            query = query.filter(Payment.payment_date >= filters.start_date)
        if filters.end_date:
            query = query.filter(Payment.payment_date <= filters.end_date)

        # Default ordering
        query = query.order_by(Payment.payment_date.desc(), Payment.id.desc())

        return paginate(query, pagination)

    def get_payment(self, payment_id: int) -> Payment:
        """Get a payment by ID.

        Args:
            payment_id: The payment ID.

        Returns:
            The Payment object.

        Raises:
            NotFoundError: If payment not found.
        """
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise NotFoundError(f"Payment {payment_id} not found")
        return payment

    def get_payment_allocations(self, payment_id: int) -> List[PaymentAllocation]:
        """Get allocations for a payment.

        Args:
            payment_id: The payment ID.

        Returns:
            List of PaymentAllocation objects.
        """
        return (
            self.db.query(PaymentAllocation)
            .filter(PaymentAllocation.payment_id == payment_id)
            .all()
        )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_payment(self, data: PaymentCreateData) -> Payment:
        """Create a new customer payment.

        Validates contact/customer, creates payment, and optionally
        processes allocations using PaymentAllocationService.

        Args:
            data: Payment creation data.

        Returns:
            The created Payment (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        if not data.customer_account_id:
            raise ValidationError("customer_account_id is required")

        if data.amount <= 0:
            raise ValidationError("Payment amount must be positive")

        payment = Payment(
            customer_account_id=data.customer_account_id,
            payment_date=data.payment_date,
            amount=data.amount,
            currency=data.currency,
            payment_method=data.payment_method,
            receipt_number=data.receipt_number,
            transaction_reference=data.transaction_reference,
            notes=data.notes,
            conversion_rate=data.conversion_rate,
            bank_account_id=data.bank_account_id,
            source=PaymentSource.INTERNAL,
            status=PaymentStatus.PENDING,
            workflow_status="pending",
            write_back_status="pending",
            created_by_id=self.principal.id if self.principal else None,
            origin_system="local",
        )

        # Calculate base amount
        payment.base_currency = "NGN"  # TODO: Get from company settings
        payment.base_amount = payment.amount * payment.conversion_rate
        payment.unallocated_amount = payment.amount
        payment.total_allocated = Decimal("0")

        self.db.add(payment)
        self.db.flush()  # Get payment.id for allocations

        # Process allocations if provided
        if data.allocations:
            self._process_allocations(payment.id, data.allocations)
            self.db.refresh(payment)

        return payment

    def update_payment(self, payment_id: int, data: PaymentUpdateData) -> Payment:
        """Update a draft payment.

        Args:
            payment_id: The payment ID.
            data: Fields to update.

        Returns:
            The updated Payment (not yet committed).

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment is not a draft.
        """
        # Use SELECT FOR UPDATE to prevent race conditions
        payment = (
            self.db.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()
            .first()
        )
        if not payment:
            raise NotFoundError(f"Payment {payment_id} not found")

        if payment.docstatus != 0:
            raise ValidationError("Can only update draft payments")

        if data.payment_date is not None:
            payment.payment_date = data.payment_date

        if data.amount is not None:
            if data.amount <= 0:
                raise ValidationError("Payment amount must be positive")
            payment.amount = data.amount
            payment.base_amount = payment.amount * payment.conversion_rate
            payment.unallocated_amount = payment.amount - payment.total_allocated

        if data.payment_method is not None:
            payment.payment_method = data.payment_method

        if data.transaction_reference is not None:
            payment.transaction_reference = data.transaction_reference

        if data.notes is not None:
            payment.notes = data.notes

        if data.conversion_rate is not None:
            payment.conversion_rate = data.conversion_rate
            payment.base_amount = payment.amount * payment.conversion_rate

        payment.updated_by_id = self.principal.id if self.principal else None

        return payment

    def delete_payment(self, payment_id: int) -> None:
        """Soft delete a draft payment and its allocations.

        Args:
            payment_id: The payment ID.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment is not a draft.
        """
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise NotFoundError(f"Payment {payment_id} not found")

        if payment.docstatus != 0:
            raise ValidationError("Can only delete draft payments")

        # Remove allocations first
        self.db.query(PaymentAllocation).filter(
            PaymentAllocation.payment_id == payment_id
        ).delete()

        payment.is_deleted = True
        payment.deleted_at = datetime.now(timezone.utc)
        payment.deleted_by_id = self.principal.id if self.principal else None

    # -------------------------------------------------------------------------
    # Allocations
    # -------------------------------------------------------------------------

    def add_allocations(
        self, payment_id: int, allocations: List[AllocationData]
    ) -> Payment:
        """Add allocations to an existing payment.

        Args:
            payment_id: The payment ID.
            allocations: List of allocations to add.

        Returns:
            The updated Payment.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If allocation fails.
        """
        payment = self.get_payment(payment_id)
        self._process_allocations(payment_id, allocations)
        self.db.refresh(payment)
        return payment

    def _process_allocations(
        self, payment_id: int, allocations: List[AllocationData]
    ) -> None:
        """Process payment allocations using PaymentAllocationService.

        Args:
            payment_id: The payment ID.
            allocations: List of allocations to process.

        Raises:
            ValidationError: If allocation fails.
        """
        alloc_service = PaymentAllocationService(self.db)
        alloc_requests = [
            AllocationRequest(
                document_type=a.document_type,
                document_id=a.document_id,
                allocated_amount=a.allocated_amount,
                discount_amount=a.discount_amount,
                write_off_amount=a.write_off_amount,
                discount_type=a.discount_type,
                discount_account=a.discount_account,
                write_off_account=a.write_off_account,
                write_off_reason=a.write_off_reason,
            )
            for a in allocations
        ]
        try:
            alloc_service.allocate_payment(
                payment_id=payment_id,
                allocations=alloc_requests,
                user_id=self.principal.id if self.principal else None,
                is_supplier_payment=False,
            )
        except PaymentAllocationError as e:
            raise ValidationError(str(e)) from e
