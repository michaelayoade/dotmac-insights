"""Batch service - business logic for batch tracking and management.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc, func
from sqlalchemy.orm import Session

from app.models.inventory import Batch, StockLedgerEntry
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import BatchFilters, BatchCreateData

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["BatchService"]


class BatchService:
    """Service for batch tracking business logic.

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

    def list_batches(
        self,
        filters: Optional[BatchFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Batch]:
        """List batches with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing batches and total count.
        """
        if filters is None:
            filters = BatchFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Batch)

        # Search
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Batch.batch_id.ilike(search_term),
                    Batch.item_code.ilike(search_term),
                    Batch.item_name.ilike(search_term),
                )
            )

        # Filters
        if filters.item_code:
            query = query.filter(Batch.item_code == filters.item_code)

        if filters.has_expiry is not None:
            if filters.has_expiry:
                query = query.filter(Batch.expiry_date.isnot(None))
            else:
                query = query.filter(Batch.expiry_date.is_(None))

        if filters.expired is not None:
            today = date.today()
            if filters.expired:
                query = query.filter(Batch.expiry_date < today)
            else:
                query = query.filter(
                    or_(
                        Batch.expiry_date.is_(None),
                        Batch.expiry_date >= today,
                    )
                )

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(Batch, filters.sort_by, Batch.batch_id)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_batch(self, batch_id: int) -> Batch:
        """Get a batch by ID.

        Args:
            batch_id: The batch record ID.

        Returns:
            The Batch object.

        Raises:
            NotFoundError: If batch not found.
        """
        batch = self.db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise NotFoundError(f"Batch {batch_id} not found")
        return batch

    def get_batch_by_id_code(self, batch_id_code: str) -> Optional[Batch]:
        """Get a batch by its batch ID code.

        Args:
            batch_id_code: The batch ID code (e.g., "BATCH-001").

        Returns:
            The Batch object if found, None otherwise.
        """
        return self.db.query(Batch).filter(Batch.batch_id == batch_id_code).first()

    def get_batches_for_item(self, item_code: str, include_expired: bool = False) -> List[Batch]:
        """Get all batches for an item.

        Args:
            item_code: The item code.
            include_expired: Whether to include expired batches.

        Returns:
            List of batches for the item.
        """
        query = self.db.query(Batch).filter(
            Batch.item_code == item_code,
            Batch.disabled == False,
        )

        if not include_expired:
            today = date.today()
            query = query.filter(
                or_(
                    Batch.expiry_date.is_(None),
                    Batch.expiry_date >= today,
                )
            )

        return query.order_by(Batch.expiry_date.asc().nullslast()).all()

    def get_batch_stock(self, batch_id_code: str, warehouse: Optional[str] = None) -> Decimal:
        """Get current stock quantity for a batch.

        Args:
            batch_id_code: The batch ID code.
            warehouse: Optional warehouse to filter by.

        Returns:
            Total stock quantity for the batch.
        """
        query = self.db.query(func.sum(StockLedgerEntry.actual_qty)).filter(
            StockLedgerEntry.batch_no == batch_id_code
        )
        if warehouse:
            query = query.filter(StockLedgerEntry.warehouse == warehouse)

        result = query.scalar()
        return Decimal(str(result or 0))

    def get_expiring_batches(self, days_ahead: int = 30) -> List[Batch]:
        """Get batches expiring within the specified days.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of batches expiring soon.
        """
        from datetime import timedelta

        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        return (
            self.db.query(Batch)
            .filter(
                Batch.expiry_date.isnot(None),
                Batch.expiry_date >= today,
                Batch.expiry_date <= cutoff,
                Batch.disabled == False,
            )
            .order_by(Batch.expiry_date.asc())
            .all()
        )

    def get_expired_batches(self) -> List[Batch]:
        """Get all expired batches.

        Returns:
            List of expired batches.
        """
        today = date.today()

        return (
            self.db.query(Batch)
            .filter(
                Batch.expiry_date.isnot(None),
                Batch.expiry_date < today,
                Batch.disabled == False,
            )
            .order_by(Batch.expiry_date.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_batch(self, data: BatchCreateData) -> Batch:
        """Create a new batch.

        Args:
            data: Batch creation data.

        Returns:
            The newly created Batch.

        Raises:
            ConflictError: If batch ID already exists.
        """
        # Check for duplicate batch ID
        existing = self.get_batch_by_id_code(data.batch_id)
        if existing:
            raise ConflictError(f"Batch '{data.batch_id}' already exists")

        batch = Batch(
            batch_id=data.batch_id,
            item_code=data.item_code,
            expiry_date=data.expiry_date,
            manufacturing_date=data.manufacturing_date,
            batch_qty=data.batch_qty,
            reference_doctype=data.reference_doctype,
            reference_name=data.reference_name,
        )

        if self.principal:
            batch.created_by_id = self.principal.user_id

        self.db.add(batch)
        self.db.flush()
        return batch

    def update_batch(
        self,
        batch_id: int,
        expiry_date: Optional[date] = None,
        manufacturing_date: Optional[date] = None,
        description: Optional[str] = None,
    ) -> Batch:
        """Update a batch.

        Args:
            batch_id: The batch record ID.
            expiry_date: New expiry date (if provided).
            manufacturing_date: New manufacturing date (if provided).
            description: New description (if provided).

        Returns:
            The updated Batch.

        Raises:
            NotFoundError: If batch not found.
        """
        batch = self.get_batch(batch_id)

        if expiry_date is not None:
            batch.expiry_date = expiry_date
        if manufacturing_date is not None:
            batch.manufacturing_date = manufacturing_date
        if description is not None:
            batch.description = description

        batch.updated_at = datetime.utcnow()
        self.db.flush()
        return batch

    def disable_batch(self, batch_id: int) -> Batch:
        """Disable a batch.

        Args:
            batch_id: The batch record ID.

        Returns:
            The disabled Batch.

        Raises:
            NotFoundError: If batch not found.
        """
        batch = self.get_batch(batch_id)
        batch.disabled = True
        batch.updated_at = datetime.utcnow()
        self.db.flush()
        return batch

    def enable_batch(self, batch_id: int) -> Batch:
        """Enable a previously disabled batch.

        Args:
            batch_id: The batch record ID.

        Returns:
            The enabled Batch.

        Raises:
            NotFoundError: If batch not found.
        """
        batch = self.get_batch(batch_id)
        batch.disabled = False
        batch.updated_at = datetime.utcnow()
        self.db.flush()
        return batch
