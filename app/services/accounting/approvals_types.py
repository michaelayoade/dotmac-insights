"""Type definitions for approval workflow service."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

__all__ = [
    "ApprovalListFilters",
    "WorkflowFilters",
    "WorkflowCreateData",
    "WorkflowUpdateData",
    "WorkflowStepCreateData",
    "ControlsUpdateData",
]


@dataclass
class ApprovalListFilters:
    """Filters for listing document approvals."""

    doctype: Optional[str] = None


@dataclass
class WorkflowFilters:
    """Filters for listing approval workflows."""

    query: Optional[str] = None
    doctype: Optional[str] = None
    status: Optional[str] = None


@dataclass
class WorkflowCreateData:
    """Data for creating an approval workflow."""

    workflow_name: str
    doctype: str
    description: Optional[str] = None
    is_active: bool = True
    is_mandatory: bool = False
    escalation_enabled: bool = False
    escalation_hours: int = 24


@dataclass
class WorkflowUpdateData:
    """Data for updating an approval workflow."""

    workflow_name: str
    doctype: str
    description: Optional[str] = None
    is_active: bool = True
    is_mandatory: bool = False
    escalation_enabled: bool = False
    escalation_hours: int = 24


@dataclass
class WorkflowStepCreateData:
    """Data for creating a workflow step."""

    step_order: int
    step_name: str
    approval_mode: str = "any"
    role_required: Optional[str] = None
    user_id: Optional[int] = None
    amount_threshold_min: Optional[Decimal] = None
    amount_threshold_max: Optional[Decimal] = None


@dataclass
class ControlsUpdateData:
    """Data for updating accounting controls."""

    require_approval_journal_entry: bool = False
    require_approval_payment: bool = False
    backdating_days_allowed: int = 30
