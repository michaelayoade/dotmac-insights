from fastapi import APIRouter
from app.api import sync, customers, analytics, data_explorer, admin, insights, finance, support, network, zoho_import, accounting, purchasing, books_settings, hr_settings, support_settings

api_router = APIRouter()

# Domain routers (new structure)
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(finance.router, prefix="/finance", tags=["finance"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["accounting"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(books_settings.router, tags=["books-settings"])
api_router.include_router(hr_settings.router, tags=["hr-settings"])
api_router.include_router(support_settings.router, tags=["support-settings"])
# Versioned prefixes (v1) for newer clients
api_router.include_router(accounting.router, prefix="/v1/accounting", tags=["accounting"])
api_router.include_router(purchasing.router, prefix="/v1/purchasing", tags=["purchasing"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(network.router, prefix="/network", tags=["network"])

# Legacy routers (to be deprecated)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(data_explorer.router, prefix="/explore", tags=["data-explorer"])

# System routers
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(admin.router)  # Already has /admin prefix

# Import routers
api_router.include_router(zoho_import.router)  # Already has /zoho-import prefix
