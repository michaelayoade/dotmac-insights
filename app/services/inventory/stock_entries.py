"""Stock entry service - business logic for stock entry operations.

This service encapsulates all stock entry (inventory movement) business logic:
- Material issue/receipt/transfer
- Stock entry CRUD
- Stock ledger updates

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc, func, and_
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import (
    StockEntry,
    StockEntryDetail,
    StockLedgerEntry,
    Warehouse,
)

from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    StockEntryFilters,
    StockEntryCreateData,
    StockEntryUpdateData,
    StockEntryItemData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["StockEntryService"]


class StockEntryService:
    """Service for stock entry business logic.

    Handles creation and management of inventory movements.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
        allow_negative_stock: If False (default), validates stock won't go negative.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        allow_negative_stock: bool = False,
    ) -> None:
        self.db = db
        self.principal = principal
        self.allow_negative_stock = allow_negative_stock

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_entries(
        self,
        filters: Optional[StockEntryFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[StockEntry]:
        """List stock entries with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing entries and total count.
        """
        filters = filters or StockEntryFilters()
        pagination = pagination or PaginationParams()

        query = (
            self.db.query(StockEntry)
            .filter(StockEntry.is_deleted == False)
        )

        # Search
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                or_(
                    StockEntry.erpnext_id.ilike(search),
                    StockEntry.from_warehouse.ilike(search),
                    StockEntry.to_warehouse.ilike(search),
                    StockEntry.remarks.ilike(search),
                )
            )

        # Filters
        if filters.stock_entry_type:
            query = query.filter(StockEntry.stock_entry_type == filters.stock_entry_type)
        if filters.from_warehouse:
            query = query.filter(StockEntry.from_warehouse == filters.from_warehouse)
        if filters.to_warehouse:
            query = query.filter(StockEntry.to_warehouse == filters.to_warehouse)
        if filters.from_date:
            query = query.filter(StockEntry.posting_date >= filters.from_date)
        if filters.to_date:
            query = query.filter(StockEntry.posting_date <= filters.to_date)
        if filters.company:
            query = query.filter(StockEntry.company == filters.company)
        if filters.docstatus is not None:
            query = query.filter(StockEntry.docstatus == filters.docstatus)

        # Count total
        total = query.count()

        # Sorting
        sort_col = getattr(StockEntry, filters.sort_by, StockEntry.posting_date)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(items=query.all(), total=total)

    def get_entry(self, entry_id: int, include_items: bool = True) -> StockEntry:
        """Get a single stock entry by ID.

        Args:
            entry_id: The stock entry ID.
            include_items: Whether to eagerly load line items.

        Returns:
            The StockEntry object.

        Raises:
            NotFoundError: If entry not found.
        """
        query = self.db.query(StockEntry).filter(
            StockEntry.id == entry_id,
            StockEntry.is_deleted == False,
        )

        if include_items:
            query = query.options(selectinload(StockEntry.items))

        entry = query.first()
        if not entry:
            raise NotFoundError(f"Stock entry {entry_id} not found")
        return entry

    def get_entries_for_warehouse(
        self,
        warehouse: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 50,
    ) -> List[StockEntry]:
        """Get stock entries involving a specific warehouse.

        Args:
            warehouse: The warehouse name.
            from_date: Optional start date.
            to_date: Optional end date.
            limit: Maximum entries to return.

        Returns:
            List of StockEntry objects.
        """
        query = (
            self.db.query(StockEntry)
            .filter(
                StockEntry.is_deleted == False,
                or_(
                    StockEntry.from_warehouse == warehouse,
                    StockEntry.to_warehouse == warehouse,
                ),
            )
        )

        if from_date:
            query = query.filter(StockEntry.posting_date >= from_date)
        if to_date:
            query = query.filter(StockEntry.posting_date <= to_date)

        return query.order_by(desc(StockEntry.posting_date)).limit(limit).all()

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_entry(self, data: StockEntryCreateData) -> StockEntry:
        """Create a new stock entry.

        Args:
            data: Stock entry creation data.

        Returns:
            The created StockEntry.

        Raises:
            ValidationError: If validation fails.
        """
        # Validate entry type
        valid_types = [
            "Material Issue",
            "Material Receipt",
            "Material Transfer",
            "Material Transfer for Manufacture",
            "Material Consumption for Manufacture",
            "Manufacture",
            "Repack",
            "Send to Subcontractor",
        ]
        if data.stock_entry_type not in valid_types:
            raise ValidationError(f"Invalid stock entry type: {data.stock_entry_type}")

        # Validate warehouses based on type
        self._validate_warehouses_for_type(data)

        # Create entry
        entry = StockEntry(
            stock_entry_type=data.stock_entry_type,
            posting_date=datetime.combine(data.posting_date, datetime.min.time()),
            posting_time=data.posting_time,
            from_warehouse=data.from_warehouse,
            to_warehouse=data.to_warehouse,
            company=data.company,
            purpose=data.purpose,
            remarks=data.remarks,
            work_order=data.work_order,
            purchase_order=data.purchase_order,
            sales_order=data.sales_order,
            origin_system="local",
            write_back_status="pending",
            docstatus=0,  # Draft
        )

        if self.principal:
            entry.created_by_id = self.principal.id

        self.db.add(entry)
        self.db.flush()

        # Create line items
        total_incoming = Decimal("0")
        total_outgoing = Decimal("0")

        for idx, item_data in enumerate(data.items):
            item = StockEntryDetail(
                stock_entry_id=entry.id,
                item_code=item_data.item_code,
                item_name=item_data.item_name,
                description=item_data.description,
                qty=item_data.qty,
                transfer_qty=item_data.qty,
                uom=item_data.uom,
                stock_uom=item_data.uom,
                conversion_factor=Decimal("1"),
                s_warehouse=item_data.s_warehouse or data.from_warehouse,
                t_warehouse=item_data.t_warehouse or data.to_warehouse,
                basic_rate=item_data.basic_rate,
                basic_amount=item_data.qty * item_data.basic_rate,
                valuation_rate=item_data.basic_rate,
                amount=item_data.qty * item_data.basic_rate,
                batch_no=item_data.batch_no,
                serial_no=item_data.serial_no,
                idx=idx,
            )
            self.db.add(item)

            # Calculate totals
            if item.t_warehouse:
                total_incoming += item.amount
            if item.s_warehouse:
                total_outgoing += item.amount

        entry.total_incoming_value = total_incoming
        entry.total_outgoing_value = total_outgoing
        entry.total_amount = max(total_incoming, total_outgoing)
        entry.value_difference = total_incoming - total_outgoing

        self.db.flush()

        return entry

    def update_entry(self, entry_id: int, data: StockEntryUpdateData) -> StockEntry:
        """Update an existing stock entry.

        Only draft entries can be updated.

        Args:
            entry_id: The stock entry ID.
            data: Update data.

        Returns:
            The updated StockEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry is not in draft status.
        """
        entry = self.get_entry(entry_id)

        if entry.docstatus != 0:
            raise ValidationError("Only draft entries can be updated")

        if data.stock_entry_type is not None:
            entry.stock_entry_type = data.stock_entry_type
        if data.posting_date is not None:
            entry.posting_date = datetime.combine(data.posting_date, datetime.min.time())
        if data.posting_time is not None:
            entry.posting_time = data.posting_time
        if data.from_warehouse is not None:
            entry.from_warehouse = data.from_warehouse or None
        if data.to_warehouse is not None:
            entry.to_warehouse = data.to_warehouse or None
        if data.purpose is not None:
            entry.purpose = data.purpose or None
        if data.remarks is not None:
            entry.remarks = data.remarks or None

        entry.updated_at = datetime.utcnow()
        if self.principal:
            entry.updated_by_id = self.principal.id

        self.db.flush()

        return entry

    def submit_entry(self, entry_id: int) -> StockEntry:
        """Submit a stock entry (post to stock ledger).

        Args:
            entry_id: The stock entry ID.

        Returns:
            The submitted StockEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry cannot be submitted.
        """
        entry = self.get_entry(entry_id, include_items=True)

        if entry.docstatus != 0:
            raise ValidationError("Only draft entries can be submitted")

        if not entry.items:
            raise ValidationError("Cannot submit entry without items")

        # Create stock ledger entries
        self._create_stock_ledger_entries(entry)

        entry.docstatus = 1  # Submitted
        entry.updated_at = datetime.utcnow()

        self.db.flush()

        return entry

    def cancel_entry(self, entry_id: int) -> StockEntry:
        """Cancel a submitted stock entry.

        Creates reverse stock ledger entries.

        Args:
            entry_id: The stock entry ID.

        Returns:
            The cancelled StockEntry.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry cannot be cancelled.
        """
        entry = self.get_entry(entry_id, include_items=True)

        if entry.docstatus != 1:
            raise ValidationError("Only submitted entries can be cancelled")

        # Create reverse stock ledger entries
        self._create_reverse_stock_ledger_entries(entry)

        entry.docstatus = 2  # Cancelled
        entry.updated_at = datetime.utcnow()

        self.db.flush()

        return entry

    def delete_entry(self, entry_id: int) -> None:
        """Soft delete a stock entry.

        Only draft entries can be deleted.

        Args:
            entry_id: The stock entry ID.

        Raises:
            NotFoundError: If entry not found.
            ValidationError: If entry is not in draft status.
        """
        entry = self.get_entry(entry_id)

        if entry.docstatus != 0:
            raise ValidationError("Only draft entries can be deleted")

        entry.is_deleted = True
        entry.deleted_at = datetime.utcnow()
        if self.principal:
            entry.deleted_by_id = self.principal.id

        self.db.flush()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _validate_warehouses_for_type(self, data: StockEntryCreateData) -> None:
        """Validate warehouse requirements based on entry type."""
        entry_type = data.stock_entry_type

        if entry_type == "Material Issue":
            if not data.from_warehouse:
                raise ValidationError("Source warehouse required for Material Issue")
        elif entry_type == "Material Receipt":
            if not data.to_warehouse:
                raise ValidationError("Target warehouse required for Material Receipt")
        elif entry_type == "Material Transfer":
            if not data.from_warehouse or not data.to_warehouse:
                raise ValidationError("Both source and target warehouse required for transfer")
            if data.from_warehouse == data.to_warehouse:
                raise ValidationError("Source and target warehouse cannot be the same")

        # Validate warehouses exist
        if data.from_warehouse:
            wh = (
                self.db.query(Warehouse)
                .filter(
                    Warehouse.warehouse_name == data.from_warehouse,
                    Warehouse.is_deleted == False,
                )
                .first()
            )
            if not wh:
                raise ValidationError(f"Warehouse '{data.from_warehouse}' not found")
            if wh.is_group:
                raise ValidationError(f"Cannot use group warehouse '{data.from_warehouse}'")

        if data.to_warehouse:
            wh = (
                self.db.query(Warehouse)
                .filter(
                    Warehouse.warehouse_name == data.to_warehouse,
                    Warehouse.is_deleted == False,
                )
                .first()
            )
            if not wh:
                raise ValidationError(f"Warehouse '{data.to_warehouse}' not found")
            if wh.is_group:
                raise ValidationError(f"Cannot use group warehouse '{data.to_warehouse}'")

    def _create_stock_ledger_entries(self, entry: StockEntry) -> None:
        """Create stock ledger entries for a submitted stock entry.

        Raises:
            ValidationError: If stock would go negative and allow_negative_stock is False.
        """
        for item in entry.items:
            # Outgoing entry (from source warehouse)
            if item.s_warehouse:
                # Get current stock balance
                current_balance = self._get_stock_balance(
                    item.item_code, item.s_warehouse
                )
                new_balance = current_balance - item.qty

                # Validate stock availability
                if not self.allow_negative_stock and new_balance < 0:
                    raise ValidationError(
                        f"Insufficient stock for item '{item.item_code}' in warehouse "
                        f"'{item.s_warehouse}'. Available: {current_balance}, Required: {item.qty}"
                    )

                sle = StockLedgerEntry(
                    item_code=item.item_code,
                    warehouse=item.s_warehouse,
                    company=entry.company,
                    posting_date=entry.posting_date,
                    posting_time=entry.posting_time,
                    actual_qty=-item.qty,  # Negative for outgoing
                    qty_after_transaction=new_balance,
                    valuation_rate=item.valuation_rate,
                    outgoing_rate=item.valuation_rate,
                    stock_value=new_balance * item.valuation_rate,
                    stock_value_difference=-item.amount,
                    voucher_type="Stock Entry",
                    voucher_no=entry.erpnext_id or str(entry.id),
                    batch_no=item.batch_no,
                    serial_no=item.serial_no,
                )
                self.db.add(sle)

            # Incoming entry (to target warehouse)
            if item.t_warehouse:
                current_balance = self._get_stock_balance(
                    item.item_code, item.t_warehouse
                )
                new_balance = current_balance + item.qty

                sle = StockLedgerEntry(
                    item_code=item.item_code,
                    warehouse=item.t_warehouse,
                    company=entry.company,
                    posting_date=entry.posting_date,
                    posting_time=entry.posting_time,
                    actual_qty=item.qty,  # Positive for incoming
                    qty_after_transaction=new_balance,
                    valuation_rate=item.valuation_rate,
                    incoming_rate=item.valuation_rate,
                    stock_value=new_balance * item.valuation_rate,
                    stock_value_difference=item.amount,
                    voucher_type="Stock Entry",
                    voucher_no=entry.erpnext_id or str(entry.id),
                    batch_no=item.batch_no,
                    serial_no=item.serial_no,
                )
                self.db.add(sle)

    def _create_reverse_stock_ledger_entries(self, entry: StockEntry) -> None:
        """Create reverse stock ledger entries for cancellation."""
        for item in entry.items:
            # Reverse outgoing (add back to source)
            if item.s_warehouse:
                current_balance = self._get_stock_balance(
                    item.item_code, item.s_warehouse
                )
                new_balance = current_balance + item.qty

                sle = StockLedgerEntry(
                    item_code=item.item_code,
                    warehouse=item.s_warehouse,
                    company=entry.company,
                    posting_date=datetime.utcnow(),
                    actual_qty=item.qty,  # Add back
                    qty_after_transaction=new_balance,
                    valuation_rate=item.valuation_rate,
                    stock_value=new_balance * item.valuation_rate,
                    stock_value_difference=item.amount,
                    voucher_type="Stock Entry",
                    voucher_no=f"{entry.erpnext_id or entry.id}-CANCEL",
                    is_cancelled=True,
                )
                self.db.add(sle)

            # Reverse incoming (remove from target)
            if item.t_warehouse:
                current_balance = self._get_stock_balance(
                    item.item_code, item.t_warehouse
                )
                new_balance = current_balance - item.qty

                sle = StockLedgerEntry(
                    item_code=item.item_code,
                    warehouse=item.t_warehouse,
                    company=entry.company,
                    posting_date=datetime.utcnow(),
                    actual_qty=-item.qty,  # Remove
                    qty_after_transaction=new_balance,
                    valuation_rate=item.valuation_rate,
                    stock_value=new_balance * item.valuation_rate,
                    stock_value_difference=-item.amount,
                    voucher_type="Stock Entry",
                    voucher_no=f"{entry.erpnext_id or entry.id}-CANCEL",
                    is_cancelled=True,
                )
                self.db.add(sle)

    def _get_stock_balance(self, item_code: str, warehouse: str) -> Decimal:
        """Get current stock balance for item at warehouse."""
        last_entry = (
            self.db.query(StockLedgerEntry)
            .filter(
                StockLedgerEntry.item_code == item_code,
                StockLedgerEntry.warehouse == warehouse,
                StockLedgerEntry.is_cancelled == False,
            )
            .order_by(desc(StockLedgerEntry.posting_date), desc(StockLedgerEntry.id))
            .first()
        )

        if last_entry:
            return last_entry.qty_after_transaction
        return Decimal("0")

    # -------------------------------------------------------------------------
    # Aggregations
    # -------------------------------------------------------------------------

    def get_entry_summary(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict:
        """Get summary of stock entries."""
        query = self.db.query(StockEntry).filter(StockEntry.is_deleted == False)

        if from_date:
            query = query.filter(StockEntry.posting_date >= from_date)
        if to_date:
            query = query.filter(StockEntry.posting_date <= to_date)

        total = query.count()

        by_type = (
            query.with_entities(
                StockEntry.stock_entry_type, func.count(StockEntry.id)
            )
            .group_by(StockEntry.stock_entry_type)
            .all()
        )

        by_status = (
            query.with_entities(StockEntry.docstatus, func.count(StockEntry.id))
            .group_by(StockEntry.docstatus)
            .all()
        )

        status_map = {0: "draft", 1: "submitted", 2: "cancelled"}

        return {
            "total": total,
            "by_type": {t or "Unknown": c for t, c in by_type},
            "by_status": {status_map.get(s, str(s)): c for s, c in by_status},
        }
