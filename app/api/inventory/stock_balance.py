"""Stock Balance API endpoints.

Thin wrapper around StockBalanceService for stock balance queries.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.services.inventory import StockBalanceService, StockBalanceQuery
from app.services.errors import NotFoundError

from ._deps import (
    get_stock_balance_service,
    RequireInventoryRead,
    handle_service_error,
)

router = APIRouter(prefix="/stock", tags=["inventory"])


def _parse_date(value: str | None):
    """Parse date string to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/balance", dependencies=[RequireInventoryRead])
async def get_stock_balance(
    item_code: str | None = None,
    warehouse: str | None = None,
    company: str | None = None,
    as_of_date: str | None = None,
    include_zero_stock: bool = False,
    service: StockBalanceService = Depends(get_stock_balance_service),
) -> Dict[str, Any]:
    """Get stock balance for items/warehouses."""
    query = StockBalanceQuery(
        item_code=item_code,
        warehouse=warehouse,
        company=company,
        as_of_date=_parse_date(as_of_date),
        include_zero_stock=include_zero_stock,
    )

    result = service.get_stock_balance(query)

    return {
        "as_of_date": result.as_of_date.isoformat(),
        "total_qty": str(result.total_qty),
        "total_value": str(result.total_value),
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "warehouse": item.warehouse,
                "actual_qty": str(item.actual_qty),
                "valuation_rate": str(item.valuation_rate),
                "stock_value": str(item.stock_value),
                "batch_no": item.batch_no,
            }
            for item in result.items
        ],
    }


@router.get("/summary", dependencies=[RequireInventoryRead])
async def get_stock_summary(
    service: StockBalanceService = Depends(get_stock_balance_service),
) -> Dict[str, Any]:
    """Get stock summary by warehouse."""
    summary = service.get_warehouse_summary()

    return {
        "warehouses": [
            {
                "warehouse": ws.warehouse,
                "warehouse_type": ws.warehouse_type,
                "total_items": ws.total_items,
                "total_qty": str(ws.total_qty),
                "total_value": str(ws.total_value),
            }
            for ws in summary
        ],
    }


@router.get("/ledger", dependencies=[RequireInventoryRead])
async def get_stock_ledger_entries(
    item_code: str | None = None,
    warehouse: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = Query(default=100, le=500),
    service: StockBalanceService = Depends(get_stock_balance_service),
) -> Dict[str, Any]:
    """Get stock ledger entries."""
    entries = service.get_stock_ledger(
        item_code=item_code,
        warehouse=warehouse,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        limit=limit,
    )

    return {
        "limit": limit,
        "count": len(entries),
        "entries": [
            {
                "id": e.id,
                "item_code": e.item_code,
                "warehouse": e.warehouse,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "actual_qty": str(e.actual_qty),
                "qty_after_transaction": str(e.qty_after_transaction),
                "valuation_rate": str(e.valuation_rate),
                "stock_value": str(e.stock_value),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
            }
            for e in entries
        ],
    }


@router.get("/valuation", dependencies=[RequireInventoryRead])
async def get_stock_valuation(
    service: StockBalanceService = Depends(get_stock_balance_service),
) -> Dict[str, Any]:
    """Get stock valuation summary."""
    valuation = service.get_stock_valuation_summary()

    return {
        "total_value": str(valuation["total_value"]),
        "total_qty": str(valuation["total_qty"]),
        "total_items": valuation["total_items"],
        "by_warehouse": valuation["by_warehouse"],
    }
