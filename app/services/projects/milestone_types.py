"""Type definitions for milestone service.

These dataclasses define the contract for milestone operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models.project import MilestoneStatus

__all__ = [
    "MilestoneFilters",
    "MilestoneCreateData",
    "MilestoneUpdateData",
    "MilestoneProgress",
]


@dataclass
class MilestoneFilters:
    """Filters for listing milestones."""

    project_id: Optional[int] = None
    status: Optional[MilestoneStatus] = None
    overdue_only: bool = False
    search: Optional[str] = None
    sort_by: str = "idx"
    sort_dir: str = "asc"


@dataclass
class MilestoneCreateData:
    """Data for creating a milestone."""

    project_id: int
    name: str
    description: Optional[str] = None
    status: MilestoneStatus = MilestoneStatus.PLANNED
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    percent_complete: Decimal = Decimal("0")
    idx: Optional[int] = None  # If None, will be auto-calculated
    company: Optional[str] = None


@dataclass
class MilestoneUpdateData:
    """Data for updating a milestone (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[MilestoneStatus] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    percent_complete: Optional[Decimal] = None
    idx: Optional[int] = None


@dataclass
class MilestoneProgress:
    """Progress information for a milestone."""

    total_tasks: int
    completed_tasks: int
    percent_complete: Decimal
