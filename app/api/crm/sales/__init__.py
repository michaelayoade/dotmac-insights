"""
CRM Sales Sub-module

Sales documents and transactions:
- Orders (sales orders)
- Quotations (proposals/quotes)

Note: Invoices, payments, and credit notes are in the accounting module.
"""
from fastapi import APIRouter

from .orders import router as orders_router
from .quotations import router as quotations_router

router = APIRouter(prefix="/sales", tags=["crm-sales"])

router.include_router(orders_router)
router.include_router(quotations_router)
