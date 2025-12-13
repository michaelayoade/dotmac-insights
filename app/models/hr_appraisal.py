"""Appraisal/Performance models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.auth import User


# ============= ENUMS =============
class AppraisalStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ============= APPRAISAL TEMPLATE =============
class AppraisalTemplate(Base):
    """Appraisal Template - appraisal structure/format definition."""

    __tablename__ = "appraisal_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    template_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    goals: Mapped[List["AppraisalTemplateGoal"]] = relationship(
        back_populates="appraisal_template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AppraisalTemplate {self.template_name}>"


# ============= APPRAISAL TEMPLATE GOAL (Child Table) =============
class AppraisalTemplateGoal(Base):
    """Appraisal Template Goal - KRA definitions in a template."""

    __tablename__ = "appraisal_template_goals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appraisal_template_id: Mapped[int] = mapped_column(
        ForeignKey("appraisal_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    kra: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Key Result Area
    per_weightage: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    appraisal_template: Mapped["AppraisalTemplate"] = relationship(back_populates="goals")

    def __repr__(self) -> str:
        return f"<AppraisalTemplateGoal {self.kra}: {self.per_weightage}%>"


# ============= APPRAISAL =============
class Appraisal(Base):
    """Appraisal - employee performance appraisal."""

    __tablename__ = "appraisals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Template reference
    appraisal_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    appraisal_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("appraisal_templates.id"), nullable=True, index=True
    )

    # Appraisal period
    start_date: Mapped[date] = mapped_column(nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(nullable=False)

    # Status
    status: Mapped[AppraisalStatus] = mapped_column(
        Enum(AppraisalStatus), default=AppraisalStatus.DRAFT, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Scores
    total_score: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    self_score: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    final_score: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Feedback
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reflections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    goals: Mapped[List["AppraisalGoal"]] = relationship(
        back_populates="appraisal", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_appraisals_emp_period", "employee_id", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<Appraisal {self.employee_name} ({self.start_date} to {self.end_date})>"


# ============= APPRAISAL GOAL (Child Table) =============
class AppraisalGoal(Base):
    """Appraisal Goal - individual goal scores in an appraisal."""

    __tablename__ = "appraisal_goals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appraisal_id: Mapped[int] = mapped_column(
        ForeignKey("appraisals.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    kra: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    per_weightage: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_earned: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    self_score: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    appraisal: Mapped["Appraisal"] = relationship(back_populates="goals")

    def __repr__(self) -> str:
        return f"<AppraisalGoal {self.kra}: {self.score_earned}>"
