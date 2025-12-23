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
    entitlements,
)
from app.api import auth as auth_router
from app.api import expenses
from app.api.tax import router as tax_router
from app.api.integrations import router as integrations_router, public_router as public_integrations_router
from app.assets import router as assets_router
from app.api.asset_settings import router as asset_settings_router
from app.api.crm import router as crm_router
from app.api.field_service import router as field_service_router
from app.api.inbox import router as inbox_router
from app.api.contacts import router as contacts_router
from app.api.performance import router as performance_router
from app.api.omni import public_router as public_omni_router
from app.api.platform import router as platform_router
from app.api.payroll_config import router as payroll_config_router
from app.api.tax_core import router as tax_core_router
from app.api.vehicles import router as vehicles_router
from app.api.dashboards import router as dashboards_router
from app.api.workflow_tasks import router as workflow_tasks_router

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
api_router.include_router(customers.router, prefix="/v1/customers", tags=["customers"])
api_router.include_router(finance.router, prefix="/v1/finance", tags=["finance"])
api_router.include_router(tax_router, prefix="/v1/tax", tags=["tax"])
api_router.include_router(books_settings.router, prefix="/v1", tags=["books-settings"])
api_router.include_router(hr_settings.router, prefix="/v1", tags=["hr-settings"])
api_router.include_router(support_settings.router, prefix="/v1", tags=["support-settings"])
api_router.include_router(settings.router, prefix="/v1", tags=["settings"])
api_router.include_router(expenses.router, prefix="/v1", tags=["expenses"])
api_router.include_router(support.router, prefix="/v1/support", tags=["support"])
api_router.include_router(network.router, prefix="/v1/network", tags=["network"])
api_router.include_router(inventory.router, prefix="/v1", tags=["inventory"])
api_router.include_router(assets_router, prefix="/v1", tags=["assets"])
api_router.include_router(asset_settings_router, prefix="/v1", tags=["asset-settings"])
api_router.include_router(crm_router, prefix="/v1", tags=["crm"])
api_router.include_router(inbox_router, prefix="/v1", tags=["inbox"])
api_router.include_router(contacts_router, prefix="/v1")
api_router.include_router(performance_router, prefix="/v1")
api_router.include_router(analytics.router, prefix="/v1/analytics", tags=["analytics"])
api_router.include_router(insights.router, prefix="/v1/insights", tags=["insights"])
api_router.include_router(data_explorer.router, prefix="/v1/explore", tags=["data-explorer"])
api_router.include_router(hr.router, prefix="/v1/hr", tags=["hr"])
api_router.include_router(projects.router, prefix="/v1/projects", tags=["projects"])
api_router.include_router(field_service_router, prefix="/v1")
api_router.include_router(integrations_router, prefix="/v1")
api_router.include_router(sync.router, prefix="/v1/sync", tags=["sync"])
api_router.include_router(admin.router, prefix="/v1")
api_router.include_router(platform_router, prefix="/v1")
api_router.include_router(entitlements.router, prefix="/v1")
api_router.include_router(payroll_config_router, prefix="/v1")
api_router.include_router(tax_core_router, prefix="/v1")
api_router.include_router(vehicles_router, prefix="/v1", tags=["vehicles"])
api_router.include_router(dashboards_router, prefix="/v1", tags=["dashboards"])
api_router.include_router(workflow_tasks_router, prefix="/v1", tags=["workflow-tasks"])
api_router.include_router(zoho_import.router, prefix="/v1")
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(network.router, prefix="/network", tags=["network"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(assets_router, tags=["assets"])
api_router.include_router(asset_settings_router, tags=["asset-settings"])
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
api_router.include_router(platform_router)  # Already has /platform prefix
api_router.include_router(entitlements.router)
api_router.include_router(payroll_config_router)  # Generic payroll configuration
api_router.include_router(tax_core_router)  # Generic tax configuration
api_router.include_router(vehicles_router, tags=["vehicles"])  # Fleet/Vehicle management
api_router.include_router(dashboards_router, tags=["dashboards"])  # Consolidated dashboards
api_router.include_router(workflow_tasks_router, tags=["workflow-tasks"])  # Unified workflow tasks

# Import routers
api_router.include_router(zoho_import.router)  # Already has /zoho-import prefix

# Public (unauthenticated) routers
public_api_router = APIRouter()
public_api_router.include_router(auth_router.router)
public_api_router.include_router(public_integrations_router)  # /integrations/webhooks
public_api_router.include_router(public_omni_router)  # /omni/webhooks
