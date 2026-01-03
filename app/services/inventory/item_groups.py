"""Item group service - business logic for item group management.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.models.sales import ItemGroup
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    ItemGroupFilters,
    ItemGroupCreateData,
    ItemGroupUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ItemGroupService"]


class ItemGroupService:
    """Service for item group business logic.

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

    def list_item_groups(
        self,
        filters: Optional[ItemGroupFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ItemGroup]:
        """List item groups with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing item groups and total count.
        """
        if filters is None:
            filters = ItemGroupFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ItemGroup)

        # Search
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(ItemGroup.item_group_name.ilike(search_term))

        # Filters
        if filters.parent_item_group is not None:
            query = query.filter(ItemGroup.parent_item_group == filters.parent_item_group)
        if filters.is_group is not None:
            query = query.filter(ItemGroup.is_group == filters.is_group)

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(ItemGroup, filters.sort_by, ItemGroup.item_group_name)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_item_group(self, group_id: int) -> ItemGroup:
        """Get an item group by ID.

        Args:
            group_id: The item group ID.

        Returns:
            The ItemGroup object.

        Raises:
            NotFoundError: If item group not found.
        """
        group = self.db.query(ItemGroup).filter(ItemGroup.id == group_id).first()
        if not group:
            raise NotFoundError(f"Item group {group_id} not found")
        return group

    def get_item_group_by_name(self, group_name: str) -> Optional[ItemGroup]:
        """Get an item group by name.

        Args:
            group_name: The item group name.

        Returns:
            The ItemGroup object if found, None otherwise.
        """
        return (
            self.db.query(ItemGroup)
            .filter(ItemGroup.item_group_name == group_name)
            .first()
        )

    def get_root_groups(self) -> List[ItemGroup]:
        """Get all root item groups (no parent).

        Returns:
            List of root item groups.
        """
        return (
            self.db.query(ItemGroup)
            .filter(
                or_(
                    ItemGroup.parent_item_group.is_(None),
                    ItemGroup.parent_item_group == "",
                )
            )
            .order_by(ItemGroup.item_group_name)
            .all()
        )

    def get_child_groups(self, parent_name: str) -> List[ItemGroup]:
        """Get child item groups for a parent.

        Args:
            parent_name: The parent item group name.

        Returns:
            List of child item groups.
        """
        return (
            self.db.query(ItemGroup)
            .filter(ItemGroup.parent_item_group == parent_name)
            .order_by(ItemGroup.item_group_name)
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_item_group(self, data: ItemGroupCreateData) -> ItemGroup:
        """Create a new item group.

        Args:
            data: Item group creation data.

        Returns:
            The newly created ItemGroup.

        Raises:
            ConflictError: If item group name already exists.
            ValidationError: If parent group doesn't exist.
        """
        # Check for duplicate name
        existing = self.get_item_group_by_name(data.item_group_name)
        if existing:
            raise ConflictError(f"Item group '{data.item_group_name}' already exists")

        # Validate parent if specified
        if data.parent_item_group:
            parent = self.get_item_group_by_name(data.parent_item_group)
            if not parent:
                raise ValidationError(f"Parent item group '{data.parent_item_group}' not found")

        group = ItemGroup(
            item_group_name=data.item_group_name,
            parent_item_group=data.parent_item_group,
            is_group=data.is_group,
            lft=data.lft or 0,
            rgt=data.rgt or 0,
        )
        self.db.add(group)
        self.db.flush()

        return group

    def update_item_group(self, group_id: int, data: ItemGroupUpdateData) -> ItemGroup:
        """Update an existing item group.

        Args:
            group_id: The item group ID.
            data: Update data (only non-None fields are applied).

        Returns:
            The updated ItemGroup.

        Raises:
            NotFoundError: If item group not found.
            ConflictError: If new name conflicts with existing group.
            ValidationError: If parent group doesn't exist or creates a cycle.
        """
        group = self.get_item_group(group_id)

        if data.item_group_name is not None:
            # Check for duplicate name
            existing = self.get_item_group_by_name(data.item_group_name)
            if existing and existing.id != group_id:
                raise ConflictError(f"Item group '{data.item_group_name}' already exists")
            group.item_group_name = data.item_group_name

        if data.parent_item_group is not None:
            if data.parent_item_group:
                # Can't be its own parent
                if data.parent_item_group == group.item_group_name:
                    raise ValidationError("Item group cannot be its own parent")
                # Validate parent exists
                parent = self.get_item_group_by_name(data.parent_item_group)
                if not parent:
                    raise ValidationError(f"Parent item group '{data.parent_item_group}' not found")
            group.parent_item_group = data.parent_item_group or None

        if data.is_group is not None:
            group.is_group = data.is_group

        if data.lft is not None:
            group.lft = data.lft

        if data.rgt is not None:
            group.rgt = data.rgt

        self.db.flush()
        return group

    def delete_item_group(self, group_id: int) -> None:
        """Delete an item group.

        Cannot delete if:
        - Has child groups
        - Has items assigned

        Args:
            group_id: The item group ID.

        Raises:
            NotFoundError: If item group not found.
            ValidationError: If item group cannot be deleted.
        """
        from app.models.sales import Item

        group = self.get_item_group(group_id)

        # Check for child groups
        children = (
            self.db.query(ItemGroup)
            .filter(ItemGroup.parent_item_group == group.item_group_name)
            .count()
        )
        if children > 0:
            raise ValidationError(
                f"Cannot delete item group '{group.item_group_name}' - has {children} child group(s)"
            )

        # Check for items in this group
        items = (
            self.db.query(Item)
            .filter(Item.item_group == group.item_group_name)
            .count()
        )
        if items > 0:
            raise ValidationError(
                f"Cannot delete item group '{group.item_group_name}' - has {items} item(s)"
            )

        self.db.delete(group)
        self.db.flush()
