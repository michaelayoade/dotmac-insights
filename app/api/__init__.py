from fastapi import APIRouter
from app.api import (
    sync,
    analytics,
    data_explorer,
    admin,
    insights,
    finance,
    hr,
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
from app.api.sales_pkg import router as sales_router
from app.api import auth as auth_router
from app.api import expenses
from app.api.tax import router as tax_router
from app.api.integrations import public_router as public_integrations_router
from app.assets import router as assets_router
from app.api.asset_settings import router as asset_settings_router
from app.api.crm import router as crm_router
from app.api.field_service import router as field_service_router
from app.api.inbox import router as inbox_router
from app.api.omni import public_router as public_omni_router
from app.api.platform import router as platform_router
from app.api.payroll_config import router as payroll_config_router
from app.api.workflow_tasks import router as workflow_tasks_router
from app.api.migration import router as migration_router
from app.api.admin_sync import router as admin_sync_router
from app.api.reports import router as reports_router
from app.api.search import router as search_router

api_router = APIRouter()

# Versioned prefixes (v1) for API clients
api_router.include_router(sales_router, prefix="/v1/sales", tags=["sales"])
api_router.include_router(accounting.router, prefix="/v1/accounting", tags=["accounting"])
api_router.include_router(purchasing.router, prefix="/v1/purchasing", tags=["purchasing"])
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
api_router.include_router(analytics.router, prefix="/v1/analytics", tags=["analytics"])
api_router.include_router(insights.router, prefix="/v1/insights", tags=["insights"])
api_router.include_router(data_explorer.router, prefix="/v1/explore", tags=["data-explorer"])
api_router.include_router(hr.router, prefix="/v1/hr", tags=["hr"])
api_router.include_router(projects.router, prefix="/v1/projects", tags=["projects"])
api_router.include_router(field_service_router, prefix="/v1")
api_router.include_router(sync.router, prefix="/v1/sync", tags=["sync"])
api_router.include_router(admin.router, prefix="/v1")
api_router.include_router(admin_sync_router, prefix="/v1", tags=["admin-sync"])
api_router.include_router(platform_router, prefix="/v1")
api_router.include_router(entitlements.router, prefix="/v1")
api_router.include_router(payroll_config_router, prefix="/v1")
api_router.include_router(workflow_tasks_router, prefix="/v1", tags=["workflow-tasks"])
api_router.include_router(zoho_import.router, prefix="/v1")
api_router.include_router(migration_router, prefix="/v1")
api_router.include_router(reports_router, prefix="/v1")
api_router.include_router(search_router, tags=["search"])

# Public (unauthenticated) routers
public_api_router = APIRouter()
public_api_router.include_router(auth_router.router)
public_api_router.include_router(public_integrations_router)
public_api_router.include_router(public_omni_router)
