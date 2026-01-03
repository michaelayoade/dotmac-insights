"""Payment Modes service.

This module contains business logic for payment modes (cash, bank, etc.).
All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.models.accounting import ModeOfPayment, PaymentModeType
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .payment_modes_types import (
    PaymentModeFilters,
    PaymentModeCreateData,
    PaymentModeUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["PaymentModeService"]

# Allowed sort fields
ALLOWED_SORTS = {"mode_of_payment", "type", "id", "enabled"}


class PaymentModeService:
    """Service for payment mode business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def list_payment_modes(
        self,
        filters: Optional[PaymentModeFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ModeOfPayment]:
        """List payment modes with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing payment modes and total count.
        """
        if filters is None:
            filters = PaymentModeFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ModeOfPayment)
        query = scoped_query(query, self.principal)

        # Apply filters
        if not filters.include_disabled:
            query = query.filter(ModeOfPayment.enabled == True)  # noqa: E712

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(ModeOfPayment.mode_of_payment.ilike(search_pattern))

        if filters.mode_type:
            query = query.filter(ModeOfPayment.type == filters.mode_type)

        # Apply sorting
        sort_field = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "mode_of_payment"
        sort_column = getattr(ModeOfPayment, sort_field, ModeOfPayment.mode_of_payment)
        if filters.sort_dir == "desc":
            query = query.order_by(sort_column.desc(), ModeOfPayment.id.desc())
        else:
            query = query.order_by(sort_column.asc(), ModeOfPayment.id.asc())

        return paginate(query, pagination)

    def get_payment_mode(self, mode_id: int) -> ModeOfPayment:
        """Get payment mode by ID.

        Args:
            mode_id: The payment mode ID.

        Returns:
            The ModeOfPayment object.

        Raises:
            NotFoundError: If payment mode not found.
        """
        mode = (
            self.db.query(ModeOfPayment)
            .filter(ModeOfPayment.id == mode_id)
            .first()
        )
        if not mode:
            raise NotFoundError(f"Mode of payment {mode_id} not found")
        return mode

    def get_payment_mode_by_name(self, mode_of_payment: str) -> Optional[ModeOfPayment]:
        """Get payment mode by name.

        Args:
            mode_of_payment: The mode name.

        Returns:
            The ModeOfPayment object or None if not found.
        """
        return (
            self.db.query(ModeOfPayment)
            .filter(ModeOfPayment.mode_of_payment == mode_of_payment)
            .first()
        )

    def validate_mode_type(self, type_str: str) -> PaymentModeType:
        """Validate and convert mode type string to enum.

        Args:
            type_str: The type string (case-insensitive).

        Returns:
            The PaymentModeType enum value.

        Raises:
            ValidationError: If type is invalid.
        """
        try:
            return PaymentModeType(type_str.lower())
        except ValueError:
            valid_types = [t.value for t in PaymentModeType]
            raise ValidationError(
                f"Invalid payment mode type: {type_str}. "
                f"Valid types: {', '.join(valid_types)}"
            )

    def create_payment_mode(self, data: PaymentModeCreateData) -> ModeOfPayment:
        """Create a new payment mode.

        Args:
            data: Payment mode creation data.

        Returns:
            The created ModeOfPayment (not yet committed).

        Raises:
            ValidationError: If mode name already exists.
        """
        # Check for duplicate
        existing = self.get_payment_mode_by_name(data.mode_of_payment)
        if existing:
            raise ValidationError(
                f"Payment mode '{data.mode_of_payment}' already exists"
            )

        mode = ModeOfPayment(
            mode_of_payment=data.mode_of_payment,
            type=data.mode_type,
            enabled=data.enabled,
        )
        self.db.add(mode)
        self.db.flush()

        return mode

    def update_payment_mode(
        self, mode_id: int, data: PaymentModeUpdateData
    ) -> ModeOfPayment:
        """Update a payment mode.

        Args:
            mode_id: The payment mode ID.
            data: Fields to update.

        Returns:
            The updated ModeOfPayment (not yet committed).

        Raises:
            NotFoundError: If payment mode not found.
            ValidationError: If mode name already exists.
        """
        mode = self.get_payment_mode(mode_id)

        if data.mode_of_payment is not None:
            # Check for duplicate
            existing = (
                self.db.query(ModeOfPayment)
                .filter(
                    ModeOfPayment.mode_of_payment == data.mode_of_payment,
                    ModeOfPayment.id != mode_id,
                )
                .first()
            )
            if existing:
                raise ValidationError(
                    f"Payment mode '{data.mode_of_payment}' already exists"
                )
            mode.mode_of_payment = data.mode_of_payment

        if data.mode_type is not None:
            mode.type = data.mode_type

        if data.enabled is not None:
            mode.enabled = data.enabled

        return mode

    def disable_payment_mode(self, mode_id: int) -> ModeOfPayment:
        """Disable (soft delete) a payment mode.

        Args:
            mode_id: The payment mode ID.

        Returns:
            The updated ModeOfPayment.

        Raises:
            NotFoundError: If payment mode not found.
        """
        mode = self.get_payment_mode(mode_id)
        mode.enabled = False
        return mode

    def enable_payment_mode(self, mode_id: int) -> ModeOfPayment:
        """Enable a payment mode.

        Args:
            mode_id: The payment mode ID.

        Returns:
            The updated ModeOfPayment.

        Raises:
            NotFoundError: If payment mode not found.
        """
        mode = self.get_payment_mode(mode_id)
        mode.enabled = True
        return mode

    def delete_payment_mode(self, mode_id: int) -> None:
        """Hard delete a payment mode.

        Note: Consider using disable_payment_mode for soft delete instead.

        Args:
            mode_id: The payment mode ID.

        Raises:
            NotFoundError: If payment mode not found.
        """
        mode = self.get_payment_mode(mode_id)
        self.db.delete(mode)
