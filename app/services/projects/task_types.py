"""Type definitions for task service.

These dataclasses define the contract for task operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.models.task import TaskStatus, TaskPriority

__all__ = [
    "TaskFilters",
    "TaskDependencyData",
    "TaskCreateData",
    "TaskUpdateData",
]


@dataclass
class TaskFilters:
    """Filters for listing tasks."""

    project_id: Optional[int] = None
    milestone_id: Optional[int] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to_id: Optional[int] = None
    assigned_to: Optional[str] = None  # ERPNext user name
    task_type: Optional[str] = None
    search: Optional[str] = None
    overdue_only: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_group: Optional[bool] = None
    is_template: Optional[bool] = None
    parent_task_id: Optional[int] = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


@dataclass
class TaskDependencyData:
    """Data for a task dependency."""

    dependent_task_id: Optional[int] = None
    dependent_task_erpnext: Optional[str] = None
    subject: Optional[str] = None
    project: Optional[str] = None
    idx: int = 0


@dataclass
class TaskCreateData:
    """Data for creating a task."""

    subject: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    milestone_id: Optional[int] = None
    erpnext_project: Optional[str] = None
    issue: Optional[str] = None
    task_type: Optional[str] = None
    color: Optional[str] = None
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_to: Optional[str] = None
    assigned_to_id: Optional[int] = None
    completed_by: Optional[str] = None
    completed_by_id: Optional[int] = None
    progress: Decimal = Decimal("0")
    expected_time: Decimal = Decimal("0")
    actual_time: Decimal = Decimal("0")
    exp_start_date: Optional[date] = None
    exp_end_date: Optional[date] = None
    act_start_date: Optional[date] = None
    act_end_date: Optional[date] = None
    completed_on: Optional[date] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None
    parent_task_id: Optional[int] = None
    parent_task: Optional[str] = None
    is_group: bool = False
    is_template: bool = False
    company: Optional[str] = None
    department: Optional[str] = None
    total_costing_amount: Decimal = Decimal("0")
    total_billing_amount: Decimal = Decimal("0")
    total_expense_claim: Decimal = Decimal("0")
    template_task: Optional[str] = None
    docstatus: int = 0
    depends_on: Optional[List[TaskDependencyData]] = field(default=None)


@dataclass
class TaskUpdateData:
    """Data for updating a task (all fields optional)."""

    subject: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    milestone_id: Optional[int] = None
    erpnext_project: Optional[str] = None
    issue: Optional[str] = None
    task_type: Optional[str] = None
    color: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to: Optional[str] = None
    assigned_to_id: Optional[int] = None
    completed_by: Optional[str] = None
    completed_by_id: Optional[int] = None
    progress: Optional[Decimal] = None
    expected_time: Optional[Decimal] = None
    actual_time: Optional[Decimal] = None
    exp_start_date: Optional[date] = None
    exp_end_date: Optional[date] = None
    act_start_date: Optional[date] = None
    act_end_date: Optional[date] = None
    completed_on: Optional[date] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None
    parent_task_id: Optional[int] = None
    parent_task: Optional[str] = None
    is_group: Optional[bool] = None
    company: Optional[str] = None
    department: Optional[str] = None
    total_costing_amount: Optional[Decimal] = None
    total_billing_amount: Optional[Decimal] = None
    total_expense_claim: Optional[Decimal] = None
    docstatus: Optional[int] = None
    # None = no change, empty list = clear all
    depends_on: Optional[List[TaskDependencyData]] = None
