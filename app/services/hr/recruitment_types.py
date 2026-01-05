"""Type definitions for recruitment service.

These dataclasses define the contract for recruitment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from app.models.hr_recruitment import (
    InterviewResult,
    InterviewStatus,
    JobApplicantStatus,
    JobOfferStatus,
    JobOpeningStatus,
)

__all__ = [
    # Job Opening
    "JobOpeningFilters",
    "JobOpeningCreateData",
    "JobOpeningUpdateData",
    # Job Applicant
    "ApplicantFilters",
    "ApplicantCreateData",
    "ApplicantUpdateData",
    "ApplicantPipelineMove",
    # Interview
    "InterviewFilters",
    "InterviewScheduleData",
    "InterviewUpdateData",
    "InterviewFeedbackData",
    # Job Offer
    "JobOfferFilters",
    "JobOfferCreateData",
    "JobOfferUpdateData",
    "OfferTermData",
    # Results
    "HiringData",
    "RecruitmentMetrics",
    "PipelineSummary",
]


# ==============================================================================
# Job Opening Types
# ==============================================================================


@dataclass
class JobOpeningFilters:
    """Filters for listing job openings."""

    status: Optional[JobOpeningStatus] = None
    department: Optional[str] = None
    department_id: Optional[int] = None
    designation: Optional[str] = None
    designation_id: Optional[int] = None
    company: Optional[str] = None
    publish: Optional[bool] = None
    search: Optional[str] = None


@dataclass
class JobOpeningCreateData:
    """Data for creating a job opening."""

    job_title: str
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    lower_range: Decimal = Decimal("0")
    upper_range: Decimal = Decimal("0")
    currency: str = "NGN"
    publish: bool = False


@dataclass
class JobOpeningUpdateData:
    """Data for updating a job opening (all fields optional)."""

    job_title: Optional[str] = None
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None
    description: Optional[str] = None
    lower_range: Optional[Decimal] = None
    upper_range: Optional[Decimal] = None
    currency: Optional[str] = None
    publish: Optional[bool] = None
    status: Optional[JobOpeningStatus] = None


# ==============================================================================
# Job Applicant Types
# ==============================================================================


@dataclass
class ApplicantFilters:
    """Filters for listing job applicants."""

    job_opening_id: Optional[int] = None
    status: Optional[JobApplicantStatus] = None
    source: Optional[str] = None
    company: Optional[str] = None
    search: Optional[str] = None  # Search name/email


@dataclass
class ApplicantCreateData:
    """Data for creating a job applicant."""

    applicant_name: str
    email_id: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    job_opening_id: Optional[int] = None
    job_opening: Optional[str] = None
    job_title: Optional[str] = None
    cover_letter: Optional[str] = None
    resume_attachment: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None
    company: Optional[str] = None


@dataclass
class ApplicantUpdateData:
    """Data for updating a job applicant (all fields optional)."""

    applicant_name: Optional[str] = None
    email_id: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    cover_letter: Optional[str] = None
    resume_attachment: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None


@dataclass
class ApplicantPipelineMove:
    """Data for moving an applicant through the pipeline."""

    to_status: JobApplicantStatus
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ==============================================================================
# Interview Types
# ==============================================================================


@dataclass
class InterviewFilters:
    """Filters for listing interviews."""

    job_applicant_id: Optional[int] = None
    interviewer_id: Optional[int] = None
    status: Optional[InterviewStatus] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    interview_type: Optional[str] = None


@dataclass
class InterviewScheduleData:
    """Data for scheduling an interview."""

    job_applicant_id: int
    scheduled_date: datetime
    interviewer_id: Optional[int] = None
    interviewer_name: Optional[str] = None
    interview_type: Optional[str] = None  # phone, video, onsite
    duration_minutes: int = 60
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class InterviewUpdateData:
    """Data for updating an interview (all fields optional)."""

    scheduled_date: Optional[datetime] = None
    interviewer_id: Optional[int] = None
    interviewer_name: Optional[str] = None
    interview_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class InterviewFeedbackData:
    """Data for recording interview feedback."""

    result: InterviewResult
    feedback: Optional[str] = None
    rating: Optional[int] = None  # 1-5 scale
    notes: Optional[str] = None


# ==============================================================================
# Job Offer Types
# ==============================================================================


@dataclass
class OfferTermData:
    """Individual term in a job offer."""

    offer_term: str
    value: str
    idx: int = 0


@dataclass
class JobOfferFilters:
    """Filters for listing job offers."""

    job_applicant_id: Optional[int] = None
    status: Optional[JobOfferStatus] = None
    company: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None


@dataclass
class JobOfferCreateData:
    """Data for creating a job offer."""

    job_applicant_id: int
    job_applicant: str
    offer_date: date
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    designation: Optional[str] = None
    base: Decimal = Decimal("0")
    salary_structure: Optional[str] = None
    company: Optional[str] = None
    expiry_date: Optional[date] = None
    terms: List[OfferTermData] = field(default_factory=list)


@dataclass
class JobOfferUpdateData:
    """Data for updating a job offer (all fields optional)."""

    offer_date: Optional[date] = None
    designation: Optional[str] = None
    base: Optional[Decimal] = None
    salary_structure: Optional[str] = None
    expiry_date: Optional[date] = None
    terms: Optional[List[OfferTermData]] = None


# ==============================================================================
# Result Types
# ==============================================================================


@dataclass
class HiringData:
    """Data for converting an accepted offer to an employee."""

    job_offer_id: int
    date_of_joining: date
    department_id: Optional[int] = None
    department: Optional[str] = None
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    employment_type: str = "permanent"
    reports_to_id: Optional[int] = None


@dataclass
class PipelineSummary:
    """Summary of applicants in each pipeline stage."""

    job_opening_id: Optional[int]
    total_applicants: int = 0
    open: int = 0
    screening: int = 0
    interview: int = 0
    offer: int = 0
    accepted: int = 0
    rejected: int = 0
    withdrawn: int = 0


@dataclass
class RecruitmentMetrics:
    """Recruitment metrics and statistics."""

    total_openings: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    total_applicants: int = 0
    applicants_this_month: int = 0
    total_interviews: int = 0
    interviews_this_month: int = 0
    offers_made: int = 0
    offers_accepted: int = 0
    average_time_to_hire_days: Optional[float] = None
    pipeline_by_opening: List[PipelineSummary] = field(default_factory=list)
