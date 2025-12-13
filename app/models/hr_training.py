"""Training models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.auth import User


# ============= ENUMS =============
class TrainingEventStatus(enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrainingResultStatus(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


# ============= TRAINING PROGRAM =============
class TrainingProgram(Base):
    """Training Program - training course definitions."""

    __tablename__ = "training_programs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    training_program_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trainer info
    trainer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trainer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # External trainer

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TrainingProgram {self.training_program_name}>"


# ============= TRAINING EVENT =============
class TrainingEvent(Base):
    """Training Event - scheduled training sessions."""

    __tablename__ = "training_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    event_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # Program reference
    training_program: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    training_program_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_programs.id"), nullable=True, index=True
    )

    # Event details
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Internal, External, Seminar
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Beginner, Intermediate, Expert
    status: Mapped[TrainingEventStatus] = mapped_column(
        Enum(TrainingEventStatus), default=TrainingEventStatus.SCHEDULED, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Schedule
    start_time: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Trainer
    trainer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trainer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Content
    course: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    introduction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employees: Mapped[List["TrainingEventEmployee"]] = relationship(
        back_populates="training_event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TrainingEvent {self.event_name} ({self.status.value})>"


# ============= TRAINING EVENT EMPLOYEE (Child Table) =============
class TrainingEventEmployee(Base):
    """Training Event Employee - employees registered for training."""

    __tablename__ = "training_event_employees"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    training_event_id: Mapped[int] = mapped_column(
        ForeignKey("training_events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Attendance tracking
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Invited, Confirmed, Attended
    attendance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    training_event: Mapped["TrainingEvent"] = relationship(back_populates="employees")

    def __repr__(self) -> str:
        return f"<TrainingEventEmployee {self.employee_name}>"


# ============= TRAINING RESULT =============
class TrainingResult(Base):
    """Training Result - employee training outcomes/scores."""

    __tablename__ = "training_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Training event reference
    training_event: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    training_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_events.id"), nullable=True, index=True
    )

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Results
    hours: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    result: Mapped[TrainingResultStatus] = mapped_column(
        Enum(TrainingResultStatus), default=TrainingResultStatus.PENDING, index=True
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_training_results_event_emp", "training_event_id", "employee_id"),
    )

    def __repr__(self) -> str:
        return f"<TrainingResult {self.employee_name} - {self.result.value}>"
