"""Purchasing Analytics API endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.services.purchasing import PurchasingAnalyticsService

from ._deps import (
    get_analytics_service,
    RequireRead,
    parse_date,
)

router = APIRouter(prefix="/analytics", tags=["purchasing"])


@router.get("/by-supplier", dependencies=[RequireRead])
async def get_purchases_by_supplier(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    service: PurchasingAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get purchases breakdown by supplier."""
    return service.get_purchases_by_supplier(
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        limit=limit,
    )


@router.get("/by-cost-center", dependencies=[RequireRead])
async def get_expenses_by_cost_center(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: PurchasingAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get expenses breakdown by cost center."""
    return service.get_expenses_by_cost_center(
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
    )


@router.get("/expense-trend", dependencies=[RequireRead])
async def get_expense_trend(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = Query(default="month", pattern="^(day|week|month)$"),
    service: PurchasingAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get expense trend over time."""
    return service.get_expense_trend(
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        granularity=granularity,
    )
