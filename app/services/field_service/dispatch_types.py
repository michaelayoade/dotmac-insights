"""Type definitions for field service dispatch.

These dataclasses define the contract for dispatch operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

__all__ = [
    "DispatchBoardOrder",
    "DispatchBoardView",
    "TechnicianWorkload",
    "BulkAssignData",
    "BulkAssignResult",
    "RouteSuggestion",
    "RouteOptimizationResult",
]


@dataclass
class DispatchBoardOrder:
    """Order data for dispatch board."""

    id: int
    order_number: str
    title: str
    order_type: str
    status: str
    priority: str
    scheduled_start_time: Optional[str] = None
    estimated_duration_hours: float = 0.0
    customer_name: Optional[str] = None
    service_address: Optional[str] = None
    city: Optional[str] = None
    technician_id: Optional[int] = None
    technician_name: Optional[str] = None
    team_id: Optional[int] = None
    is_overdue: bool = False


@dataclass
class TechnicianWorkload:
    """Technician workload summary."""

    technician_id: int
    technician_name: str
    total_orders: int = 0
    completed: int = 0
    in_progress: int = 0
    pending: int = 0


@dataclass
class DispatchBoardSummary:
    """Dispatch board summary."""

    total: int = 0
    unassigned: int = 0
    assigned: int = 0
    in_field: int = 0
    completed: int = 0


@dataclass
class DispatchBoardView:
    """Complete dispatch board view."""

    date: str
    orders: Dict[str, List[DispatchBoardOrder]]  # status -> orders
    summary: DispatchBoardSummary
    technician_workload: List[TechnicianWorkload]


@dataclass
class BulkAssignData:
    """Data for bulk assigning orders."""

    order_ids: List[int]
    technician_id: int
    team_id: Optional[int] = None
    notify_customers: bool = True


@dataclass
class BulkAssignError:
    """Error from bulk assign operation."""

    order_id: int
    error: str


@dataclass
class BulkAssignResult:
    """Result of bulk assign operation."""

    assigned: List[int]
    assigned_count: int
    technician_name: str
    errors: List[BulkAssignError] = field(default_factory=list)


@dataclass
class RouteSuggestion:
    """Route suggestion for an unassigned order."""

    order_id: int
    order_number: str
    title: str
    customer_name: Optional[str] = None
    service_address: Optional[str] = None
    city: Optional[str] = None
    priority: str = "normal"
    suggested_technician_id: Optional[int] = None
    suggested_technician_name: Optional[str] = None
    confidence_score: int = 0


@dataclass
class RouteOptimizationResult:
    """Result of route optimization."""

    date: str
    unassigned_count: int
    suggestions: List[RouteSuggestion] = field(default_factory=list)
