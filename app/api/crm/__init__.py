"""
CRM API Module - Leads, Opportunities, Activities, Contacts, Pipeline

Customer Lifecycle: Lead → Opportunity → Quotation → Order → Invoice → Retention
"""
from fastapi import APIRouter
from .leads import router as leads_router
from .opportunities import router as opportunities_router
from .activities import router as activities_router
from .contacts import router as contacts_router
from .pipeline import router as pipeline_router

router = APIRouter(prefix="/crm", tags=["crm"])

router.include_router(leads_router)
router.include_router(opportunities_router)
router.include_router(activities_router)
router.include_router(contacts_router)
router.include_router(pipeline_router)
