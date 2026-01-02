"""Type definitions for training service.

These dataclasses define the contract for training operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from app.models.hr_training import TrainingEventStatus, TrainingResultStatus

__all__ = [
    # Training Program
    "TrainingProgramFilters",
    "TrainingProgramCreateData",
    "TrainingProgramUpdateData",
    # Training Event
    "TrainingEventFilters",
    "TrainingEventCreateData",
    "TrainingEventUpdateData",
    "EventEmployeeData",
    # Training Result
    "TrainingResultFilters",
    "TrainingResultCreateData",
    "TrainingResultUpdateData",
    # Results
    "BulkRegistrationData",
    "BulkRegistrationResult",
    "TrainingMetrics",
    "EmployeeTrainingHistory",
]


# ==============================================================================
# Training Program Types
# ==============================================================================


@dataclass
class TrainingProgramFilters:
    """Filters for listing training programs."""

    search: Optional[str] = None  # Search name/description
    trainer_name: Optional[str] = None
    supplier: Optional[str] = None


@dataclass
class TrainingProgramCreateData:
    """Data for creating a training program."""

    training_program_name: str
    description: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    supplier: Optional[str] = None


@dataclass
class TrainingProgramUpdateData:
    """Data for updating a training program (all fields optional)."""

    training_program_name: Optional[str] = None
    description: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    supplier: Optional[str] = None


# ==============================================================================
# Training Event Types
# ==============================================================================


@dataclass
class EventEmployeeData:
    """Employee registration for a training event."""

    employee_id: int
    employee: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    status: str = "Invited"  # Invited, Confirmed, Attended
    idx: int = 0


@dataclass
class TrainingEventFilters:
    """Filters for listing training events."""

    training_program_id: Optional[int] = None
    status: Optional[TrainingEventStatus] = None
    type: Optional[str] = None  # Internal, External, Seminar
    level: Optional[str] = None  # Beginner, Intermediate, Expert
    company: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    search: Optional[str] = None


@dataclass
class TrainingEventCreateData:
    """Data for creating a training event."""

    event_name: str
    training_program_id: Optional[int] = None
    training_program: Optional[str] = None
    type: Optional[str] = None  # Internal, External, Seminar
    level: Optional[str] = None  # Beginner, Intermediate, Expert
    company: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    course: Optional[str] = None
    introduction: Optional[str] = None
    employees: List[EventEmployeeData] = field(default_factory=list)


@dataclass
class TrainingEventUpdateData:
    """Data for updating a training event (all fields optional)."""

    event_name: Optional[str] = None
    training_program_id: Optional[int] = None
    training_program: Optional[str] = None
    type: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    course: Optional[str] = None
    introduction: Optional[str] = None
    status: Optional[TrainingEventStatus] = None
    employees: Optional[List[EventEmployeeData]] = None


# ==============================================================================
# Training Result Types
# ==============================================================================


@dataclass
class TrainingResultFilters:
    """Filters for listing training results."""

    training_event_id: Optional[int] = None
    employee_id: Optional[int] = None
    result: Optional[TrainingResultStatus] = None


@dataclass
class TrainingResultCreateData:
    """Data for creating a training result."""

    training_event_id: int
    training_event: str
    employee_id: int
    employee: str
    employee_name: Optional[str] = None
    hours: Decimal = Decimal("0")
    grade: Optional[str] = None
    result: TrainingResultStatus = TrainingResultStatus.PENDING
    comments: Optional[str] = None


@dataclass
class TrainingResultUpdateData:
    """Data for updating a training result (all fields optional)."""

    hours: Optional[Decimal] = None
    grade: Optional[str] = None
    result: Optional[TrainingResultStatus] = None
    comments: Optional[str] = None


# ==============================================================================
# Bulk & Result Types
# ==============================================================================


@dataclass
class BulkRegistrationData:
    """Data for bulk registering employees to a training event."""

    training_event_id: int
    employee_ids: List[int]
    status: str = "Invited"


@dataclass
class BulkRegistrationResult:
    """Result of bulk registration."""

    registered_count: int = 0
    skipped_count: int = 0
    skipped_employees: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class EmployeeTrainingHistory:
    """Training history for an employee."""

    employee_id: int
    employee_name: str
    total_trainings: int = 0
    completed: int = 0
    passed: int = 0
    failed: int = 0
    pending: int = 0
    total_hours: Decimal = Decimal("0")


@dataclass
class TrainingMetrics:
    """Training metrics and statistics."""

    total_programs: int = 0
    total_events: int = 0
    scheduled_events: int = 0
    completed_events: int = 0
    cancelled_events: int = 0
    total_participants: int = 0
    participants_this_month: int = 0
    total_training_hours: Decimal = Decimal("0")
    pass_rate: Optional[Decimal] = None
