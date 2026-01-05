"""Vendor Payments and Purchase Orders API endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.services.purchasing import VendorPaymentService, PurchaseOrderService, PaymentFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

from ._deps import (
    get_payment_service,
    get_order_service,
    RequireRead,
    parse_date,
    handle_service_error,
)

router = APIRouter(tags=["purchasing"])


# ============= PAYMENTS =============

@router.get("/payments", dependencies=[RequireRead])
async def get_vendor_payments(
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: VendorPaymentService = Depends(get_payment_service),
) -> Dict[str, Any]:
    """Get vendor payments from GL entries."""
    filters = PaymentFilters(
        supplier=supplier,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_payments(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "payments": [
            {
                "id": p.id,
                "posting_date": p.posting_date.isoformat() if p.posting_date else None,
                "supplier": p.party,
                "account": p.account,
                "debit": float(p.debit),
                "credit": float(p.credit),
                "amount": float(p.credit - p.debit),
                "voucher_no": p.voucher_no,
                "cost_center": p.cost_center,
            }
            for p in result.data
        ],
    }


# ============= PURCHASE ORDERS =============

@router.get("/orders", dependencies=[RequireRead])
async def get_purchase_orders(
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: PurchaseOrderService = Depends(get_order_service),
) -> Dict[str, Any]:
    """Get purchase orders."""
    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_orders(
        supplier=supplier,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        pagination=pagination,
    )

    return {
        "total": result["total"],
        "limit": limit,
        "offset": offset,
        "orders": result["orders"],
    }


@router.get("/orders/{order_no}", dependencies=[RequireRead])
async def get_purchase_order_detail(
    order_no: str,
    service: PurchaseOrderService = Depends(get_order_service),
) -> Dict[str, Any]:
    """Get purchase order details with linked bills."""
    try:
        return service.get_order_detail(order_no)
    except NotFoundError as e:
        handle_service_error(e)
