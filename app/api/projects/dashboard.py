"""
Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
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
from app.models.customer import Customer
from app.models.employee import Employee

router = APIRouter()

# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("projects-dashboard", ttl=CACHE_TTL["short"])
async def get_projects_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Projects dashboard with project and task metrics.
    """
    # Project counts by status
    project_by_status = db.query(
        Project.status,
        func.count(Project.id).label("count")
    ).filter(Project.is_deleted == False).group_by(Project.status).all()

    status_counts: Dict[str, int] = {
        row.status.value: int(getattr(row, "count", 0) or 0)
        for row in project_by_status
    }
    total_projects: int = sum(status_counts.values())
    active_projects: int = status_counts.get("open", 0)

    # Projects by priority
    by_priority = db.query(
        Project.priority,
        func.count(Project.id).label("count")
    ).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False,
    ).group_by(Project.priority).all()

    priority_counts: Dict[str, int] = {
        row.priority.value: int(getattr(row, "count", 0) or 0)
        for row in by_priority
    }

    # Task counts by status
    task_by_status = db.query(
        Task.status,
        func.count(Task.id).label("count")
    ).group_by(Task.status).all()

    task_status_counts: Dict[str, int] = {
        row.status.value: int(getattr(row, "count", 0) or 0)
        for row in task_by_status
    }
    total_tasks: int = sum(task_status_counts.values())
    open_tasks: int = task_status_counts.get("open", 0) + task_status_counts.get("working", 0)

    # Overdue tasks
    today = date.today()
    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.exp_end_date < today,
        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
    ).scalar() or 0

    # Project financials
    total_estimated = db.query(func.sum(Project.estimated_costing)).filter(Project.is_deleted == False).scalar() or Decimal("0")
    total_actual = db.query(func.sum(Project.total_costing_amount)).filter(Project.is_deleted == False).scalar() or Decimal("0")
    total_billed = db.query(func.sum(Project.total_billed_amount)).filter(Project.is_deleted == False).scalar() or Decimal("0")

    # Average completion
    avg_completion = db.query(
        func.avg(Project.percent_complete)
    ).filter(Project.status == ProjectStatus.OPEN, Project.is_deleted == False).scalar() or Decimal("0")

    # Projects due this week
    week_end = datetime.now(timezone.utc) + timedelta(days=7)
    due_this_week = db.query(func.count(Project.id)).filter(
        Project.expected_end_date <= week_end,
        Project.expected_end_date >= datetime.now(timezone.utc),
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False,
    ).scalar() or 0

    return {
        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": status_counts.get("completed", 0),
            "on_hold": status_counts.get("on_hold", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
        "by_priority": priority_counts,
        "tasks": {
            "total": total_tasks,
            "open": open_tasks,
            "completed": task_status_counts.get("completed", 0),
            "overdue": overdue_tasks,
        },
        "financials": {
            "total_estimated": float(total_estimated),
            "total_actual_cost": float(total_actual),
            "total_billed": float(total_billed),
            "variance": float(total_estimated - total_actual),
        },
        "metrics": {
            "avg_completion_percent": round(float(avg_completion), 1),
            "due_this_week": due_this_week,
        },
    }


