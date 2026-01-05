"""Purchasing API dependencies and service providers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, NoReturn

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require

from app.services.purchasing import (
    BillService,
    SupplierService,
    PurchasingDashboardService,
    APAgingService,
    PurchasingAnalyticsService,
    VendorPaymentService,
    PurchaseOrderService,
    DebitNoteService,
    GLExpenseService,
)
from app.services.errors import NotFoundError, ValidationError, ConflictError

# Permission dependencies
RequireRead = Depends(Require("purchasing:read"))
RequireWrite = Depends(Require("purchasing:write"))


# Service providers
def get_bill_service(db: Session = Depends(get_db)) -> BillService:
    return BillService(db)


def get_supplier_service(db: Session = Depends(get_db)) -> SupplierService:
    return SupplierService(db)


def get_dashboard_service(db: Session = Depends(get_db)) -> PurchasingDashboardService:
    return PurchasingDashboardService(db)


def get_aging_service(db: Session = Depends(get_db)) -> APAgingService:
    return APAgingService(db)


def get_analytics_service(db: Session = Depends(get_db)) -> PurchasingAnalyticsService:
    return PurchasingAnalyticsService(db)


def get_payment_service(db: Session = Depends(get_db)) -> VendorPaymentService:
    return VendorPaymentService(db)


def get_order_service(db: Session = Depends(get_db)) -> PurchaseOrderService:
    return PurchaseOrderService(db)


def get_debit_note_service(db: Session = Depends(get_db)) -> DebitNoteService:
    return DebitNoteService(db)


def get_expense_service(db: Session = Depends(get_db)) -> GLExpenseService:
    return GLExpenseService(db)


def handle_service_error(e: Exception) -> NoReturn:
    """Convert service errors to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail=str(e))


def parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")
