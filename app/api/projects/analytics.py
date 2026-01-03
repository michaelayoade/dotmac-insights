"""
Analytics Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc, case, extract
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models import (
    Project,
    ProjectStatus,
    ProjectPriority,
    ProjectType,
    ProjectUser,
    ProjectComment,
    ProjectActivity,
    ProjectActivityType,
    ProjectTemplate,
    TaskTemplate,
    MilestoneTemplate,
    Task,
    TaskStatus,
    TaskPriority,
    TaskDependency,
    Milestone,
    MilestoneStatus,
)
from app.models.employee import Employee

router = APIRouter()

# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/status-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_project_status_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly project creation and completion trend."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=months * 30)

    created = db.query(
        extract("year", Project.created_at).label("year"),
        extract("month", Project.created_at).label("month"),
        func.count(Project.id).label("created"),
    ).filter(
        Project.created_at >= start_dt,
    ).group_by(
        extract("year", Project.created_at),
        extract("month", Project.created_at),
    ).all()

    completed = db.query(
        extract("year", Project.actual_end_date).label("year"),
        extract("month", Project.actual_end_date).label("month"),
        func.count(Project.id).label("completed"),
    ).filter(
        Project.actual_end_date >= start_dt,
        Project.status == ProjectStatus.COMPLETED,
    ).group_by(
        extract("year", Project.actual_end_date),
        extract("month", Project.actual_end_date),
    ).all()

    # Merge data
    data_map: Dict[str, Dict[str, Any]] = {}
    for c in created:
        key = f"{int(c.year)}-{int(c.month):02d}"
        data_map[key] = {"period": key, "year": int(c.year), "month": int(c.month), "created": c.created, "completed": 0}
    for c in completed:
        key = f"{int(c.year)}-{int(c.month):02d}"
        if key in data_map:
            data_map[key]["completed"] = c.completed
        else:
            data_map[key] = {"period": key, "year": int(c.year), "month": int(c.month), "created": 0, "completed": c.completed}

    return sorted(data_map.values(), key=lambda x: x["period"])


@router.get("/analytics/task-distribution", dependencies=[Depends(Require("analytics:read"))])
async def get_task_distribution(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get task distribution by status, priority, and assignee."""
    # By status
    by_status = db.query(
        Task.status,
        func.count(Task.id).label("count"),
    ).group_by(Task.status).all()

    # By priority
    by_priority = db.query(
        Task.priority,
        func.count(Task.id).label("count"),
    ).group_by(Task.priority).all()

    # By assignee (top 10)
    by_assignee = db.query(
        Task.assigned_to,
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label("completed"),
    ).filter(
        Task.assigned_to.isnot(None),
    ).group_by(Task.assigned_to).order_by(func.count(Task.id).desc()).limit(10).all()

    return {
        "by_status": [
            {"status": s.status.value, "count": s.count}
            for s in by_status
        ],
        "by_priority": [
            {"priority": p.priority.value, "count": p.count}
            for p in by_priority
        ],
        "by_assignee": [
            {
                "assignee": a.assigned_to,
                "total": a.total,
                "completed": a.completed,
                "completion_rate": round(a.completed / a.total * 100, 1) if a.total > 0 else 0,
            }
            for a in by_assignee
        ],
    }


@router.get("/analytics/project-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("project-performance", ttl=CACHE_TTL["medium"])
async def get_project_performance(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get project performance metrics including budget and timeline adherence."""
    # Budget performance (projects with both estimated and actual costs)
    budget_data = db.query(
        func.count(Project.id).label("total"),
        func.sum(case(
            (Project.total_costing_amount <= Project.estimated_costing, 1),
            else_=0
        )).label("under_budget"),
        func.sum(case(
            (Project.total_costing_amount > Project.estimated_costing, 1),
            else_=0
        )).label("over_budget"),
    ).filter(
        Project.estimated_costing > 0,
        Project.total_costing_amount > 0,
    ).first()

    # Timeline performance (completed projects)
    timeline_data = db.query(
        func.count(Project.id).label("total"),
        func.sum(case(
            (Project.actual_end_date <= Project.expected_end_date, 1),
            else_=0
        )).label("on_time"),
        func.sum(case(
            (Project.actual_end_date > Project.expected_end_date, 1),
            else_=0
        )).label("delayed"),
    ).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.expected_end_date.isnot(None),
        Project.actual_end_date.isnot(None),
    ).first()

    # Average project margin
    avg_margin = db.query(
        func.avg(Project.per_gross_margin)
    ).filter(
        Project.total_billed_amount > 0
    ).scalar() or 0

    # Top profitable projects
    top_projects = db.query(Project).filter(
        Project.gross_margin > 0
    ).order_by(Project.gross_margin.desc()).limit(5).all()

    return {
        "budget": {
            "total_analyzed": budget_data.total if budget_data else 0,
            "under_budget": budget_data.under_budget if budget_data else 0,
            "over_budget": budget_data.over_budget if budget_data else 0,
            "adherence_rate": round(
                (budget_data.under_budget / budget_data.total * 100)
                if budget_data and budget_data.total > 0 else 0, 1
            ),
        },
        "timeline": {
            "total_analyzed": timeline_data.total if timeline_data else 0,
            "on_time": timeline_data.on_time if timeline_data else 0,
            "delayed": timeline_data.delayed if timeline_data else 0,
            "on_time_rate": round(
                (timeline_data.on_time / timeline_data.total * 100)
                if timeline_data and timeline_data.total > 0 else 0, 1
            ),
        },
        "profitability": {
            "avg_margin_percent": round(float(avg_margin), 1),
            "top_projects": [
                {
                    "id": p.id,
                    "project_name": p.project_name,
                    "gross_margin": float(p.gross_margin),
                    "margin_percent": float(p.per_gross_margin),
                }
                for p in top_projects
            ],
        },
    }


@router.get("/analytics/department-summary", dependencies=[Depends(Require("analytics:read"))])
async def get_department_summary(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get project and task summary by department."""
    summary = db.query(
        Project.department,
        func.count(Project.id).label("project_count"),
        func.sum(Project.estimated_costing).label("total_estimated"),
        func.sum(Project.total_billed_amount).label("total_billed"),
        func.avg(Project.percent_complete).label("avg_completion"),
    ).filter(
        Project.department.isnot(None),
        Project.is_deleted == False,
    ).group_by(Project.department).order_by(func.count(Project.id).desc()).limit(15).all()

    result = []
    for s in summary:
        # Get task counts for this department
        task_count = db.query(func.count(Task.id)).join(Project).filter(
            Project.department == s.department
        ).scalar() or 0

        result.append({
            "department": s.department,
            "project_count": s.project_count,
            "task_count": task_count,
            "total_estimated": float(s.total_estimated or 0),
            "total_billed": float(s.total_billed or 0),
            "avg_completion": round(float(s.avg_completion or 0), 1),
        })

    return result
