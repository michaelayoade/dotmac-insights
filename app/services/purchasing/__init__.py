"""Purchasing services module.

This package contains all purchasing-related business logic:
- BillService: Purchase invoice (bill) CRUD
- SupplierService: Supplier management
- PurchasingDashboardService: Dashboard metrics
- APAgingService: Accounts payable aging
- PurchasingAnalyticsService: Analytics and reporting
- VendorPaymentService: Vendor payments
- PurchaseOrderService: Purchase orders
- DebitNoteService: Debit notes (returns)
- GLExpenseService: GL-based expense entries

Usage:
    from app.services.purchasing import BillService, SupplierService

    def my_route(db: Session = Depends(get_db)):
        bill_service = BillService(db)
        bills = bill_service.list_bills(filters, pagination)
        db.commit()  # Routes control transaction
"""
from .bills import BillService
from .suppliers import SupplierService
from .dashboard import PurchasingDashboardService
from .aging import APAgingService
from .analytics import PurchasingAnalyticsService
from .payments import VendorPaymentService, PurchaseOrderService, DebitNoteService
from .expenses import GLExpenseService

from .types import (
    # Bill types
    BillFilters,
    BillCreateData,
    BillUpdateData,
    # Supplier types
    SupplierFilters,
    SupplierCreateData,
    SupplierUpdateData,
    # Other types
    PaymentFilters,
    DebitNoteFilters,
    ExpenseFilters,
    AgingBucket,
    DashboardMetrics,
)

__all__ = [
    # Services
    "BillService",
    "SupplierService",
    "PurchasingDashboardService",
    "APAgingService",
    "PurchasingAnalyticsService",
    "VendorPaymentService",
    "PurchaseOrderService",
    "DebitNoteService",
    "GLExpenseService",
    # Types
    "BillFilters",
    "BillCreateData",
    "BillUpdateData",
    "SupplierFilters",
    "SupplierCreateData",
    "SupplierUpdateData",
    "PaymentFilters",
    "DebitNoteFilters",
    "ExpenseFilters",
    "AgingBucket",
    "DashboardMetrics",
]
