"""Type definitions for project service.

These dataclasses define the contract for project operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from app.models.project import ProjectStatus, ProjectPriority

__all__ = [
    "ProjectFilters",
    "ProjectUserData",
    "ProjectCreateData",
    "ProjectUpdateData",
    "ProjectTaskStats",
]


@dataclass
class ProjectFilters:
    """Filters for listing projects."""

    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    customer_account_id: Optional[int] = None
    project_type: Optional[str] = None
    department: Optional[str] = None
    project_manager_id: Optional[int] = None
    search: Optional[str] = None
    overdue_only: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[str] = None  # "Yes" or "No"
    sort_by: str = "created_at"
    sort_dir: str = "desc"


@dataclass
class ProjectUserData:
    """Data for a project team member."""

    user: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    project_status: Optional[str] = None
    view_attachments: bool = True
    welcome_email_sent: bool = False
    idx: int = 0


@dataclass
class ProjectCreateData:
    """Data for creating a project."""

    project_name: str
    project_type: Optional[str] = None
    status: ProjectStatus = ProjectStatus.OPEN
    priority: ProjectPriority = ProjectPriority.MEDIUM
    department: Optional[str] = None
    company: Optional[str] = None
    cost_center: Optional[str] = None
    customer_account_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    erpnext_customer: Optional[str] = None
    erpnext_sales_order: Optional[str] = None
    percent_complete: Decimal = Decimal("0")
    percent_complete_method: Optional[str] = None
    is_active: str = "Yes"
    actual_time: Decimal = Decimal("0")
    total_consumed_material_cost: Decimal = Decimal("0")
    estimated_costing: Decimal = Decimal("0")
    total_costing_amount: Decimal = Decimal("0")
    total_expense_claim: Decimal = Decimal("0")
    total_purchase_cost: Decimal = Decimal("0")
    total_sales_amount: Decimal = Decimal("0")
    total_billable_amount: Decimal = Decimal("0")
    total_billed_amount: Decimal = Decimal("0")
    gross_margin: Decimal = Decimal("0")
    per_gross_margin: Decimal = Decimal("0")
    collect_progress: bool = False
    frequency: Optional[str] = None
    message: Optional[str] = None
    notes: Optional[str] = None
    expected_start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    users: Optional[List[ProjectUserData]] = field(default=None)


@dataclass
class ProjectUpdateData:
    """Data for updating a project (all fields optional)."""

    project_name: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    department: Optional[str] = None
    company: Optional[str] = None
    cost_center: Optional[str] = None
    customer_account_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    erpnext_customer: Optional[str] = None
    erpnext_sales_order: Optional[str] = None
    percent_complete: Optional[Decimal] = None
    percent_complete_method: Optional[str] = None
    is_active: Optional[str] = None
    actual_time: Optional[Decimal] = None
    total_consumed_material_cost: Optional[Decimal] = None
    estimated_costing: Optional[Decimal] = None
    total_costing_amount: Optional[Decimal] = None
    total_expense_claim: Optional[Decimal] = None
    total_purchase_cost: Optional[Decimal] = None
    total_sales_amount: Optional[Decimal] = None
    total_billable_amount: Optional[Decimal] = None
    total_billed_amount: Optional[Decimal] = None
    gross_margin: Optional[Decimal] = None
    per_gross_margin: Optional[Decimal] = None
    collect_progress: Optional[bool] = None
    frequency: Optional[str] = None
    message: Optional[str] = None
    notes: Optional[str] = None
    expected_start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    # None = no change, empty list = clear all
    users: Optional[List[ProjectUserData]] = None


@dataclass
class ProjectTaskStats:
    """Task statistics for a project."""

    total: int
    completed: int
    open: int
    overdue: int
