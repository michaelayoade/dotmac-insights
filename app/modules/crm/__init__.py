"""CRM Module - Contact Management with SSR + HTMX."""

from fastapi import APIRouter

from .routes import router as contacts_router
from .leads_routes import router as leads_router
from .opportunities_routes import router as opportunities_router
from .activities_routes import router as activities_router

# Create main CRM router that includes all sub-routers
crm_router = APIRouter()
crm_router.include_router(contacts_router)
crm_router.include_router(leads_router)
crm_router.include_router(opportunities_router)
crm_router.include_router(activities_router)
