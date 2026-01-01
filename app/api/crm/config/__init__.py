"""
CRM Configuration Sub-module

Master data for CRM:
- Territories (geographic regions)
- Sales Persons (sales team)
- Customer Groups (customer categorization)
"""
from fastapi import APIRouter

from .territories import router as territories_router
from .sales_persons import router as sales_persons_router
from .customer_groups import router as customer_groups_router

router = APIRouter(prefix="/config", tags=["crm-config"])

router.include_router(territories_router)
router.include_router(sales_persons_router)
router.include_router(customer_groups_router)
