"""
Performance Management Module API

KPI/KRA definitions, scorecards, reviews, and analytics.
"""
from fastapi import APIRouter
from .periods import router as periods_router
from .templates import router as templates_router
from .kpis import router as kpis_router
from .kras import router as kras_router
from .scorecards import router as scorecards_router
from .reviews import router as reviews_router
from .analytics import router as analytics_router

router = APIRouter(prefix="/performance", tags=["performance"])

router.include_router(periods_router)
router.include_router(templates_router)
router.include_router(kpis_router)
router.include_router(kras_router)
router.include_router(scorecards_router)
router.include_router(reviews_router)
router.include_router(analytics_router)
