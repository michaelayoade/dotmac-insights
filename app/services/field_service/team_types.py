"""Type definitions for field service teams.

These dataclasses define the contract for team operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

__all__ = [
    "TeamFilters",
    "TeamCreateData",
    "TeamUpdateData",
    "TeamMemberData",
    "TechnicianFilters",
    "TechnicianSkillData",
    "ZoneFilters",
    "ZoneCreateData",
    "ZoneUpdateData",
]


@dataclass
class TeamFilters:
    """Filters for team queries."""

    is_active: Optional[bool] = None
    search: Optional[str] = None
    company: Optional[str] = None


@dataclass
class TeamCreateData:
    """Data for creating a field team."""

    name: str
    description: Optional[str] = None
    coverage_zone_ids: Optional[List[int]] = None
    max_daily_orders: int = 10
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    company: Optional[str] = None


@dataclass
class TeamUpdateData:
    """Data for updating a field team (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    coverage_zone_ids: Optional[List[int]] = None
    max_daily_orders: Optional[int] = None
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class TeamMemberData:
    """Data for adding a team member."""

    employee_id: int
    role: str = "technician"  # lead, technician, helper


@dataclass
class TechnicianFilters:
    """Filters for technician queries."""

    team_id: Optional[int] = None
    skill_type: Optional[str] = None
    is_available: Optional[bool] = None
    search: Optional[str] = None
    company: Optional[str] = None


@dataclass
class TechnicianSkillData:
    """Data for adding a technician skill."""

    skill_type: str
    proficiency_level: str = "intermediate"  # basic, intermediate, expert
    certification: Optional[str] = None
    certification_number: Optional[str] = None
    certification_date: Optional[date] = None
    certification_expiry: Optional[date] = None


@dataclass
class ZoneFilters:
    """Filters for zone queries."""

    is_active: Optional[bool] = None
    company: Optional[str] = None


@dataclass
class ZoneCreateData:
    """Data for creating a service zone."""

    name: str
    code: str
    description: Optional[str] = None
    coverage_areas: Optional[List[str]] = None
    center_latitude: Optional[Decimal] = None
    center_longitude: Optional[Decimal] = None
    default_team_id: Optional[int] = None
    company: Optional[str] = None


@dataclass
class ZoneUpdateData:
    """Data for updating a service zone (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    coverage_areas: Optional[List[str]] = None
    center_latitude: Optional[Decimal] = None
    center_longitude: Optional[Decimal] = None
    default_team_id: Optional[int] = None
    is_active: Optional[bool] = None
