"""AP Payment service - business logic for accounts payable payments.

This service encapsulates all supplier payment-related business logic:
- CRUD operations
- Payment allocation to bills/debit notes
- Workflow (submit, approve, reject, post)
- Integration with PaymentAllocationService

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session

from app.models.supplier_payment import SupplierPayment, SupplierPaymentStatus
from app.models.payment_allocation import PaymentAllocation
from app.services.base import paginate, safe_filter, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.payment_allocation_service import (
    AllocationRequest,
    PaymentAllocationError,
    PaymentAllocationService,
)
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService
from app.services.activity_logger import ActivityLogger

from .ap_payment_types import (
    APAllocationData,
    APPaymentCreateData,
    APPaymentFilters,
    APPaymentUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["APPaymentService"]

# Allowed filter fields for safe_filter
ALLOWED_FILTERS = {"supplier_id", "status"}


class APPaymentService:
    """Service for AP (supplier) payment business logic.

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
        filters: Optional[APPaymentFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[SupplierPayment]:
        """List supplier payments with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing payments and total count.
        """
        if filters is None:
            filters = APPaymentFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(SupplierPayment)
        query = scoped_query(query, self.principal)

        # Apply simple equality filters
        filter_dict = {
            "supplier_id": filters.supplier_id,
            "status": filters.status,
        }
        query = safe_filter(query, SupplierPayment, filter_dict, ALLOWED_FILTERS)

        # Date range filters
        if filters.start_date:
            query = query.filter(SupplierPayment.payment_date >= filters.start_date)
        if filters.end_date:
            query = query.filter(SupplierPayment.payment_date <= filters.end_date)

        # Default ordering
        query = query.order_by(
            SupplierPayment.payment_date.desc(), SupplierPayment.id.desc()
        )

        return paginate(query, pagination)

    def get_payment(self, payment_id: int) -> SupplierPayment:
        """Get a supplier payment by ID.

        Args:
            payment_id: The payment ID.

        Returns:
            The SupplierPayment object.

        Raises:
            NotFoundError: If payment not found.
        """
        payment = (
            self.db.query(SupplierPayment)
            .filter(SupplierPayment.id == payment_id)
            .first()
        )
        if not payment:
            raise NotFoundError(f"Supplier payment {payment_id} not found")
        return payment

    def get_payment_allocations(self, payment_id: int) -> List[PaymentAllocation]:
        """Get allocations for a supplier payment.

        Args:
            payment_id: The payment ID.

        Returns:
            List of PaymentAllocation objects.
        """
        return (
            self.db.query(PaymentAllocation)
            .filter(PaymentAllocation.supplier_payment_id == payment_id)
            .all()
        )

    def get_outstanding_bills(
        self, supplier_id: int, currency: Optional[str] = None
    ) -> List:
        """Get outstanding bills available for payment.

        Args:
            supplier_id: The supplier ID.
            currency: Optional currency filter.

        Returns:
            List of outstanding documents.
        """
        alloc_service = PaymentAllocationService(self.db)
        return alloc_service.get_outstanding_documents("supplier", supplier_id, currency)

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_payment(self, data: APPaymentCreateData) -> SupplierPayment:
        """Create a new supplier payment.

        Validates supplier, creates payment, and optionally
        processes allocations using PaymentAllocationService.

        Args:
            data: Payment creation data.

        Returns:
            The created SupplierPayment (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        if data.paid_amount <= 0:
            raise ValidationError("Payment amount must be positive")

        # Generate payment number
        from app.services.number_generator import generate_voucher_number

        payment_number = generate_voucher_number(self.db, "supplier_payment")

        posting_date = data.posting_date if data.posting_date else data.payment_date

        payment = SupplierPayment(
            payment_number=payment_number,
            supplier_id=data.supplier_id,
            supplier_name=data.supplier_name,
            payment_date=data.payment_date,
            posting_date=posting_date,
            mode_of_payment=data.mode_of_payment,
            bank_account_id=data.bank_account_id,
            currency=data.currency,
            paid_amount=data.paid_amount,
            conversion_rate=data.conversion_rate,
            reference_number=data.reference_number,
            reference_date=data.reference_date,
            remarks=data.remarks,
            company=data.company,
            status=SupplierPaymentStatus.DRAFT,
            created_by_id=self.principal.id if self.principal else None,
        )

        # Calculate base amount
        payment.base_paid_amount = payment.paid_amount * payment.conversion_rate
        payment.unallocated_amount = payment.paid_amount
        payment.total_allocated = Decimal("0")

        self.db.add(payment)
        self.db.flush()  # Get payment.id for allocations

        # Process allocations if provided
        if data.allocations:
            self._process_allocations(payment.id, data.allocations)
            self.db.refresh(payment)

        validator = SoftValidationService(self.db)
        for allocation in self.get_payment_allocations(payment.id):
            validator.validate_and_store(allocation)
        validator.validate_and_store(payment)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.supplier_payment.create",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="supplier_payment",
            entity_id=str(payment.id),
            summary=f"Created supplier payment {payment.payment_number or payment.id}",
            metadata={"supplier_id": payment.supplier_id, "amount": float(payment.paid_amount)},
        )
        return payment

    def update_payment(
        self, payment_id: int, data: APPaymentUpdateData
    ) -> SupplierPayment:
        """Update a draft supplier payment.

        Args:
            payment_id: The payment ID.
            data: Fields to update.

        Returns:
            The updated SupplierPayment (not yet committed).

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment is not a draft.
        """
        # Use SELECT FOR UPDATE to prevent race conditions
        payment = (
            self.db.query(SupplierPayment)
            .filter(SupplierPayment.id == payment_id)
            .with_for_update()
            .first()
        )
        if not payment:
            raise NotFoundError(f"Supplier payment {payment_id} not found")

        if payment.status != SupplierPaymentStatus.DRAFT:
            raise ValidationError("Can only update draft payments")

        if data.payment_date is not None:
            payment.payment_date = data.payment_date

        if data.posting_date is not None:
            payment.posting_date = data.posting_date

        if data.mode_of_payment is not None:
            payment.mode_of_payment = data.mode_of_payment

        if data.bank_account_id is not None:
            payment.bank_account_id = data.bank_account_id

        if data.paid_amount is not None:
            if data.paid_amount <= 0:
                raise ValidationError("Payment amount must be positive")
            payment.paid_amount = data.paid_amount
            payment.unallocated_amount = payment.paid_amount - payment.total_allocated

        if data.conversion_rate is not None:
            payment.conversion_rate = data.conversion_rate
            payment.base_paid_amount = payment.paid_amount * payment.conversion_rate

        if data.reference_number is not None:
            payment.reference_number = data.reference_number

        if data.reference_date is not None:
            payment.reference_date = data.reference_date

        if data.remarks is not None:
            payment.remarks = data.remarks

        validator = SoftValidationService(self.db)
        for allocation in self.get_payment_allocations(payment.id):
            validator.validate_and_store(allocation)
        validator.validate_and_store(payment)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.supplier_payment.update",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="supplier_payment",
            entity_id=str(payment.id),
            summary=f"Updated supplier payment {payment.payment_number or payment.id}",
            metadata={"status": payment.status.value if payment.status else None},
        )
        return payment

    def delete_payment(self, payment_id: int) -> None:
        """Soft delete a draft supplier payment and its allocations.

        Args:
            payment_id: The payment ID.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment is not a draft.
        """
        payment = (
            self.db.query(SupplierPayment)
            .filter(SupplierPayment.id == payment_id)
            .first()
        )
        if not payment:
            raise NotFoundError(f"Supplier payment {payment_id} not found")

        if payment.status != SupplierPaymentStatus.DRAFT:
            raise ValidationError("Can only delete draft payments")

        # Remove allocations first
        self.db.query(PaymentAllocation).filter(
            PaymentAllocation.supplier_payment_id == payment_id
        ).delete()

        payment.is_deleted = True
        payment.deleted_at = datetime.now(timezone.utc)
        payment.deleted_by_id = self.principal.id if self.principal else None

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.supplier_payment.delete",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="supplier_payment",
            entity_id=str(payment.id),
            summary=f"Deleted supplier payment {payment.payment_number or payment.id}",
        )

    # -------------------------------------------------------------------------
    # Allocations
    # -------------------------------------------------------------------------

    def add_allocations(
        self, payment_id: int, allocations: List[APAllocationData]
    ) -> SupplierPayment:
        """Add allocations to an existing supplier payment.

        Args:
            payment_id: The payment ID.
            allocations: List of allocations to add.

        Returns:
            The updated SupplierPayment.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If allocation fails or status invalid.
        """
        payment = self.get_payment(payment_id)

        if payment.status not in [
            SupplierPaymentStatus.DRAFT,
            SupplierPaymentStatus.SUBMITTED,
        ]:
            raise ValidationError("Cannot allocate on this payment status")

        self._process_allocations(payment_id, allocations)
        self.db.refresh(payment)
        validator = SoftValidationService(self.db)
        for allocation in self.get_payment_allocations(payment.id):
            validator.validate_and_store(allocation)
        validator.validate_and_store(payment)
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="finance.supplier_payment.allocate",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="supplier_payment",
            entity_id=str(payment.id),
            summary=f"Allocated supplier payment {payment.payment_number or payment.id}",
            metadata={"allocation_count": len(allocations)},
        )
        return payment

    def remove_allocation(self, payment_id: int, allocation_id: int) -> None:
        """Remove an allocation from a supplier payment.

        Args:
            payment_id: The payment ID.
            allocation_id: The allocation ID to remove.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If status invalid or allocation fails.
        """
        payment = self.get_payment(payment_id)

        if payment.status not in [
            SupplierPaymentStatus.DRAFT,
            SupplierPaymentStatus.SUBMITTED,
        ]:
            raise ValidationError("Cannot modify allocations on this payment status")

        alloc_service = PaymentAllocationService(self.db)
        try:
            alloc_service.remove_allocation(
                allocation_id, self.principal.id if self.principal else None
            )
        except PaymentAllocationError as e:
            raise ValidationError(str(e)) from e

    def _process_allocations(
        self, payment_id: int, allocations: List[APAllocationData]
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
                is_supplier_payment=True,
            )
        except PaymentAllocationError as e:
            raise ValidationError(str(e)) from e

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------

    def submit_payment(self, payment_id: int) -> SupplierPayment:
        """Submit a supplier payment for approval.

        Args:
            payment_id: The payment ID.

        Returns:
            The updated SupplierPayment with approval info.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment is not a draft or submission fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        payment = self.get_payment(payment_id)

        if payment.status != SupplierPaymentStatus.DRAFT:
            raise ValidationError("Can only submit draft payments")

        engine = ApprovalEngine(self.db)
        try:
            engine.submit_document(
                doctype="supplier_payment",
                document_id=payment_id,
                user_id=self.principal.id if self.principal else None,
                amount=payment.paid_amount,
                document_name=payment.payment_number,
            )
            payment.status = SupplierPaymentStatus.SUBMITTED
            payment.workflow_status = "pending_approval"
            return payment
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def approve_payment(
        self, payment_id: int, remarks: Optional[str] = None
    ) -> SupplierPayment:
        """Approve a supplier payment.

        Args:
            payment_id: The payment ID.
            remarks: Optional approval remarks.

        Returns:
            The approved SupplierPayment.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If approval fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        payment = self.get_payment(payment_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.approve_document(
                doctype="supplier_payment",
                document_id=payment_id,
                user_id=self.principal.id if self.principal else None,
                remarks=remarks,
            )
            payment.status = SupplierPaymentStatus.APPROVED
            payment.workflow_status = "approved"
            activity_logger = ActivityLogger(self.db)
            activity_logger.log(
                action="finance.supplier_payment.approve",
                user_id=self.principal.id if self.principal else None,
                user_email=getattr(self.principal, "email", None),
                entity_type="supplier_payment",
                entity_id=str(payment.id),
                summary=f"Approved supplier payment {payment.payment_number or payment.id}",
                metadata={"remarks": remarks},
            )
            return payment
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def reject_payment(self, payment_id: int, reason: str) -> SupplierPayment:
        """Reject a supplier payment.

        Args:
            payment_id: The payment ID.
            reason: Rejection reason.

        Returns:
            The rejected SupplierPayment (back to draft).

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If rejection fails.
        """
        from app.services.approval_engine import ApprovalEngine, ApprovalError

        payment = self.get_payment(payment_id)

        engine = ApprovalEngine(self.db)
        try:
            engine.reject_document(
                doctype="supplier_payment",
                document_id=payment_id,
                user_id=self.principal.id if self.principal else None,
                reason=reason,
            )
            payment.status = SupplierPaymentStatus.DRAFT
            payment.workflow_status = "rejected"
            activity_logger = ActivityLogger(self.db)
            activity_logger.log(
                action="finance.supplier_payment.reject",
                user_id=self.principal.id if self.principal else None,
                user_email=getattr(self.principal, "email", None),
                entity_type="supplier_payment",
                entity_id=str(payment.id),
                summary=f"Rejected supplier payment {payment.payment_number or payment.id}",
                metadata={"reason": reason},
            )
            return payment
        except ApprovalError as e:
            raise ValidationError(str(e)) from e

    def post_payment(self, payment_id: int) -> SupplierPayment:
        """Post an approved supplier payment to the GL.

        Args:
            payment_id: The payment ID.

        Returns:
            The posted SupplierPayment with journal_entry_id set.

        Raises:
            NotFoundError: If payment not found.
            ValidationError: If payment not approved or posting fails.
        """
        from app.services.document_posting import DocumentPostingService, PostingError

        payment = self.get_payment(payment_id)

        if payment.status != SupplierPaymentStatus.APPROVED:
            raise ValidationError("Can only post approved payments")

        posting_service = DocumentPostingService(self.db)
        try:
            je = posting_service.post_supplier_payment(
                payment_id, self.principal.id if self.principal else None
            )
            payment.status = SupplierPaymentStatus.POSTED
            payment.workflow_status = "posted"
            payment.journal_entry_id = je.id
            activity_logger = ActivityLogger(self.db)
            activity_logger.log(
                action="finance.supplier_payment.post",
                user_id=self.principal.id if self.principal else None,
                user_email=getattr(self.principal, "email", None),
                entity_type="supplier_payment",
                entity_id=str(payment.id),
                summary=f"Posted supplier payment {payment.payment_number or payment.id}",
                metadata={"journal_entry_id": je.id},
            )
            return payment
        except PostingError as e:
            raise ValidationError(str(e)) from e
