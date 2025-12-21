"""Recruitment models for ERPNext HR Module sync."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.hr import Department, Designation
    from app.models.auth import User


# ============= ENUMS =============
class JobOpeningStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class JobApplicantStatus(enum.Enum):
    # Existing values (unchanged)
    OPEN = "open"
    REPLIED = "replied"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    HOLD = "hold"
    # New pipeline stages
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    WITHDRAWN = "withdrawn"


class JobOfferStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AWAITING_RESPONSE = "awaiting_response"
    # New statuses
    EXPIRED = "expired"
    VOIDED = "voided"


class InterviewStatus(enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class InterviewResult(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


# ============= JOB OPENING =============
class JobOpening(Base):
    """Job Opening - open positions/vacancies."""

    __tablename__ = "job_openings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    job_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # Organization references
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("designations.id"), nullable=True, index=True
    )
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status and publishing
    status: Mapped[JobOpeningStatus] = mapped_column(
        Enum(JobOpeningStatus), default=JobOpeningStatus.OPEN, index=True
    )
    publish: Mapped[bool] = mapped_column(default=False)
    route: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Compensation range
    lower_range: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    upper_range: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<JobOpening {self.job_title} ({self.status.value})>"


# ============= JOB APPLICANT =============
class JobApplicant(Base):
    """Job Applicant - candidates applying for positions."""

    __tablename__ = "job_applicants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Applicant info
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Job reference
    job_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    job_opening: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_opening_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_openings.id"), nullable=True, index=True
    )

    # Status
    status: Mapped[JobApplicantStatus] = mapped_column(
        Enum(JobApplicantStatus), default=JobApplicantStatus.OPEN, index=True
    )

    # Application details
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_attachment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Source tracking
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<JobApplicant {self.applicant_name} ({self.status.value})>"


# ============= JOB OFFER =============
class JobOffer(Base):
    """Job Offer - offer letters to candidates."""

    __tablename__ = "job_offers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Applicant reference
    job_applicant: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_applicant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_applicants.id"), nullable=True, index=True
    )
    applicant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applicant_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Position
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Offer details
    offer_date: Mapped[date] = mapped_column(nullable=False, index=True)
    status: Mapped[JobOfferStatus] = mapped_column(
        Enum(JobOfferStatus), default=JobOfferStatus.PENDING, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Compensation
    base: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    salary_structure: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Expiry and void tracking
    expiry_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    voided_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

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
    terms: Mapped[List["JobOfferTerm"]] = relationship(
        back_populates="job_offer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JobOffer {self.applicant_name} ({self.status.value})>"


# ============= JOB OFFER TERM (Child Table) =============
class JobOfferTerm(Base):
    """Job Offer Term - individual terms/conditions in an offer."""

    __tablename__ = "job_offer_terms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_offer_id: Mapped[int] = mapped_column(
        ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    offer_term: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    job_offer: Mapped["JobOffer"] = relationship(back_populates="terms")

    def __repr__(self) -> str:
        return f"<JobOfferTerm {self.offer_term}>"


# ============= INTERVIEW =============
class Interview(Base):
    """Interview - scheduled interviews with applicants."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Applicant reference
    job_applicant_id: Mapped[int] = mapped_column(
        ForeignKey("job_applicants.id"), nullable=False, index=True
    )

    # Scheduling
    scheduled_date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True, default=60)

    # Interviewer
    interviewer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    interviewer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Interview details
    interview_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # phone, video, onsite
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Status and result
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus), default=InterviewStatus.SCHEDULED, index=True
    )
    result: Mapped[Optional[InterviewResult]] = mapped_column(
        Enum(InterviewResult), nullable=True
    )

    # Feedback
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5 scale
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit fields
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_interviews_applicant_date", "job_applicant_id", "scheduled_date"),
    )

    def __repr__(self) -> str:
        return f"<Interview applicant={self.job_applicant_id} on {self.scheduled_date}>"
