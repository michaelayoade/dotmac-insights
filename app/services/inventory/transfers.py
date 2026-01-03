"""Transfer request service - business logic for warehouse transfers.

This service encapsulates transfer request workflow:
- Transfer request creation
- Approval workflow
- Transfer execution (creates stock entries)

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc, func
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import (
    TransferRequest,
    TransferRequestItem,
    TransferStatus,
    StockEntry,
)

from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    TransferFilters,
    TransferCreateData,
    TransferItemData,
    TransferApprovalData,
)
from .stock_entries import StockEntryService

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TransferRequestService"]


class TransferRequestService:
    """Service for transfer request business logic.

    Handles transfer request workflow from creation to completion.

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

    def list_transfers(
        self,
        filters: Optional[TransferFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[TransferRequest]:
        """List transfer requests with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing requests and total count.
        """
        filters = filters or TransferFilters()
        pagination = pagination or PaginationParams()

        query = (
            self.db.query(TransferRequest)
            .filter(TransferRequest.is_deleted == False)
        )

        # Search
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                or_(
                    TransferRequest.from_warehouse.ilike(search),
                    TransferRequest.to_warehouse.ilike(search),
                    TransferRequest.remarks.ilike(search),
                )
            )

        # Filters
        if filters.status:
            query = query.filter(TransferRequest.status == filters.status)
        if filters.from_warehouse:
            query = query.filter(TransferRequest.from_warehouse == filters.from_warehouse)
        if filters.to_warehouse:
            query = query.filter(TransferRequest.to_warehouse == filters.to_warehouse)
        if filters.from_date:
            query = query.filter(func.date(TransferRequest.request_date) >= filters.from_date)
        if filters.to_date:
            query = query.filter(func.date(TransferRequest.request_date) <= filters.to_date)
        if filters.requested_by_id:
            query = query.filter(TransferRequest.requested_by_id == filters.requested_by_id)

        # Count total
        total = query.count()

        # Sorting
        sort_col = getattr(TransferRequest, filters.sort_by, TransferRequest.request_date)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_transfer(self, transfer_id: int, include_items: bool = True) -> TransferRequest:
        """Get a single transfer request by ID.

        Args:
            transfer_id: The transfer request ID.
            include_items: Whether to eagerly load line items.

        Returns:
            The TransferRequest object.

        Raises:
            NotFoundError: If request not found.
        """
        query = self.db.query(TransferRequest).filter(
            TransferRequest.id == transfer_id,
            TransferRequest.is_deleted == False,
        )

        if include_items:
            query = query.options(selectinload(TransferRequest.items))

        transfer = query.first()
        if not transfer:
            raise NotFoundError(f"Transfer request {transfer_id} not found")
        return transfer

    def get_pending_approvals(self) -> List[TransferRequest]:
        """Get transfer requests pending approval.

        Returns:
            List of pending TransferRequest objects.
        """
        return (
            self.db.query(TransferRequest)
            .filter(
                TransferRequest.status == TransferStatus.PENDING_APPROVAL,
                TransferRequest.is_deleted == False,
            )
            .options(selectinload(TransferRequest.items))
            .order_by(TransferRequest.request_date)
            .all()
        )

    def get_in_transit_transfers(self) -> List[TransferRequest]:
        """Get transfers currently in transit.

        Returns:
            List of in-transit TransferRequest objects.
        """
        return (
            self.db.query(TransferRequest)
            .filter(
                TransferRequest.status == TransferStatus.IN_TRANSIT,
                TransferRequest.is_deleted == False,
            )
            .options(selectinload(TransferRequest.items))
            .order_by(TransferRequest.transfer_date)
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_transfer(self, data: TransferCreateData) -> TransferRequest:
        """Create a new transfer request.

        Args:
            data: Transfer creation data.

        Returns:
            The created TransferRequest.

        Raises:
            ValidationError: If validation fails.
        """
        if not data.from_warehouse or not data.to_warehouse:
            raise ValidationError("Source and target warehouse are required")
        if data.from_warehouse == data.to_warehouse:
            raise ValidationError("Source and target warehouse cannot be the same")
        if not data.items:
            raise ValidationError("At least one item is required")

        # Calculate totals
        total_qty = sum(item.qty for item in data.items)

        transfer = TransferRequest(
            from_warehouse=data.from_warehouse,
            to_warehouse=data.to_warehouse,
            company=data.company,
            required_date=data.required_date,
            remarks=data.remarks,
            total_qty=total_qty,
            total_value=Decimal("0"),  # Will be calculated
            status=TransferStatus.DRAFT,
        )

        if self.principal:
            transfer.requested_by_id = self.principal.id
            transfer.created_by_id = self.principal.id

        self.db.add(transfer)
        self.db.flush()

        # Create line items
        for idx, item_data in enumerate(data.items):
            item = TransferRequestItem(
                transfer_id=transfer.id,
                item_code=item_data.item_code,
                item_name=item_data.item_name,
                description=item_data.description,
                qty=item_data.qty,
                uom=item_data.uom,
                batch_no=item_data.batch_no,
                serial_no=item_data.serial_no,
                idx=idx,
            )
            self.db.add(item)

        self.db.flush()

        return transfer

    def submit_for_approval(self, transfer_id: int) -> TransferRequest:
        """Submit a transfer request for approval.

        Args:
            transfer_id: The transfer request ID.

        Returns:
            The updated TransferRequest.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If not in draft status.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status != TransferStatus.DRAFT:
            raise ValidationError("Only draft requests can be submitted for approval")

        transfer.status = TransferStatus.PENDING_APPROVAL
        transfer.updated_at = datetime.utcnow()

        if self.principal:
            transfer.updated_by_id = self.principal.id

        self.db.flush()

        return transfer

    def approve_transfer(self, transfer_id: int, data: TransferApprovalData) -> TransferRequest:
        """Approve or reject a transfer request.

        Args:
            transfer_id: The transfer request ID.
            data: Approval data.

        Returns:
            The updated TransferRequest.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If not pending approval.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status != TransferStatus.PENDING_APPROVAL:
            raise ValidationError("Only pending requests can be approved/rejected")

        if data.approved:
            transfer.status = TransferStatus.APPROVED
        else:
            transfer.status = TransferStatus.REJECTED
            transfer.rejection_reason = data.rejection_reason

        transfer.approved_at = datetime.utcnow()
        if self.principal:
            transfer.approved_by_id = self.principal.id
            transfer.updated_by_id = self.principal.id

        self.db.flush()

        return transfer

    def execute_transfer(self, transfer_id: int) -> TransferRequest:
        """Execute an approved transfer (create stock entries).

        Creates outbound and inbound stock entries.

        Args:
            transfer_id: The transfer request ID.

        Returns:
            The updated TransferRequest.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If not in approved status.
        """
        transfer = self.get_transfer(transfer_id, include_items=True)

        if transfer.status != TransferStatus.APPROVED:
            raise ValidationError("Only approved requests can be executed")

        # Create stock entry service
        stock_service = StockEntryService(self.db, self.principal)

        # Create outbound stock entry (from source warehouse)
        from .types import StockEntryCreateData, StockEntryItemData

        outbound_items = [
            StockEntryItemData(
                item_code=item.item_code,
                qty=item.qty,
                item_name=item.item_name,
                uom=item.uom,
                s_warehouse=transfer.from_warehouse,
                t_warehouse=transfer.to_warehouse,
                batch_no=item.batch_no,
                serial_no=item.serial_no,
            )
            for item in transfer.items
        ]

        outbound_data = StockEntryCreateData(
            stock_entry_type="Material Transfer",
            posting_date=date.today(),
            from_warehouse=transfer.from_warehouse,
            to_warehouse=transfer.to_warehouse,
            company=transfer.company,
            purpose="Material Transfer",
            remarks=f"Transfer Request #{transfer.id}",
            items=outbound_items,
        )

        outbound_entry = stock_service.create_entry(outbound_data)
        outbound_entry = stock_service.submit_entry(outbound_entry.id)

        transfer.outbound_stock_entry_id = outbound_entry.id
        transfer.status = TransferStatus.IN_TRANSIT
        transfer.transfer_date = datetime.utcnow()
        transfer.updated_at = datetime.utcnow()

        if self.principal:
            transfer.updated_by_id = self.principal.id

        self.db.flush()

        return transfer

    def complete_transfer(self, transfer_id: int) -> TransferRequest:
        """Mark a transfer as completed (goods received).

        Args:
            transfer_id: The transfer request ID.

        Returns:
            The updated TransferRequest.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If not in transit.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ValidationError("Only in-transit transfers can be completed")

        transfer.status = TransferStatus.COMPLETED
        transfer.updated_at = datetime.utcnow()

        if self.principal:
            transfer.updated_by_id = self.principal.id

        self.db.flush()

        return transfer

    def cancel_transfer(self, transfer_id: int, reason: Optional[str] = None) -> TransferRequest:
        """Cancel a transfer request.

        Args:
            transfer_id: The transfer request ID.
            reason: Optional cancellation reason.

        Returns:
            The updated TransferRequest.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If transfer cannot be cancelled.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status in [TransferStatus.COMPLETED, TransferStatus.CANCELLED]:
            raise ValidationError(f"Cannot cancel {transfer.status.value} transfer")

        # If in transit, we'd need to reverse stock entries
        if transfer.status == TransferStatus.IN_TRANSIT:
            # Cancel the outbound stock entry
            if transfer.outbound_stock_entry_id:
                stock_service = StockEntryService(self.db, self.principal)
                stock_service.cancel_entry(transfer.outbound_stock_entry_id)

        transfer.status = TransferStatus.CANCELLED
        if reason:
            transfer.rejection_reason = reason
        transfer.updated_at = datetime.utcnow()

        if self.principal:
            transfer.updated_by_id = self.principal.id

        self.db.flush()

        return transfer

    def delete_transfer(self, transfer_id: int) -> None:
        """Soft delete a transfer request.

        Only draft requests can be deleted.

        Args:
            transfer_id: The transfer request ID.

        Raises:
            NotFoundError: If request not found.
            ValidationError: If not in draft status.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status != TransferStatus.DRAFT:
            raise ValidationError("Only draft requests can be deleted")

        transfer.is_deleted = True
        transfer.deleted_at = datetime.utcnow()
        if self.principal:
            transfer.deleted_by_id = self.principal.id

        self.db.flush()

    # -------------------------------------------------------------------------
    # Aggregations
    # -------------------------------------------------------------------------

    def get_transfer_summary(self) -> dict:
        """Get summary of transfer requests by status.

        Returns:
            Dictionary with counts by status.
        """
        results = (
            self.db.query(TransferRequest.status, func.count(TransferRequest.id))
            .filter(TransferRequest.is_deleted == False)
            .group_by(TransferRequest.status)
            .all()
        )

        by_status = {status.value: count for status, count in results}
        total = sum(by_status.values())

        return {
            "total": total,
            "by_status": by_status,
            "pending_approval": by_status.get("pending_approval", 0),
            "in_transit": by_status.get("in_transit", 0),
        }
