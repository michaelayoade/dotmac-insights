from fastapi import APIRouter
from app.api import (
    sync,
    customers,
    analytics,
    data_explorer,
    admin,
    insights,
    finance,
    hr,
    sales,
    support,
    network,
    zoho_import,
    accounting,
    purchasing,
    books_settings,
    hr_settings,
    support_settings,
    settings,
    inventory,
    projects,
)
from app.api import expenses
from app.api.tax import router as tax_router
from app.api.integrations import router as integrations_router, public_router as public_integrations_router
from app.assets import router as assets_router
from app.api.crm import router as crm_router
from app.api.field_service import router as field_service_router
from app.api.inbox import router as inbox_router
from app.api.contacts import router as contacts_router
from app.api.performance import router as performance_router
from app.api.omni import public_router as public_omni_router

api_router = APIRouter()

# Domain routers (new structure)
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(finance.router, prefix="/finance", tags=["finance"])
api_router.include_router(sales.router, tags=["sales"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["accounting"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(tax_router, prefix="/tax", tags=["tax"])
api_router.include_router(books_settings.router, tags=["books-settings"])
api_router.include_router(hr_settings.router, tags=["hr-settings"])
api_router.include_router(support_settings.router, tags=["support-settings"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(expenses.router, tags=["expenses"])
# Versioned prefixes (v1) for newer clients
api_router.include_router(sales.router, prefix="/v1", tags=["sales"])
api_router.include_router(accounting.router, prefix="/v1/accounting", tags=["accounting"])
api_router.include_router(purchasing.router, prefix="/v1/purchasing", tags=["purchasing"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(network.router, prefix="/network", tags=["network"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(assets_router, tags=["assets"])
api_router.include_router(crm_router, tags=["crm"])  # CRM: leads, opportunities, activities
api_router.include_router(inbox_router, tags=["inbox"])  # Omnichannel inbox
api_router.include_router(contacts_router)  # Unified contacts (replaces CRM contacts)
api_router.include_router(performance_router)  # Performance management module

# Legacy routers (to be deprecated)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(data_explorer.router, prefix="/explore", tags=["data-explorer"])

# HR router
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])

# Projects router
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

# Field Service router
api_router.include_router(field_service_router)  # Already has /field-service prefix

# Payment & Banking integrations
api_router.include_router(integrations_router)  # Already has /integrations prefix

# System routers
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(admin.router)  # Already has /admin prefix

# Import routers
api_router.include_router(zoho_import.router)  # Already has /zoho-import prefix

# Public (unauthenticated) routers
public_api_router = APIRouter()
public_api_router.include_router(public_integrations_router)  # /integrations/webhooks
public_api_router.include_router(public_omni_router)  # /omni/webhooks
