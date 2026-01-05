"""
Gantt Endpoints
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
from app.models.employee import Employee

router = APIRouter()

# =============================================================================
# GANTT CHART DATA
# =============================================================================


@router.get("/projects/{project_id}/gantt", dependencies=[Depends(Require("explorer:read"))])
async def get_project_gantt_data(
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all tasks with full dependency data for Gantt chart visualization.
    Returns tasks with their dependencies in a format optimized for rendering.
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all tasks for this project
    tasks = db.query(Task).filter(Task.project_id == project_id).all()

    # Build task list with dependencies
    task_list = []
    min_date = None
    max_date = None

    for task in tasks:
        # Extract dependency IDs
        depends_on_ids = [
            dep.dependent_task_id
            for dep in task.depends_on
            if dep.dependent_task_id is not None
        ]

        task_data = {
            "id": task.id,
            "subject": task.subject,
            "status": task.status.value if task.status else "open",
            "priority": task.priority.value if task.priority else "medium",
            "progress": float(task.progress) if task.progress else 0,
            "exp_start_date": task.exp_start_date.isoformat() if task.exp_start_date else None,
            "exp_end_date": task.exp_end_date.isoformat() if task.exp_end_date else None,
            "assigned_to": task.assigned_to,
            "parent_task_id": task.parent_task_id,
            "is_group": task.is_group,
            "depends_on": depends_on_ids,
        }
        task_list.append(task_data)

        # Track date range
        if task.exp_start_date:
            if min_date is None or task.exp_start_date < min_date:
                min_date = task.exp_start_date
        if task.exp_end_date:
            if max_date is None or task.exp_end_date > max_date:
                max_date = task.exp_end_date

    return {
        "tasks": task_list,
        "date_range": {
            "min_date": min_date.isoformat() if min_date else None,
            "max_date": max_date.isoformat() if max_date else None,
        },
    }

