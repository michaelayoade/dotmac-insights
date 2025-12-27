"""
Payment and banking integration API endpoints.
"""

from fastapi import APIRouter

from app.api.integrations.payments import router as payments_router
from app.api.integrations.webhooks import router as webhooks_router
from app.api.integrations.transfers import router as transfers_router
from app.api.integrations.banks import router as banks_router
from app.api.integrations.openbanking import router as openbanking_router

# Router for authenticated integration endpoints
router = APIRouter(prefix="/integrations", tags=["integrations"])

router.include_router(payments_router)
router.include_router(transfers_router)
router.include_router(banks_router)
router.include_router(openbanking_router)

# Public-facing router for provider webhooks (no JWT expected)
public_router = APIRouter(prefix="/integrations", tags=["integrations"])
public_router.include_router(webhooks_router)
