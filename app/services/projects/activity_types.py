"""Type definitions for activity service.

These dataclasses define the contract for activity operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.models.project import ProjectActivityType

__all__ = [
    "ActivityFilters",
    "ActivityCreateData",
]


@dataclass
class ActivityFilters:
    """Filters for listing activities."""

    entity_type: Optional[str] = None  # project, task, milestone
    entity_id: Optional[int] = None
    activity_type: Optional[ProjectActivityType] = None
    actor_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


@dataclass
class ActivityCreateData:
    """Data for creating an activity record."""

    entity_type: str  # project, task, milestone
    entity_id: int
    activity_type: ProjectActivityType
    description: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    changed_fields: Optional[List[str]] = None
    company: Optional[str] = None
