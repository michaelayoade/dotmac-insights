"""Item service - business logic for item (product) management.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc, func
from sqlalchemy.orm import Session

from app.models.sales import Item, ItemGroup
from app.models.inventory import StockLedgerEntry
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    ItemFilters,
    ItemCreateData,
    ItemUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ItemService"]


class ItemService:
    """Service for item business logic.

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

    def list_items(
        self,
        filters: Optional[ItemFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Item]:
        """List items with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing items and total count.
        """
        if filters is None:
            filters = ItemFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Item)

        # Search
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Item.item_code.ilike(search_term),
                    Item.item_name.ilike(search_term),
                    Item.description.ilike(search_term),
                )
            )

        # Filters
        if filters.item_group:
            query = query.filter(Item.item_group == filters.item_group)
        if filters.status:
            query = query.filter(Item.status == filters.status)
        if filters.is_stock_item is not None:
            query = query.filter(Item.is_stock_item == filters.is_stock_item)

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(Item, filters.sort_by, Item.item_name)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_item(self, item_id: int) -> Item:
        """Get an item by ID.

        Args:
            item_id: The item ID.

        Returns:
            The Item object.

        Raises:
            NotFoundError: If item not found.
        """
        item = self.db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise NotFoundError(f"Item {item_id} not found")
        return item

    def get_item_by_code(self, item_code: str) -> Optional[Item]:
        """Get an item by code.

        Args:
            item_code: The item code.

        Returns:
            The Item object if found, None otherwise.
        """
        return self.db.query(Item).filter(Item.item_code == item_code).first()

    def get_items_by_group(self, item_group: str) -> List[Item]:
        """Get all items in an item group.

        Args:
            item_group: The item group name.

        Returns:
            List of items in the group.
        """
        return (
            self.db.query(Item)
            .filter(Item.item_group == item_group)
            .order_by(Item.item_name)
            .all()
        )

    def get_stock_items(self) -> List[Item]:
        """Get all stock items (is_stock_item=True).

        Returns:
            List of stock items.
        """
        return (
            self.db.query(Item)
            .filter(Item.is_stock_item == True, Item.status == "active")
            .order_by(Item.item_name)
            .all()
        )

    def get_item_stock_qty(self, item_code: str, warehouse: Optional[str] = None) -> Decimal:
        """Get current stock quantity for an item.

        Args:
            item_code: The item code.
            warehouse: Optional warehouse to filter by.

        Returns:
            Total stock quantity.
        """
        query = self.db.query(func.sum(StockLedgerEntry.actual_qty)).filter(
            StockLedgerEntry.item_code == item_code
        )
        if warehouse:
            query = query.filter(StockLedgerEntry.warehouse == warehouse)

        result = query.scalar()
        return Decimal(str(result or 0))

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_item(self, data: ItemCreateData) -> Item:
        """Create a new item.

        Args:
            data: Item creation data.

        Returns:
            The newly created Item.

        Raises:
            ConflictError: If item code already exists.
            ValidationError: If item group doesn't exist.
        """
        # Check for duplicate code
        existing = self.get_item_by_code(data.item_code)
        if existing:
            raise ConflictError(f"Item with code '{data.item_code}' already exists")

        # Validate item group if specified
        if data.item_group:
            group = (
                self.db.query(ItemGroup)
                .filter(ItemGroup.item_group_name == data.item_group)
                .first()
            )
            if not group:
                raise ValidationError(f"Item group '{data.item_group}' not found")

        item = Item(
            item_code=data.item_code,
            item_name=data.item_name,
            description=data.description,
            item_group=data.item_group,
            uom=data.uom,
            default_warehouse=data.default_warehouse,
            valuation_rate=data.valuation_rate or Decimal("0"),
            standard_selling_rate=data.standard_selling_rate or Decimal("0"),
            is_stock_item=data.is_stock_item,
            status=data.status,
        )
        self.db.add(item)
        self.db.flush()

        return item

    def update_item(self, item_id: int, data: ItemUpdateData) -> Item:
        """Update an existing item.

        Args:
            item_id: The item ID.
            data: Update data (only non-None fields are applied).

        Returns:
            The updated Item.

        Raises:
            NotFoundError: If item not found.
            ValidationError: If item group doesn't exist.
        """
        item = self.get_item(item_id)

        if data.item_name is not None:
            item.item_name = data.item_name

        if data.description is not None:
            item.description = data.description

        if data.item_group is not None:
            if data.item_group:
                group = (
                    self.db.query(ItemGroup)
                    .filter(ItemGroup.item_group_name == data.item_group)
                    .first()
                )
                if not group:
                    raise ValidationError(f"Item group '{data.item_group}' not found")
            item.item_group = data.item_group or None

        if data.uom is not None:
            item.uom = data.uom

        if data.default_warehouse is not None:
            item.default_warehouse = data.default_warehouse or None

        if data.valuation_rate is not None:
            item.valuation_rate = data.valuation_rate

        if data.standard_selling_rate is not None:
            item.standard_selling_rate = data.standard_selling_rate

        if data.is_stock_item is not None:
            item.is_stock_item = data.is_stock_item

        if data.status is not None:
            item.status = data.status

        item.updated_at = datetime.utcnow()
        self.db.flush()
        return item

    def delete_item(self, item_id: int) -> None:
        """Delete an item.

        Cannot delete if item has stock transactions.

        Args:
            item_id: The item ID.

        Raises:
            NotFoundError: If item not found.
            ValidationError: If item has stock transactions.
        """
        item = self.get_item(item_id)

        # Check for stock ledger entries
        entries = (
            self.db.query(StockLedgerEntry)
            .filter(StockLedgerEntry.item_code == item.item_code)
            .count()
        )
        if entries > 0:
            raise ValidationError(
                f"Cannot delete item '{item.item_code}' - has {entries} stock transaction(s)"
            )

        self.db.delete(item)
        self.db.flush()

    def deactivate_item(self, item_id: int) -> Item:
        """Deactivate an item (set status to inactive).

        Args:
            item_id: The item ID.

        Returns:
            The updated Item.

        Raises:
            NotFoundError: If item not found.
        """
        item = self.get_item(item_id)
        item.status = "inactive"
        item.updated_at = datetime.utcnow()
        self.db.flush()
        return item

    def activate_item(self, item_id: int) -> Item:
        """Activate an item (set status to active).

        Args:
            item_id: The item ID.

        Returns:
            The updated Item.

        Raises:
            NotFoundError: If item not found.
        """
        item = self.get_item(item_id)
        item.status = "active"
        item.updated_at = datetime.utcnow()
        self.db.flush()
        return item
