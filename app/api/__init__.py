from fastapi import APIRouter
from app.api import sync, customers, analytics, data_explorer, admin, insights

api_router = APIRouter()

api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(data_explorer.router, prefix="/explore", tags=["data-explorer"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(admin.router)  # Already has /admin prefix
