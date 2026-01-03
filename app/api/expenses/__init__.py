"""Expense Management API router."""
from fastapi import APIRouter

from app.api.expenses import categories, policies, claims, cash_advances, cards, transactions, statements, analytics, reports

router = APIRouter(prefix="/expenses", tags=["expenses"])

router.include_router(categories.router, prefix="/categories")
router.include_router(policies.router, prefix="/policies")
router.include_router(claims.router, prefix="/claims")
router.include_router(cash_advances.router, prefix="/cash-advances")
router.include_router(cards.router, prefix="/cards", tags=["corporate-cards"])
router.include_router(transactions.router, prefix="/transactions", tags=["corporate-cards"])
router.include_router(statements.router, prefix="/statements", tags=["corporate-cards"])
router.include_router(analytics.router, tags=["corporate-card-analytics"])
router.include_router(reports.router, tags=["expense-reports"])
