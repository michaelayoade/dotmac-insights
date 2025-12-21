"""Lifecycle Events models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.auth import User


# ============= ENUMS =============
class BoardingStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ============= EMPLOYEE ONBOARDING =============
class EmployeeOnboarding(Base):
    """Employee Onboarding - onboarding process tracking."""

    __tablename__ = "employee_onboardings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Recruitment links
    job_applicant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_offer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Onboarding details
    date_of_joining: Mapped[Optional[date]] = mapped_column(nullable=True, index=True)
    boarding_status: Mapped[BoardingStatus] = mapped_column(
        Enum(BoardingStatus), default=BoardingStatus.PENDING, index=True
    )

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Template
    employee_onboarding_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    activities: Mapped[List["EmployeeOnboardingActivity"]] = relationship(
        back_populates="employee_onboarding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmployeeOnboarding {self.employee_name} ({self.boarding_status.value})>"


# ============= EMPLOYEE ONBOARDING ACTIVITY (Child Table) =============
class EmployeeOnboardingActivity(Base):
    """Employee Onboarding Activity - individual onboarding tasks."""

    __tablename__ = "employee_onboarding_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_onboarding_id: Mapped[int] = mapped_column(
        ForeignKey("employee_onboardings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    activity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    required_for_employee_creation: Mapped[bool] = mapped_column(default=False)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Pending, Completed
    completed_on: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    employee_onboarding: Mapped["EmployeeOnboarding"] = relationship(back_populates="activities")

    def __repr__(self) -> str:
        return f"<EmployeeOnboardingActivity {self.activity_name}>"


# ============= EMPLOYEE SEPARATION =============
class EmployeeSeparation(Base):
    """Employee Separation - offboarding/exit process tracking."""

    __tablename__ = "employee_separations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Separation details
    resignation_letter_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    separation_date: Mapped[Optional[date]] = mapped_column(nullable=True, index=True)
    boarding_status: Mapped[BoardingStatus] = mapped_column(
        Enum(BoardingStatus), default=BoardingStatus.PENDING, index=True
    )

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Exit details
    reason_for_leaving: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_interview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Template
    employee_separation_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    activities: Mapped[List["EmployeeSeparationActivity"]] = relationship(
        back_populates="employee_separation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmployeeSeparation {self.employee_name} ({self.boarding_status.value})>"


# ============= EMPLOYEE SEPARATION ACTIVITY (Child Table) =============
class EmployeeSeparationActivity(Base):
    """Employee Separation Activity - individual offboarding tasks."""

    __tablename__ = "employee_separation_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_separation_id: Mapped[int] = mapped_column(
        ForeignKey("employee_separations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    activity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Pending, Completed
    completed_on: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    employee_separation: Mapped["EmployeeSeparation"] = relationship(back_populates="activities")

    def __repr__(self) -> str:
        return f"<EmployeeSeparationActivity {self.activity_name}>"


# ============= EMPLOYEE PROMOTION =============
class EmployeePromotion(Base):
    """Employee Promotion - promotion records."""

    __tablename__ = "employee_promotions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Promotion details
    promotion_date: Mapped[date] = mapped_column(nullable=False, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)

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
    details: Mapped[List["EmployeePromotionDetail"]] = relationship(
        back_populates="employee_promotion", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmployeePromotion {self.employee_name} on {self.promotion_date}>"


# ============= EMPLOYEE PROMOTION DETAIL (Child Table) =============
class EmployeePromotionDetail(Base):
    """Employee Promotion Detail - what changed in the promotion."""

    __tablename__ = "employee_promotion_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_promotion_id: Mapped[int] = mapped_column(
        ForeignKey("employee_promotions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    property: Mapped[str] = mapped_column(String(100), nullable=False)  # designation, department, grade, etc.
    current: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    employee_promotion: Mapped["EmployeePromotion"] = relationship(back_populates="details")

    def __repr__(self) -> str:
        return f"<EmployeePromotionDetail {self.property}: {self.current} -> {self.new}>"


# ============= EMPLOYEE TRANSFER =============
class EmployeeTransfer(Base):
    """Employee Transfer - transfer records."""

    __tablename__ = "employee_transfers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Employee reference
    employee: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Transfer details
    transfer_date: Mapped[date] = mapped_column(nullable=False, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)

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
    details: Mapped[List["EmployeeTransferDetail"]] = relationship(
        back_populates="employee_transfer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmployeeTransfer {self.employee_name} on {self.transfer_date}>"


# ============= EMPLOYEE TRANSFER DETAIL (Child Table) =============
class EmployeeTransferDetail(Base):
    """Employee Transfer Detail - what changed in the transfer."""

    __tablename__ = "employee_transfer_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_transfer_id: Mapped[int] = mapped_column(
        ForeignKey("employee_transfers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    property: Mapped[str] = mapped_column(String(100), nullable=False)  # department, branch, etc.
    current: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    employee_transfer: Mapped["EmployeeTransfer"] = relationship(back_populates="details")

    def __repr__(self) -> str:
        return f"<EmployeeTransferDetail {self.property}: {self.current} -> {self.new}>"
