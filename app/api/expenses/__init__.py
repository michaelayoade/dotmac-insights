"""Expense Management API router."""
from fastapi import APIRouter

from app.api.expenses import categories, policies, claims, cash_advances

router = APIRouter(prefix="/expenses", tags=["expenses"])

router.include_router(categories.router, prefix="/categories")
router.include_router(policies.router, prefix="/policies")
router.include_router(claims.router, prefix="/claims")
router.include_router(cash_advances.router, prefix="/cash-advances")
