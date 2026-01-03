"""Warehouse service - business logic for warehouse management.

This service encapsulates all warehouse-related business logic:
- Warehouse CRUD operations
- Hierarchy management
- Stock location validation

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc, func
from sqlalchemy.orm import Session

from app.models.inventory import Warehouse

from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import WarehouseFilters, WarehouseCreateData, WarehouseUpdateData

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["WarehouseService"]


class WarehouseService:
    """Service for warehouse business logic.

    Handles warehouse CRUD operations and hierarchy management.

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

    def list_warehouses(
        self,
        filters: Optional[WarehouseFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Warehouse]:
        """List warehouses with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing warehouses and total count.
        """
        filters = filters or WarehouseFilters()
        pagination = pagination or PaginationParams()

        query = self.db.query(Warehouse)

        # Exclude deleted unless showing disabled
        if not filters.include_disabled:
            query = query.filter(Warehouse.is_deleted == False)
            query = query.filter(Warehouse.disabled == False)
        else:
            query = query.filter(Warehouse.is_deleted == False)

        # Search
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Warehouse.warehouse_name.ilike(search),
                    Warehouse.warehouse_type.ilike(search),
                    Warehouse.parent_warehouse.ilike(search),
                )
            )

        # Filters
        if filters.warehouse_type:
            query = query.filter(Warehouse.warehouse_type == filters.warehouse_type)
        if filters.parent_warehouse:
            query = query.filter(Warehouse.parent_warehouse == filters.parent_warehouse)
        if filters.company:
            query = query.filter(Warehouse.company == filters.company)
        if filters.is_group is not None:
            query = query.filter(Warehouse.is_group == filters.is_group)

        # Count total
        total = query.count()

        # Sorting
        sort_col = getattr(Warehouse, filters.sort_by, Warehouse.warehouse_name)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_warehouse(self, warehouse_id: int) -> Warehouse:
        """Get a single warehouse by ID.

        Args:
            warehouse_id: The warehouse ID.

        Returns:
            The Warehouse object.

        Raises:
            NotFoundError: If warehouse not found.
        """
        warehouse = (
            self.db.query(Warehouse)
            .filter(Warehouse.id == warehouse_id, Warehouse.is_deleted == False)
            .first()
        )
        if not warehouse:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return warehouse

    def get_warehouse_by_name(self, name: str) -> Optional[Warehouse]:
        """Get a warehouse by name.

        Args:
            name: The warehouse name.

        Returns:
            The Warehouse object or None if not found.
        """
        return (
            self.db.query(Warehouse)
            .filter(
                Warehouse.warehouse_name == name,
                Warehouse.is_deleted == False,
            )
            .first()
        )

    def get_child_warehouses(self, parent_name: str) -> List[Warehouse]:
        """Get all child warehouses of a parent.

        Args:
            parent_name: The parent warehouse name.

        Returns:
            List of child warehouses.
        """
        return (
            self.db.query(Warehouse)
            .filter(
                Warehouse.parent_warehouse == parent_name,
                Warehouse.is_deleted == False,
            )
            .order_by(Warehouse.warehouse_name)
            .all()
        )

    def get_root_warehouses(self) -> List[Warehouse]:
        """Get all root warehouses (no parent).

        Returns:
            List of root warehouses.
        """
        return (
            self.db.query(Warehouse)
            .filter(
                or_(
                    Warehouse.parent_warehouse.is_(None),
                    Warehouse.parent_warehouse == "",
                ),
                Warehouse.is_deleted == False,
            )
            .order_by(Warehouse.warehouse_name)
            .all()
        )

    def get_leaf_warehouses(self) -> List[Warehouse]:
        """Get all leaf warehouses (non-group warehouses).

        Returns:
            List of warehouses that can hold stock.
        """
        return (
            self.db.query(Warehouse)
            .filter(
                Warehouse.is_group == False,
                Warehouse.is_deleted == False,
                Warehouse.disabled == False,
            )
            .order_by(Warehouse.warehouse_name)
            .all()
        )

    def get_parent_warehouses(self) -> List[Warehouse]:
        """Get all group warehouses that can be parents.

        Returns:
            List of warehouses that are groups (can have children).
        """
        return (
            self.db.query(Warehouse)
            .filter(
                Warehouse.is_group == True,
                Warehouse.is_deleted == False,
                Warehouse.disabled == False,
            )
            .order_by(Warehouse.warehouse_name)
            .all()
        )

    def get_parent_warehouses_excluding(self, warehouse_id: int) -> List[Warehouse]:
        """Get all group warehouses excluding a specific one.

        Used for edit form dropdowns to prevent self-reference.

        Args:
            warehouse_id: Warehouse ID to exclude from results.

        Returns:
            List of group warehouses excluding the specified one.
        """
        return (
            self.db.query(Warehouse)
            .filter(
                Warehouse.is_group == True,
                Warehouse.is_deleted == False,
                Warehouse.disabled == False,
                Warehouse.id != warehouse_id,
            )
            .order_by(Warehouse.warehouse_name)
            .all()
        )

    def get_warehouse_hierarchy(self) -> List[dict]:
        """Get warehouse hierarchy as a tree structure.

        Returns:
            List of warehouse dictionaries with nested children.
        """
        # Get all warehouses
        warehouses = (
            self.db.query(Warehouse)
            .filter(Warehouse.is_deleted == False)
            .order_by(Warehouse.warehouse_name)
            .all()
        )

        # Build lookup
        by_name = {w.warehouse_name: w for w in warehouses}

        # Build tree
        roots = []
        for w in warehouses:
            node = {
                "id": w.id,
                "name": w.warehouse_name,
                "type": w.warehouse_type,
                "is_group": w.is_group,
                "disabled": w.disabled,
                "children": [],
            }

            if not w.parent_warehouse or w.parent_warehouse not in by_name:
                roots.append(node)
            else:
                # Will be added as child of parent
                pass

        return roots

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_warehouse(self, data: WarehouseCreateData) -> Warehouse:
        """Create a new warehouse.

        Args:
            data: Warehouse creation data.

        Returns:
            The created Warehouse.

        Raises:
            ValidationError: If validation fails.
            ConflictError: If warehouse name already exists.
        """
        if not data.warehouse_name:
            raise ValidationError("Warehouse name is required")

        # Check for duplicate
        existing = self.get_warehouse_by_name(data.warehouse_name)
        if existing:
            raise ConflictError(f"Warehouse '{data.warehouse_name}' already exists")

        # Validate parent if specified
        if data.parent_warehouse:
            parent = self.get_warehouse_by_name(data.parent_warehouse)
            if not parent:
                raise ValidationError(f"Parent warehouse '{data.parent_warehouse}' not found")
            if not parent.is_group:
                raise ValidationError(
                    f"Parent warehouse '{data.parent_warehouse}' is not a group warehouse"
                )

        warehouse = Warehouse(
            warehouse_name=data.warehouse_name,
            warehouse_type=data.warehouse_type,
            parent_warehouse=data.parent_warehouse,
            company=data.company,
            account=data.account,
            is_group=data.is_group,
            origin_system="local",
            write_back_status="pending",
        )

        if self.principal:
            warehouse.created_by_id = self.principal.id

        self.db.add(warehouse)
        self.db.flush()

        return warehouse

    def update_warehouse(self, warehouse_id: int, data: WarehouseUpdateData) -> Warehouse:
        """Update an existing warehouse.

        Args:
            warehouse_id: The warehouse ID.
            data: Update data.

        Returns:
            The updated Warehouse.

        Raises:
            NotFoundError: If warehouse not found.
            ValidationError: If validation fails.
            ConflictError: If new name conflicts.
        """
        warehouse = self.get_warehouse(warehouse_id)

        # Check name change for conflict
        if data.warehouse_name and data.warehouse_name != warehouse.warehouse_name:
            existing = self.get_warehouse_by_name(data.warehouse_name)
            if existing:
                raise ConflictError(f"Warehouse '{data.warehouse_name}' already exists")
            warehouse.warehouse_name = data.warehouse_name

        # Validate parent change
        if data.parent_warehouse is not None and data.parent_warehouse != warehouse.parent_warehouse:
            if data.parent_warehouse:
                parent = self.get_warehouse_by_name(data.parent_warehouse)
                if not parent:
                    raise ValidationError(f"Parent warehouse '{data.parent_warehouse}' not found")
                if not parent.is_group:
                    raise ValidationError(
                        f"Parent warehouse '{data.parent_warehouse}' is not a group warehouse"
                    )
                # Prevent circular reference
                if parent.warehouse_name == warehouse.warehouse_name:
                    raise ValidationError("Warehouse cannot be its own parent")
            warehouse.parent_warehouse = data.parent_warehouse or None

        # Update other fields
        if data.warehouse_type is not None:
            warehouse.warehouse_type = data.warehouse_type or None
        if data.company is not None:
            warehouse.company = data.company or None
        if data.account is not None:
            warehouse.account = data.account or None
        if data.is_group is not None:
            # Don't allow changing to non-group if it has children
            if not data.is_group and warehouse.is_group:
                children = self.get_child_warehouses(warehouse.warehouse_name)
                if children:
                    raise ValidationError(
                        "Cannot convert to non-group warehouse while it has child warehouses"
                    )
            warehouse.is_group = data.is_group
        if data.disabled is not None:
            warehouse.disabled = data.disabled

        warehouse.updated_at = datetime.utcnow()
        if self.principal:
            warehouse.updated_by_id = self.principal.id

        self.db.flush()

        return warehouse

    def delete_warehouse(self, warehouse_id: int) -> None:
        """Soft delete a warehouse.

        Args:
            warehouse_id: The warehouse ID.

        Raises:
            NotFoundError: If warehouse not found.
            ValidationError: If warehouse has children or stock.
        """
        warehouse = self.get_warehouse(warehouse_id)

        # Check for children
        children = self.get_child_warehouses(warehouse.warehouse_name)
        if children:
            raise ValidationError(
                f"Cannot delete warehouse with {len(children)} child warehouse(s)"
            )

        # Check for stock (via stock ledger entries)
        from app.models.inventory import StockLedgerEntry

        has_stock = (
            self.db.query(StockLedgerEntry)
            .filter(
                StockLedgerEntry.warehouse == warehouse.warehouse_name,
                StockLedgerEntry.qty_after_transaction != 0,
            )
            .first()
        )
        if has_stock:
            raise ValidationError("Cannot delete warehouse with existing stock")

        warehouse.is_deleted = True
        warehouse.deleted_at = datetime.utcnow()
        if self.principal:
            warehouse.deleted_by_id = self.principal.id

        self.db.flush()

    def disable_warehouse(self, warehouse_id: int, disabled: bool = True) -> Warehouse:
        """Enable or disable a warehouse.

        Args:
            warehouse_id: The warehouse ID.
            disabled: Whether to disable (True) or enable (False).

        Returns:
            The updated Warehouse.
        """
        warehouse = self.get_warehouse(warehouse_id)
        warehouse.disabled = disabled
        warehouse.updated_at = datetime.utcnow()

        if self.principal:
            warehouse.updated_by_id = self.principal.id

        self.db.flush()
        return warehouse

    def enable_warehouse(self, warehouse_id: int) -> Warehouse:
        """Enable a disabled warehouse.

        Args:
            warehouse_id: The warehouse ID.

        Returns:
            The updated Warehouse.
        """
        return self.disable_warehouse(warehouse_id, disabled=False)

    # -------------------------------------------------------------------------
    # Aggregations
    # -------------------------------------------------------------------------

    def get_warehouse_summary(self) -> dict:
        """Get summary statistics for warehouses.

        Returns:
            Dictionary with warehouse counts by type.
        """
        total = (
            self.db.query(func.count(Warehouse.id))
            .filter(Warehouse.is_deleted == False)
            .scalar()
            or 0
        )

        by_type = (
            self.db.query(Warehouse.warehouse_type, func.count(Warehouse.id))
            .filter(Warehouse.is_deleted == False)
            .group_by(Warehouse.warehouse_type)
            .all()
        )

        groups = (
            self.db.query(func.count(Warehouse.id))
            .filter(Warehouse.is_deleted == False, Warehouse.is_group == True)
            .scalar()
            or 0
        )

        disabled = (
            self.db.query(func.count(Warehouse.id))
            .filter(Warehouse.is_deleted == False, Warehouse.disabled == True)
            .scalar()
            or 0
        )

        return {
            "total": total,
            "by_type": {t or "Uncategorized": c for t, c in by_type},
            "groups": groups,
            "leaf": total - groups,
            "disabled": disabled,
            "active": total - disabled,
        }
