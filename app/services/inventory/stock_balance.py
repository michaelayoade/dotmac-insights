"""Stock balance service - business logic for stock level queries.

This service encapsulates all stock balance/valuation queries:
- Current stock levels by item/warehouse
- Stock valuation reports
- Low stock alerts
- Stock aging analysis

This is primarily a read-only service.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from app.models.inventory import StockLedgerEntry, Warehouse

from .types import (
    StockBalanceQuery,
    StockBalanceResult,
    ItemStock,
    WarehouseStock,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["StockBalanceService"]


class StockBalanceService:
    """Service for stock balance queries.

    Provides read-only queries for stock levels, valuation, and analysis.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Stock Balance Queries
    # -------------------------------------------------------------------------

    def get_stock_balance(
        self, query: Optional[StockBalanceQuery] = None
    ) -> StockBalanceResult:
        """Get stock balance for items across warehouses.

        Args:
            query: Query parameters for filtering.

        Returns:
            StockBalanceResult with item balances.
        """
        query = query or StockBalanceQuery()
        as_of = query.as_of_date or date.today()

        # Subquery to get the latest SLE for each item/warehouse
        # This gets the running balance (qty_after_transaction)
        latest_sle = (
            self.db.query(
                StockLedgerEntry.item_code,
                StockLedgerEntry.warehouse,
                func.max(StockLedgerEntry.id).label("max_id"),
            )
            .filter(
                StockLedgerEntry.is_cancelled == False,
                func.date(StockLedgerEntry.posting_date) <= as_of,
            )
            .group_by(StockLedgerEntry.item_code, StockLedgerEntry.warehouse)
            .subquery()
        )

        # Get the actual SLE records with balances
        stock_query = (
            self.db.query(StockLedgerEntry)
            .join(
                latest_sle,
                and_(
                    StockLedgerEntry.id == latest_sle.c.max_id,
                ),
            )
        )

        # Apply filters
        if query.item_code:
            stock_query = stock_query.filter(StockLedgerEntry.item_code == query.item_code)
        if query.warehouse:
            stock_query = stock_query.filter(StockLedgerEntry.warehouse == query.warehouse)
        if query.company:
            stock_query = stock_query.filter(StockLedgerEntry.company == query.company)
        if not query.include_zero_stock:
            stock_query = stock_query.filter(StockLedgerEntry.qty_after_transaction != 0)

        entries = stock_query.all()

        # Build results
        items = []
        total_qty = Decimal("0")
        total_value = Decimal("0")

        for sle in entries:
            item_stock = ItemStock(
                item_code=sle.item_code,
                item_name=None,  # Would need item master lookup
                warehouse=sle.warehouse,
                actual_qty=sle.qty_after_transaction,
                valuation_rate=sle.valuation_rate,
                stock_value=sle.stock_value,
                batch_no=sle.batch_no,
            )
            items.append(item_stock)
            total_qty += sle.qty_after_transaction
            total_value += sle.stock_value

        return StockBalanceResult(
            items=items,
            total_qty=total_qty,
            total_value=total_value,
            as_of_date=as_of,
        )

    def get_item_balance(self, item_code: str, warehouse: Optional[str] = None) -> Decimal:
        """Get current stock balance for a specific item.

        Args:
            item_code: The item code.
            warehouse: Optional warehouse filter.

        Returns:
            Current stock quantity.
        """
        query = (
            self.db.query(func.sum(StockLedgerEntry.actual_qty))
            .filter(
                StockLedgerEntry.item_code == item_code,
                StockLedgerEntry.is_cancelled == False,
            )
        )

        if warehouse:
            query = query.filter(StockLedgerEntry.warehouse == warehouse)

        result = query.scalar()
        return Decimal(result) if result else Decimal("0")

    def get_warehouse_balance(self, warehouse: str) -> List[ItemStock]:
        """Get all item balances for a warehouse.

        Args:
            warehouse: The warehouse name.

        Returns:
            List of ItemStock for items in the warehouse.
        """
        # Get latest entry for each item
        latest_sle = (
            self.db.query(
                StockLedgerEntry.item_code,
                func.max(StockLedgerEntry.id).label("max_id"),
            )
            .filter(
                StockLedgerEntry.warehouse == warehouse,
                StockLedgerEntry.is_cancelled == False,
            )
            .group_by(StockLedgerEntry.item_code)
            .subquery()
        )

        entries = (
            self.db.query(StockLedgerEntry)
            .join(latest_sle, StockLedgerEntry.id == latest_sle.c.max_id)
            .filter(StockLedgerEntry.qty_after_transaction != 0)
            .all()
        )

        return [
            ItemStock(
                item_code=sle.item_code,
                item_name=None,
                warehouse=sle.warehouse,
                actual_qty=sle.qty_after_transaction,
                valuation_rate=sle.valuation_rate,
                stock_value=sle.stock_value,
                batch_no=sle.batch_no,
            )
            for sle in entries
        ]

    # -------------------------------------------------------------------------
    # Warehouse Summary
    # -------------------------------------------------------------------------

    def get_warehouse_summary(self) -> List[WarehouseStock]:
        """Get stock summary for all warehouses.

        Returns:
            List of WarehouseStock with totals per warehouse.
        """
        # Get latest entry for each item/warehouse combination
        latest_sle = (
            self.db.query(
                StockLedgerEntry.warehouse,
                StockLedgerEntry.item_code,
                func.max(StockLedgerEntry.id).label("max_id"),
            )
            .filter(StockLedgerEntry.is_cancelled == False)
            .group_by(StockLedgerEntry.warehouse, StockLedgerEntry.item_code)
            .subquery()
        )

        # Get aggregates per warehouse
        warehouse_totals = (
            self.db.query(
                StockLedgerEntry.warehouse,
                func.count(StockLedgerEntry.item_code.distinct()).label("total_items"),
                func.sum(StockLedgerEntry.qty_after_transaction).label("total_qty"),
                func.sum(StockLedgerEntry.stock_value).label("total_value"),
            )
            .join(latest_sle, StockLedgerEntry.id == latest_sle.c.max_id)
            .filter(StockLedgerEntry.qty_after_transaction != 0)
            .group_by(StockLedgerEntry.warehouse)
            .all()
        )

        # Get warehouse types
        warehouses = {
            w.warehouse_name: w.warehouse_type
            for w in self.db.query(Warehouse)
            .filter(Warehouse.is_deleted == False)
            .all()
        }

        return [
            WarehouseStock(
                warehouse=wh,
                warehouse_type=warehouses.get(wh),
                total_items=items or 0,
                total_qty=qty or Decimal("0"),
                total_value=value or Decimal("0"),
            )
            for wh, items, qty, value in warehouse_totals
        ]

    # -------------------------------------------------------------------------
    # Stock Alerts
    # -------------------------------------------------------------------------

    def get_low_stock_items(
        self,
        threshold: Decimal = Decimal("10"),
        warehouse: Optional[str] = None,
    ) -> List[ItemStock]:
        """Get items with low stock levels.

        Args:
            threshold: Minimum quantity threshold.
            warehouse: Optional warehouse filter.

        Returns:
            List of items below threshold.
        """
        # Get current balances
        latest_sle = (
            self.db.query(
                StockLedgerEntry.item_code,
                StockLedgerEntry.warehouse,
                func.max(StockLedgerEntry.id).label("max_id"),
            )
            .filter(StockLedgerEntry.is_cancelled == False)
            .group_by(StockLedgerEntry.item_code, StockLedgerEntry.warehouse)
            .subquery()
        )

        query = (
            self.db.query(StockLedgerEntry)
            .join(latest_sle, StockLedgerEntry.id == latest_sle.c.max_id)
            .filter(
                StockLedgerEntry.qty_after_transaction > 0,
                StockLedgerEntry.qty_after_transaction <= threshold,
            )
        )

        if warehouse:
            query = query.filter(StockLedgerEntry.warehouse == warehouse)

        entries = query.order_by(StockLedgerEntry.qty_after_transaction).all()

        return [
            ItemStock(
                item_code=sle.item_code,
                item_name=None,
                warehouse=sle.warehouse,
                actual_qty=sle.qty_after_transaction,
                valuation_rate=sle.valuation_rate,
                stock_value=sle.stock_value,
            )
            for sle in entries
        ]

    def get_negative_stock_items(self) -> List[ItemStock]:
        """Get items with negative stock (data issues).

        Returns:
            List of items with negative quantity.
        """
        latest_sle = (
            self.db.query(
                StockLedgerEntry.item_code,
                StockLedgerEntry.warehouse,
                func.max(StockLedgerEntry.id).label("max_id"),
            )
            .filter(StockLedgerEntry.is_cancelled == False)
            .group_by(StockLedgerEntry.item_code, StockLedgerEntry.warehouse)
            .subquery()
        )

        entries = (
            self.db.query(StockLedgerEntry)
            .join(latest_sle, StockLedgerEntry.id == latest_sle.c.max_id)
            .filter(StockLedgerEntry.qty_after_transaction < 0)
            .all()
        )

        return [
            ItemStock(
                item_code=sle.item_code,
                item_name=None,
                warehouse=sle.warehouse,
                actual_qty=sle.qty_after_transaction,
                valuation_rate=sle.valuation_rate,
                stock_value=sle.stock_value,
            )
            for sle in entries
        ]

    # -------------------------------------------------------------------------
    # Stock Movement History
    # -------------------------------------------------------------------------

    def get_stock_ledger(
        self,
        item_code: Optional[str] = None,
        warehouse: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[StockLedgerEntry]:
        """Get stock ledger entries (movement history).

        Args:
            item_code: Optional item filter.
            warehouse: Optional warehouse filter.
            from_date: Optional start date.
            to_date: Optional end date.
            limit: Maximum entries to return.

        Returns:
            List of StockLedgerEntry records.
        """
        query = self.db.query(StockLedgerEntry).filter(
            StockLedgerEntry.is_cancelled == False
        )

        if item_code:
            query = query.filter(StockLedgerEntry.item_code == item_code)
        if warehouse:
            query = query.filter(StockLedgerEntry.warehouse == warehouse)
        if from_date:
            query = query.filter(func.date(StockLedgerEntry.posting_date) >= from_date)
        if to_date:
            query = query.filter(func.date(StockLedgerEntry.posting_date) <= to_date)

        return (
            query.order_by(desc(StockLedgerEntry.posting_date), desc(StockLedgerEntry.id))
            .limit(limit)
            .all()
        )

    # -------------------------------------------------------------------------
    # Valuation
    # -------------------------------------------------------------------------

    def get_stock_valuation_summary(self) -> dict:
        """Get overall stock valuation summary.

        Returns:
            Dictionary with total stock value by warehouse.
        """
        summary = self.get_warehouse_summary()

        total_value = sum(ws.total_value for ws in summary)
        total_qty = sum(ws.total_qty for ws in summary)
        total_items = sum(ws.total_items for ws in summary)

        return {
            "total_value": total_value,
            "total_qty": total_qty,
            "total_items": total_items,
            "by_warehouse": {ws.warehouse: float(ws.total_value) for ws in summary},
        }
