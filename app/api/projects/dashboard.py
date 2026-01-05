"""
Dashboard Endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.services.projects import ProjectsAnalyticsService

router = APIRouter()

# =============================================================================
# DASHBOARD
# =============================================================================


@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("projects-dashboard", ttl=CACHE_TTL["short"])
async def get_projects_dashboard(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Projects dashboard with project and task metrics.
    """
    service = ProjectsAnalyticsService(db, principal)
    stats = service.get_dashboard_stats()

    return {
        "projects": {
            "total": stats.total_projects,
            "active": stats.active_projects,
            "completed": stats.completed_projects,
            "on_hold": stats.on_hold_projects,
            "cancelled": stats.cancelled_projects,
        },
        "by_priority": stats.by_priority,
        "tasks": {
            "total": stats.total_tasks,
            "open": stats.open_tasks,
            "completed": stats.completed_tasks,
            "overdue": stats.overdue_tasks,
        },
        "financials": {
            "total_estimated": float(stats.total_estimated),
            "total_actual_cost": float(stats.total_actual_cost),
            "total_billed": float(stats.total_billed),
            "variance": float(stats.cost_variance),
        },
        "metrics": {
            "avg_completion_percent": stats.avg_completion_percent,
            "due_this_week": stats.due_this_week,
        },
    }

