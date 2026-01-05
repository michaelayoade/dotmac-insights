"""Landed cost voucher service - business logic for landed cost management.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import desc, asc
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import LandedCostVoucher, LandedCostItem, LandedCostTax
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService

from .types import (
    LandedCostFilters,
    LandedCostCreateData,
    LandedCostItemData,
    LandedCostTaxData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["LandedCostService"]


class LandedCostService:
    """Service for landed cost voucher business logic.

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

    def list_vouchers(
        self,
        filters: Optional[LandedCostFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[LandedCostVoucher]:
        """List landed cost vouchers with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing vouchers and total count.
        """
        if filters is None:
            filters = LandedCostFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(LandedCostVoucher).filter(
            LandedCostVoucher.is_deleted == False
        )

        # Filters
        if filters.from_date:
            query = query.filter(LandedCostVoucher.posting_date >= filters.from_date)
        if filters.to_date:
            query = query.filter(LandedCostVoucher.posting_date <= filters.to_date)
        if filters.company:
            query = query.filter(LandedCostVoucher.company == filters.company)
        if filters.docstatus is not None:
            query = query.filter(LandedCostVoucher.docstatus == filters.docstatus)

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(LandedCostVoucher, filters.sort_by, LandedCostVoucher.posting_date)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(
            items=query.all(),
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_voucher(
        self, voucher_id: int, include_details: bool = True
    ) -> LandedCostVoucher:
        """Get a landed cost voucher by ID.

        Args:
            voucher_id: The voucher ID.
            include_details: Whether to eagerly load items and taxes.

        Returns:
            The LandedCostVoucher object.

        Raises:
            NotFoundError: If voucher not found.
        """
        query = self.db.query(LandedCostVoucher).filter(
            LandedCostVoucher.id == voucher_id,
            LandedCostVoucher.is_deleted == False,
        )

        if include_details:
            query = query.options(
                selectinload(LandedCostVoucher.items),
                selectinload(LandedCostVoucher.taxes),
            )

        voucher = query.first()
        if not voucher:
            raise NotFoundError(f"Landed cost voucher {voucher_id} not found")
        return voucher

    def get_vouchers_for_receipt(self, purchase_receipt: str) -> List[LandedCostVoucher]:
        """Get all landed cost vouchers for a purchase receipt.

        Args:
            purchase_receipt: The purchase receipt reference.

        Returns:
            List of landed cost vouchers.
        """
        return (
            self.db.query(LandedCostVoucher)
            .filter(
                LandedCostVoucher.purchase_receipt == purchase_receipt,
                LandedCostVoucher.is_deleted == False,
            )
            .order_by(LandedCostVoucher.posting_date.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_voucher(self, data: LandedCostCreateData) -> LandedCostVoucher:
        """Create a new landed cost voucher.

        Args:
            data: Voucher creation data including items and taxes.

        Returns:
            The newly created LandedCostVoucher.

        Raises:
            ValidationError: If no items or taxes provided.
        """
        if not data.items:
            raise ValidationError("At least one item is required")
        if not data.taxes:
            raise ValidationError("At least one tax/charge is required")

        voucher = LandedCostVoucher(
            posting_date=data.posting_date,
            company=data.company,
            distribute_charges_based_on=data.distribute_charges_based_on,
            docstatus=0,  # Draft
            origin_system="local",
        )

        # Set audit fields
        if self.principal:
            voucher.created_by_id = self.principal.user_id

        self.db.add(voucher)
        self.db.flush()  # Get voucher ID

        # Add items
        for idx, item_data in enumerate(data.items):
            item = LandedCostItem(
                voucher_id=voucher.id,
                item_code=item_data.item_code,
                description=item_data.description,
                qty=item_data.qty,
                rate=item_data.rate,
                amount=item_data.amount,
                idx=idx,
            )
            self.db.add(item)
            SoftValidationService(self.db).validate_and_store(item)

        # Add taxes
        total_charges = Decimal("0")
        for idx, tax_data in enumerate(data.taxes):
            tax = LandedCostTax(
                voucher_id=voucher.id,
                expense_account=tax_data.expense_account,
                description=tax_data.description,
                amount=tax_data.amount,
                idx=idx,
            )
            self.db.add(tax)
            SoftValidationService(self.db).validate_and_store(tax)
            total_charges += tax_data.amount

        voucher.total_taxes_and_charges = total_charges

        # Distribute charges to items
        self._distribute_charges(voucher, data.items, data.taxes)

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(voucher)
        return voucher

    def _distribute_charges(
        self,
        voucher: LandedCostVoucher,
        items: List[LandedCostItemData],
        taxes: List[LandedCostTaxData],
    ) -> None:
        """Distribute landed costs to items based on distribution method.

        Args:
            voucher: The voucher to update items for.
            items: List of item data.
            taxes: List of tax data.
        """
        total_charges = sum(t.amount for t in taxes)
        if total_charges == Decimal("0"):
            return

        method = voucher.distribute_charges_based_on

        if method == "Qty":
            total_qty = sum(item.qty for item in items)
            if total_qty > 0:
                rate_per_unit = total_charges / total_qty
                for item in voucher.items:
                    item.applicable_charges = item.qty * rate_per_unit
        else:  # Amount (default)
            total_amount = sum(item.amount for item in items)
            if total_amount > 0:
                for item in voucher.items:
                    proportion = item.amount / total_amount
                    item.applicable_charges = total_charges * proportion

    def submit_voucher(self, voucher_id: int) -> LandedCostVoucher:
        """Submit a landed cost voucher.

        Args:
            voucher_id: The voucher ID.

        Returns:
            The submitted LandedCostVoucher.

        Raises:
            NotFoundError: If voucher not found.
            ValidationError: If voucher is not in draft status.
        """
        voucher = self.get_voucher(voucher_id)

        if voucher.docstatus != 0:
            raise ValidationError("Only draft vouchers can be submitted")

        if not voucher.items:
            raise ValidationError("Cannot submit voucher without items")
        if not voucher.taxes:
            raise ValidationError("Cannot submit voucher without taxes/charges")

        voucher.docstatus = 1
        voucher.updated_at = datetime.utcnow()
        if self.principal:
            voucher.updated_by_id = self.principal.user_id

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(voucher)
        return voucher

    def cancel_voucher(self, voucher_id: int) -> LandedCostVoucher:
        """Cancel a submitted landed cost voucher.

        Args:
            voucher_id: The voucher ID.

        Returns:
            The cancelled LandedCostVoucher.

        Raises:
            NotFoundError: If voucher not found.
            ValidationError: If voucher cannot be cancelled.
        """
        voucher = self.get_voucher(voucher_id)

        if voucher.docstatus != 1:
            raise ValidationError("Only submitted vouchers can be cancelled")

        voucher.docstatus = 2
        voucher.updated_at = datetime.utcnow()
        if self.principal:
            voucher.updated_by_id = self.principal.user_id

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(voucher)
        return voucher

    def delete_voucher(self, voucher_id: int) -> None:
        """Soft delete a landed cost voucher.

        Can only delete draft vouchers.

        Args:
            voucher_id: The voucher ID.

        Raises:
            NotFoundError: If voucher not found.
            ValidationError: If voucher cannot be deleted.
        """
        voucher = self.get_voucher(voucher_id)

        if voucher.docstatus != 0:
            raise ValidationError("Only draft vouchers can be deleted")

        voucher.is_deleted = True
        voucher.deleted_at = datetime.utcnow()
        if self.principal:
            voucher.deleted_by_id = self.principal.user_id

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(voucher)
