"""Type definitions for field service scheduling.

These dataclasses define the contract for scheduling operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Dict, List, Optional

__all__ = [
    "CalendarFilters",
    "CalendarDay",
    "CalendarView",
    "TechnicianSchedule",
    "AvailabilitySlot",
    "TechnicianAvailability",
    "AvailableTechnician",
]


@dataclass
class CalendarFilters:
    """Filters for calendar queries."""

    start_date: date
    end_date: date
    technician_id: Optional[int] = None
    team_id: Optional[int] = None
    zone_id: Optional[int] = None
    company: Optional[str] = None


@dataclass
class CalendarDay:
    """Daily calendar summary."""

    total: int = 0
    completed: int = 0
    in_progress: int = 0
    scheduled: int = 0
    urgent: int = 0


@dataclass
class CalendarView:
    """Complete calendar view result."""

    start_date: str
    end_date: str
    calendar: Dict[str, List[Dict[str, Any]]]  # date -> list of orders
    daily_summary: Dict[str, CalendarDay]


@dataclass
class AvailabilitySlot:
    """A time slot in a technician's schedule."""

    start: str  # time ISO format
    end: str  # time ISO format
    order_id: int
    title: str


@dataclass
class TechnicianAvailability:
    """Availability information for a technician."""

    technician_id: int
    technician_name: str
    date: str
    scheduled_orders: int
    scheduled_hours: float
    available_hours: float
    available_slots: int
    is_available: bool
    scheduled_slots: List[AvailabilitySlot] = field(default_factory=list)


@dataclass
class AvailableTechnician:
    """Technician with availability info."""

    technician_id: int
    technician_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    scheduled_orders: int = 0
    scheduled_hours: float = 0.0
    available_hours: float = 8.0


@dataclass
class TechnicianSchedule:
    """A technician's schedule for a date range."""

    technician_id: int
    technician_name: str
    technician_email: Optional[str]
    start_date: str
    end_date: str
    schedule: Dict[str, List[Dict[str, Any]]]  # date -> list of orders
    total_orders: int
    total_hours_scheduled: float
    completed: int


@dataclass
class ScheduleConflict:
    """Information about a scheduling conflict."""

    technician_id: int
    date: date
    conflicting_order_id: int
    conflict_type: str  # "overlap", "exceeded_capacity", "unavailable"
    message: str
