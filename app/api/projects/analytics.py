"""
Analytics Endpoints
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.services.projects import ProjectsAnalyticsService

router = APIRouter()

# =============================================================================
# ANALYTICS
# =============================================================================


@router.get("/analytics/status-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_project_status_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> List[Dict[str, Any]]:
    """Get monthly project creation and completion trend."""
    service = ProjectsAnalyticsService(db, principal)
    trends = service.get_status_trend(months=months)

    return [
        {
            "period": t.period,
            "year": t.year,
            "month": t.month,
            "created": t.created,
            "completed": t.completed,
        }
        for t in trends
    ]


@router.get("/analytics/task-distribution", dependencies=[Depends(Require("analytics:read"))])
async def get_task_distribution(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get task distribution by status, priority, and assignee."""
    service = ProjectsAnalyticsService(db, principal)
    dist = service.get_task_distribution()

    return {
        "by_status": [
            {"status": s.status, "count": s.count}
            for s in dist.by_status
        ],
        "by_priority": [
            {"priority": p.priority, "count": p.count}
            for p in dist.by_priority
        ],
        "by_assignee": [
            {
                "assignee": a.assignee,
                "total": a.total,
                "completed": a.completed,
                "completion_rate": a.completion_rate,
            }
            for a in dist.by_assignee
        ],
    }


@router.get("/analytics/project-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("project-performance", ttl=CACHE_TTL["medium"])
async def get_project_performance(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get project performance metrics including budget and timeline adherence."""
    service = ProjectsAnalyticsService(db, principal)
    perf = service.get_project_performance()

    return {
        "budget": {
            "total_analyzed": perf.budget_total_analyzed,
            "under_budget": perf.budget_under,
            "over_budget": perf.budget_over,
            "adherence_rate": perf.budget_adherence_rate,
        },
        "timeline": {
            "total_analyzed": perf.timeline_total_analyzed,
            "on_time": perf.timeline_on_time,
            "delayed": perf.timeline_delayed,
            "on_time_rate": perf.timeline_on_time_rate,
        },
        "profitability": {
            "avg_margin_percent": perf.avg_margin_percent,
            "top_projects": [
                {
                    "id": p.id,
                    "project_name": p.project_name,
                    "gross_margin": p.gross_margin,
                    "margin_percent": p.margin_percent,
                }
                for p in perf.top_projects
            ],
        },
    }


@router.get("/analytics/department-summary", dependencies=[Depends(Require("analytics:read"))])
async def get_department_summary(
    limit: int = Query(default=15, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> List[Dict[str, Any]]:
    """Get project and task summary by department."""
    service = ProjectsAnalyticsService(db, principal)
    summaries = service.get_department_summary(limit=limit)

    return [
        {
            "department": s.department,
            "project_count": s.project_count,
            "task_count": s.task_count,
            "total_estimated": s.total_estimated,
            "total_billed": s.total_billed,
            "avg_completion": s.avg_completion,
        }
        for s in summaries
    ]
