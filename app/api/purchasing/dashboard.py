"""Purchasing Dashboard API endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.services.purchasing import PurchasingDashboardService

from ._deps import (
    get_dashboard_service,
    RequireRead,
    parse_date,
)

router = APIRouter(tags=["purchasing"])


@router.get("/dashboard", dependencies=[RequireRead])
async def get_purchasing_dashboard(
    as_of_date: str | None = None,
    service: PurchasingDashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """Get purchasing/AP overview dashboard with key metrics."""
    cutoff = parse_date(as_of_date, "as_of_date")
    metrics = service.get_dashboard_metrics(cutoff)

    return {
        "as_of_date": (cutoff or __import__("datetime").date.today()).isoformat(),
        "total_outstanding": float(metrics.total_outstanding),
        "total_overdue": float(metrics.total_overdue),
        "overdue_percentage": metrics.overdue_percentage,
        "supplier_count": metrics.supplier_count,
        "status_breakdown": metrics.status_breakdown,
        "due_this_week": metrics.due_this_week,
        "top_suppliers": metrics.top_suppliers,
    }
