"""Recruitment service for HR module.

Handles job openings, applicants, interviews, and job offers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.utils.datetime_utils import utc_now
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.hr_recruitment import (
    Interview,
    InterviewResult,
    InterviewStatus,
    JobApplicant,
    JobApplicantStatus,
    JobOffer,
    JobOfferStatus,
    JobOfferTerm,
    JobOpening,
    JobOpeningStatus,
)
from app.services.base import apply_sort, paginate
from app.services.hr.recruitment_types import (
    ApplicantCreateData,
    ApplicantFilters,
    ApplicantPipelineMove,
    ApplicantUpdateData,
    HiringData,
    InterviewFeedbackData,
    InterviewFilters,
    InterviewScheduleData,
    InterviewUpdateData,
    JobOfferCreateData,
    JobOfferFilters,
    JobOfferUpdateData,
    JobOpeningCreateData,
    JobOpeningFilters,
    JobOpeningUpdateData,
    PipelineSummary,
    RecruitmentMetrics,
)
from app.services.hr.errors import (
    ApplicantNotFoundError,
    ApplicantPipelineError,
    InterviewNotFoundError,
    JobOfferNotFoundError,
    JobOpeningNotFoundError,
    OfferExpiredError,
)
from app.services.types import PaginatedResult, PaginationParams, SortParams

if TYPE_CHECKING:
    from app.models.hr_settings import HRSettings
    from app.web.context import Principal

__all__ = ["RecruitmentService"]


# Valid pipeline transitions
PIPELINE_TRANSITIONS = {
    JobApplicantStatus.OPEN: {
        JobApplicantStatus.SCREENING,
        JobApplicantStatus.REJECTED,
        JobApplicantStatus.WITHDRAWN,
    },
    JobApplicantStatus.SCREENING: {
        JobApplicantStatus.INTERVIEW,
        JobApplicantStatus.REJECTED,
        JobApplicantStatus.WITHDRAWN,
    },
    JobApplicantStatus.INTERVIEW: {
        JobApplicantStatus.OFFER,
        JobApplicantStatus.REJECTED,
        JobApplicantStatus.WITHDRAWN,
    },
    JobApplicantStatus.OFFER: {
        JobApplicantStatus.ACCEPTED,
        JobApplicantStatus.REJECTED,
        JobApplicantStatus.WITHDRAWN,
    },
    JobApplicantStatus.REPLIED: {
        JobApplicantStatus.SCREENING,
        JobApplicantStatus.REJECTED,
    },
    JobApplicantStatus.HOLD: {
        JobApplicantStatus.OPEN,
        JobApplicantStatus.SCREENING,
        JobApplicantStatus.REJECTED,
    },
}


class RecruitmentService:
    """Service for recruitment management operations.

    Uses HR settings for configurable behavior:
    - job_posting_validity_days: Default validity period for job postings
    - offer_validity_days: Default validity period for job offers
    - default_interview_duration_minutes: Default interview duration
    - require_background_check: Whether background check is mandatory
    - allow_offer_negotiation: Whether offer negotiation is allowed
    """

    def __init__(
        self, db: Session, principal: Optional["Principal"] = None
    ) -> None:
        self.db = db
        self.principal = principal
        self._settings_cache: dict[str, "HRSettings"] = {}

    def _get_settings(self, company: Optional[str] = None) -> "HRSettings":
        """Get HR settings, using cache for repeated access within same request."""
        cache_key = company or "__default__"
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]

        from .settings import HRSettingsService

        settings_service = HRSettingsService(self.db, self.principal)
        self._settings_cache[cache_key] = settings_service.get_settings(company)
        return self._settings_cache[cache_key]

    # ==========================================================================
    # Job Openings
    # ==========================================================================

    def list_job_openings(
        self,
        filters: Optional[JobOpeningFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[JobOpening]:
        """List job openings with filters."""
        query = select(JobOpening)

        if filters:
            if filters.status is not None:
                query = query.where(JobOpening.status == filters.status)
            if filters.department is not None:
                query = query.where(JobOpening.department.ilike(f"%{filters.department}%"))
            if filters.department_id is not None:
                query = query.where(JobOpening.department_id == filters.department_id)
            if filters.designation is not None:
                query = query.where(JobOpening.designation.ilike(f"%{filters.designation}%"))
            if filters.designation_id is not None:
                query = query.where(JobOpening.designation_id == filters.designation_id)
            if filters.company is not None:
                query = query.where(JobOpening.company == filters.company)
            if filters.publish is not None:
                query = query.where(JobOpening.publish == filters.publish)
            if filters.search:
                query = query.where(
                    JobOpening.job_title.ilike(f"%{filters.search}%")
                )

        if sort:
            query = apply_sort(query, JobOpening, sort)
        else:
            query = query.order_by(JobOpening.created_at.desc())

        return paginate(self.db, query, pagination)

    def get_job_opening(self, opening_id: int) -> JobOpening:
        """Get a job opening by ID."""
        opening = self.db.get(JobOpening, opening_id)
        if not opening:
            raise JobOpeningNotFoundError(opening_id)
        return opening

    def create_job_opening(self, data: JobOpeningCreateData) -> JobOpening:
        """Create a new job opening."""
        opening = JobOpening(
            job_title=data.job_title,
            designation_id=data.designation_id,
            designation=data.designation,
            department_id=data.department_id,
            department=data.department,
            company=data.company,
            description=data.description,
            lower_range=data.lower_range,
            upper_range=data.upper_range,
            currency=data.currency,
            publish=data.publish,
            status=JobOpeningStatus.OPEN,
        )

        if self.principal and self.principal.user_id:
            opening.created_by_id = self.principal.user_id

        self.db.add(opening)
        self.db.flush()
        return opening

    def update_job_opening(
        self, opening_id: int, data: JobOpeningUpdateData
    ) -> JobOpening:
        """Update a job opening."""
        opening = self.get_job_opening(opening_id)

        if data.job_title is not None:
            opening.job_title = data.job_title
        if data.designation_id is not None:
            opening.designation_id = data.designation_id
        if data.designation is not None:
            opening.designation = data.designation
        if data.department_id is not None:
            opening.department_id = data.department_id
        if data.department is not None:
            opening.department = data.department
        if data.description is not None:
            opening.description = data.description
        if data.lower_range is not None:
            opening.lower_range = data.lower_range
        if data.upper_range is not None:
            opening.upper_range = data.upper_range
        if data.currency is not None:
            opening.currency = data.currency
        if data.publish is not None:
            opening.publish = data.publish
        if data.status is not None:
            opening.status = data.status
            opening.status_changed_at = utc_now()
            if self.principal and self.principal.user_id:
                opening.status_changed_by_id = self.principal.user_id

        if self.principal and self.principal.user_id:
            opening.updated_by_id = self.principal.user_id

        self.db.flush()
        return opening

    def close_job_opening(self, opening_id: int) -> JobOpening:
        """Close a job opening."""
        opening = self.get_job_opening(opening_id)
        opening.status = JobOpeningStatus.CLOSED
        opening.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            opening.status_changed_by_id = self.principal.user_id
            opening.updated_by_id = self.principal.user_id
        self.db.flush()
        return opening

    def delete_job_opening(self, opening_id: int) -> None:
        """Delete a job opening."""
        opening = self.get_job_opening(opening_id)
        self.db.delete(opening)
        self.db.flush()

    # ==========================================================================
    # Job Applicants
    # ==========================================================================

    def list_applicants(
        self,
        filters: Optional[ApplicantFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[JobApplicant]:
        """List job applicants with filters."""
        query = select(JobApplicant)

        if filters:
            if filters.job_opening_id is not None:
                query = query.where(
                    JobApplicant.job_opening_id == filters.job_opening_id
                )
            if filters.status is not None:
                query = query.where(JobApplicant.status == filters.status)
            if filters.source is not None:
                query = query.where(JobApplicant.source == filters.source)
            if filters.company is not None:
                query = query.where(JobApplicant.company == filters.company)
            if filters.search:
                query = query.where(
                    or_(
                        JobApplicant.applicant_name.ilike(f"%{filters.search}%"),
                        JobApplicant.email_id.ilike(f"%{filters.search}%"),
                    )
                )

        if sort:
            query = apply_sort(query, JobApplicant, sort)
        else:
            query = query.order_by(JobApplicant.created_at.desc())

        return paginate(self.db, query, pagination)

    def get_applicant(self, applicant_id: int) -> JobApplicant:
        """Get a job applicant by ID."""
        applicant = self.db.get(JobApplicant, applicant_id)
        if not applicant:
            raise ApplicantNotFoundError(applicant_id)
        return applicant

    def create_applicant(self, data: ApplicantCreateData) -> JobApplicant:
        """Create a new job applicant."""
        applicant = JobApplicant(
            applicant_name=data.applicant_name,
            email_id=data.email_id,
            phone_number=data.phone_number,
            country=data.country,
            job_opening_id=data.job_opening_id,
            job_opening=data.job_opening,
            job_title=data.job_title,
            cover_letter=data.cover_letter,
            resume_attachment=data.resume_attachment,
            source=data.source,
            source_name=data.source_name,
            company=data.company,
            status=JobApplicantStatus.OPEN,
        )

        if self.principal and self.principal.user_id:
            applicant.created_by_id = self.principal.user_id

        self.db.add(applicant)
        self.db.flush()
        return applicant

    def update_applicant(
        self, applicant_id: int, data: ApplicantUpdateData
    ) -> JobApplicant:
        """Update a job applicant."""
        applicant = self.get_applicant(applicant_id)

        if data.applicant_name is not None:
            applicant.applicant_name = data.applicant_name
        if data.email_id is not None:
            applicant.email_id = data.email_id
        if data.phone_number is not None:
            applicant.phone_number = data.phone_number
        if data.country is not None:
            applicant.country = data.country
        if data.cover_letter is not None:
            applicant.cover_letter = data.cover_letter
        if data.resume_attachment is not None:
            applicant.resume_attachment = data.resume_attachment
        if data.source is not None:
            applicant.source = data.source
        if data.source_name is not None:
            applicant.source_name = data.source_name

        if self.principal and self.principal.user_id:
            applicant.updated_by_id = self.principal.user_id

        self.db.flush()
        return applicant

    def advance_applicant(
        self, applicant_id: int, data: ApplicantPipelineMove
    ) -> JobApplicant:
        """Move an applicant through the hiring pipeline."""
        applicant = self.get_applicant(applicant_id)

        # Validate transition
        valid_transitions = PIPELINE_TRANSITIONS.get(applicant.status, set())
        if data.to_status not in valid_transitions:
            raise ApplicantPipelineError(
                current_stage=applicant.status.value,
                target_stage=data.to_status.value,
                reason="Invalid pipeline transition",
            )

        applicant.status = data.to_status
        applicant.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            applicant.status_changed_by_id = self.principal.user_id
            applicant.updated_by_id = self.principal.user_id

        self.db.flush()
        return applicant

    def reject_applicant(
        self, applicant_id: int, reason: Optional[str] = None
    ) -> JobApplicant:
        """Reject a job applicant."""
        applicant = self.get_applicant(applicant_id)
        applicant.status = JobApplicantStatus.REJECTED
        applicant.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            applicant.status_changed_by_id = self.principal.user_id
            applicant.updated_by_id = self.principal.user_id
        self.db.flush()
        return applicant

    def delete_applicant(self, applicant_id: int) -> None:
        """Delete a job applicant."""
        applicant = self.get_applicant(applicant_id)
        self.db.delete(applicant)
        self.db.flush()

    # ==========================================================================
    # Interviews
    # ==========================================================================

    def list_interviews(
        self,
        filters: Optional[InterviewFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[Interview]:
        """List interviews with filters."""
        query = select(Interview)

        if filters:
            if filters.job_applicant_id is not None:
                query = query.where(
                    Interview.job_applicant_id == filters.job_applicant_id
                )
            if filters.interviewer_id is not None:
                query = query.where(Interview.interviewer_id == filters.interviewer_id)
            if filters.status is not None:
                query = query.where(Interview.status == filters.status)
            if filters.from_date is not None:
                query = query.where(Interview.scheduled_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(Interview.scheduled_date <= filters.to_date)
            if filters.interview_type is not None:
                query = query.where(Interview.interview_type == filters.interview_type)

        if sort:
            query = apply_sort(query, Interview, sort)
        else:
            query = query.order_by(Interview.scheduled_date.desc())

        return paginate(self.db, query, pagination)

    def get_interview(self, interview_id: int) -> Interview:
        """Get an interview by ID."""
        interview = self.db.get(Interview, interview_id)
        if not interview:
            raise InterviewNotFoundError(interview_id)
        return interview

    def schedule_interview(self, data: InterviewScheduleData) -> Interview:
        """Schedule a new interview."""
        # Verify applicant exists
        applicant = self.get_applicant(data.job_applicant_id)

        interview = Interview(
            job_applicant_id=data.job_applicant_id,
            scheduled_date=data.scheduled_date,
            interviewer_id=data.interviewer_id,
            interviewer_name=data.interviewer_name,
            interview_type=data.interview_type,
            duration_minutes=data.duration_minutes,
            location=data.location,
            meeting_link=data.meeting_link,
            notes=data.notes,
            status=InterviewStatus.SCHEDULED,
        )

        if self.principal and self.principal.user_id:
            interview.created_by_id = self.principal.user_id

        self.db.add(interview)

        # Move applicant to interview stage if in earlier stage
        if applicant.status in [
            JobApplicantStatus.OPEN,
            JobApplicantStatus.SCREENING,
            JobApplicantStatus.REPLIED,
        ]:
            applicant.status = JobApplicantStatus.INTERVIEW
            applicant.status_changed_at = utc_now()
            if self.principal and self.principal.user_id:
                applicant.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return interview

    def update_interview(
        self, interview_id: int, data: InterviewUpdateData
    ) -> Interview:
        """Update an interview."""
        interview = self.get_interview(interview_id)

        if data.scheduled_date is not None:
            interview.scheduled_date = data.scheduled_date
        if data.interviewer_id is not None:
            interview.interviewer_id = data.interviewer_id
        if data.interviewer_name is not None:
            interview.interviewer_name = data.interviewer_name
        if data.interview_type is not None:
            interview.interview_type = data.interview_type
        if data.duration_minutes is not None:
            interview.duration_minutes = data.duration_minutes
        if data.location is not None:
            interview.location = data.location
        if data.meeting_link is not None:
            interview.meeting_link = data.meeting_link
        if data.notes is not None:
            interview.notes = data.notes

        if self.principal and self.principal.user_id:
            interview.updated_by_id = self.principal.user_id

        self.db.flush()
        return interview

    def delete_interview(self, interview_id: int) -> None:
        """Delete an interview."""
        interview = self.get_interview(interview_id)
        self.db.delete(interview)
        self.db.flush()

    def record_interview_feedback(
        self, interview_id: int, data: InterviewFeedbackData
    ) -> Interview:
        """Record feedback for a completed interview."""
        interview = self.get_interview(interview_id)

        interview.status = InterviewStatus.COMPLETED
        interview.result = data.result
        interview.feedback = data.feedback
        interview.rating = data.rating
        if data.notes:
            interview.notes = data.notes
        interview.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            interview.status_changed_by_id = self.principal.user_id
            interview.updated_by_id = self.principal.user_id

        self.db.flush()
        return interview

    def cancel_interview(
        self, interview_id: int, reason: Optional[str] = None
    ) -> Interview:
        """Cancel a scheduled interview."""
        interview = self.get_interview(interview_id)
        interview.status = InterviewStatus.CANCELLED
        interview.status_changed_at = utc_now()
        if reason:
            interview.notes = reason

        if self.principal and self.principal.user_id:
            interview.status_changed_by_id = self.principal.user_id
            interview.updated_by_id = self.principal.user_id

        self.db.flush()
        return interview

    def mark_no_show(self, interview_id: int) -> Interview:
        """Mark an interview as no-show."""
        interview = self.get_interview(interview_id)
        interview.status = InterviewStatus.NO_SHOW
        interview.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            interview.status_changed_by_id = self.principal.user_id
            interview.updated_by_id = self.principal.user_id

        self.db.flush()
        return interview

    # ==========================================================================
    # Job Offers
    # ==========================================================================

    def list_job_offers(
        self,
        filters: Optional[JobOfferFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[JobOffer]:
        """List job offers with filters."""
        query = select(JobOffer)

        if filters:
            if filters.job_applicant_id is not None:
                query = query.where(
                    JobOffer.job_applicant_id == filters.job_applicant_id
                )
            if filters.status is not None:
                query = query.where(JobOffer.status == filters.status)
            if filters.company is not None:
                query = query.where(JobOffer.company == filters.company)
            if filters.from_date is not None:
                query = query.where(JobOffer.offer_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(JobOffer.offer_date <= filters.to_date)

        if sort:
            query = apply_sort(query, JobOffer, sort)
        else:
            query = query.order_by(JobOffer.offer_date.desc())

        return paginate(self.db, query, pagination)

    def get_job_offer(self, offer_id: int) -> JobOffer:
        """Get a job offer by ID."""
        offer = self.db.get(JobOffer, offer_id)
        if not offer:
            raise JobOfferNotFoundError(offer_id)
        return offer

    def create_job_offer(self, data: JobOfferCreateData) -> JobOffer:
        """Create a new job offer."""
        # Verify applicant exists
        applicant = self.get_applicant(data.job_applicant_id)

        offer = JobOffer(
            job_applicant_id=data.job_applicant_id,
            job_applicant=data.job_applicant,
            applicant_name=data.applicant_name or applicant.applicant_name,
            applicant_email=data.applicant_email or applicant.email_id,
            offer_date=data.offer_date,
            designation=data.designation,
            base=data.base,
            salary_structure=data.salary_structure,
            company=data.company,
            expiry_date=data.expiry_date,
            status=JobOfferStatus.PENDING,
        )

        if self.principal and self.principal.user_id:
            offer.created_by_id = self.principal.user_id

        self.db.add(offer)
        self.db.flush()

        # Add offer terms
        for idx, term in enumerate(data.terms):
            self.db.add(
                JobOfferTerm(
                    job_offer_id=offer.id,
                    offer_term=term.offer_term,
                    value=term.value,
                    idx=term.idx or idx,
                )
            )

        # Move applicant to offer stage
        if applicant.status != JobApplicantStatus.OFFER:
            applicant.status = JobApplicantStatus.OFFER
            applicant.status_changed_at = utc_now()
            if self.principal and self.principal.user_id:
                applicant.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def update_job_offer(
        self, offer_id: int, data: JobOfferUpdateData
    ) -> JobOffer:
        """Update a job offer."""
        offer = self.get_job_offer(offer_id)

        if offer.status not in [JobOfferStatus.PENDING, JobOfferStatus.AWAITING_RESPONSE]:
            raise ApplicantPipelineError(
                current_stage=offer.status.value,
                target_stage="update",
                reason="Can only update pending offers",
            )

        if data.offer_date is not None:
            offer.offer_date = data.offer_date
        if data.designation is not None:
            offer.designation = data.designation
        if data.base is not None:
            offer.base = data.base
        if data.salary_structure is not None:
            offer.salary_structure = data.salary_structure
        if data.expiry_date is not None:
            offer.expiry_date = data.expiry_date

        # Replace terms if provided
        if data.terms is not None:
            for term in offer.terms:
                self.db.delete(term)
            for idx, term in enumerate(data.terms):
                self.db.add(
                    JobOfferTerm(
                        job_offer_id=offer.id,
                        offer_term=term.offer_term,
                        value=term.value,
                        idx=term.idx or idx,
                    )
                )

        if self.principal and self.principal.user_id:
            offer.updated_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def delete_job_offer(self, offer_id: int) -> None:
        """Delete a job offer."""
        offer = self.get_job_offer(offer_id)
        self.db.delete(offer)
        self.db.flush()

    def send_job_offer(self, offer_id: int) -> JobOffer:
        """Mark a job offer as sent/awaiting response."""
        offer = self.get_job_offer(offer_id)
        offer.status = JobOfferStatus.AWAITING_RESPONSE
        offer.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            offer.status_changed_by_id = self.principal.user_id
            offer.updated_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def accept_job_offer(self, offer_id: int) -> JobOffer:
        """Mark a job offer as accepted."""
        offer = self.get_job_offer(offer_id)

        # Check if expired
        if offer.expiry_date and offer.expiry_date < date.today():
            raise OfferExpiredError(offer_id, str(offer.expiry_date))

        offer.status = JobOfferStatus.ACCEPTED
        offer.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            offer.status_changed_by_id = self.principal.user_id
            offer.updated_by_id = self.principal.user_id

        # Update applicant status
        if offer.job_applicant_id:
            applicant = self.db.get(JobApplicant, offer.job_applicant_id)
            if applicant:
                applicant.status = JobApplicantStatus.ACCEPTED
                applicant.status_changed_at = utc_now()
                if self.principal and self.principal.user_id:
                    applicant.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def reject_job_offer(self, offer_id: int, reason: Optional[str] = None) -> JobOffer:
        """Mark a job offer as rejected by the candidate."""
        offer = self.get_job_offer(offer_id)
        offer.status = JobOfferStatus.REJECTED
        offer.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            offer.status_changed_by_id = self.principal.user_id
            offer.updated_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def void_job_offer(self, offer_id: int, reason: str) -> JobOffer:
        """Void a job offer (withdraw by employer)."""
        offer = self.get_job_offer(offer_id)
        offer.status = JobOfferStatus.VOIDED
        offer.void_reason = reason
        offer.voided_at = utc_now()
        offer.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            offer.voided_by_id = self.principal.user_id
            offer.status_changed_by_id = self.principal.user_id
            offer.updated_by_id = self.principal.user_id

        self.db.flush()
        return offer

    def convert_to_employee(self, data: HiringData) -> Employee:
        """Convert an accepted job offer to an employee record."""
        from app.services.hr.employees import EmployeeService
        from app.services.hr.employee_types import EmployeeCreateData

        offer = self.get_job_offer(data.job_offer_id)

        if offer.status != JobOfferStatus.ACCEPTED:
            raise ApplicantPipelineError(
                current_stage=offer.status.value,
                target_stage="hire",
                reason="Offer must be accepted before hiring",
            )

        # Get applicant info
        applicant = None
        if offer.job_applicant_id:
            applicant = self.db.get(JobApplicant, offer.job_applicant_id)

        # Create employee
        employee_service = EmployeeService(self.db, self.principal)
        employee_data = EmployeeCreateData(
            name=offer.applicant_name or (applicant.applicant_name if applicant else ""),
            email=offer.applicant_email or (applicant.email_id if applicant else None),
            phone=applicant.phone_number if applicant else None,
            department_id=data.department_id,
            department=data.department,
            designation_id=data.designation_id,
            designation=data.designation or offer.designation,
            reports_to_id=data.reports_to_id,
            employment_type=data.employment_type,
            date_of_joining=data.date_of_joining,
            salary=offer.base,
        )

        employee = employee_service.create_employee(employee_data)

        # Close the job opening if all positions filled
        if offer.job_applicant_id and applicant and applicant.job_opening_id:
            # Could check if positions are filled here
            pass

        return employee

    # ==========================================================================
    # Metrics & Reporting
    # ==========================================================================

    def get_pipeline_summary(
        self, job_opening_id: Optional[int] = None
    ) -> PipelineSummary:
        """Get applicant pipeline summary."""
        query = select(JobApplicant)
        if job_opening_id:
            query = query.where(JobApplicant.job_opening_id == job_opening_id)

        applicants = self.db.scalars(query).all()

        summary = PipelineSummary(job_opening_id=job_opening_id)
        summary.total_applicants = len(applicants)

        for applicant in applicants:
            if applicant.status == JobApplicantStatus.OPEN:
                summary.open += 1
            elif applicant.status == JobApplicantStatus.SCREENING:
                summary.screening += 1
            elif applicant.status == JobApplicantStatus.INTERVIEW:
                summary.interview += 1
            elif applicant.status == JobApplicantStatus.OFFER:
                summary.offer += 1
            elif applicant.status == JobApplicantStatus.ACCEPTED:
                summary.accepted += 1
            elif applicant.status == JobApplicantStatus.REJECTED:
                summary.rejected += 1
            elif applicant.status == JobApplicantStatus.WITHDRAWN:
                summary.withdrawn += 1

        return summary

    def get_recruitment_metrics(self) -> RecruitmentMetrics:
        """Get overall recruitment metrics."""
        metrics = RecruitmentMetrics()

        # Job openings
        metrics.total_openings = self.db.scalar(
            select(func.count(JobOpening.id))
        ) or 0
        metrics.open_positions = self.db.scalar(
            select(func.count(JobOpening.id)).where(
                JobOpening.status == JobOpeningStatus.OPEN
            )
        ) or 0
        metrics.closed_positions = self.db.scalar(
            select(func.count(JobOpening.id)).where(
                JobOpening.status == JobOpeningStatus.CLOSED
            )
        ) or 0

        # Applicants
        metrics.total_applicants = self.db.scalar(
            select(func.count(JobApplicant.id))
        ) or 0

        # This month
        start_of_month = date.today().replace(day=1)
        metrics.applicants_this_month = self.db.scalar(
            select(func.count(JobApplicant.id)).where(
                JobApplicant.created_at >= start_of_month
            )
        ) or 0

        # Interviews
        metrics.total_interviews = self.db.scalar(
            select(func.count(Interview.id))
        ) or 0
        metrics.interviews_this_month = self.db.scalar(
            select(func.count(Interview.id)).where(
                Interview.created_at >= start_of_month
            )
        ) or 0

        # Offers
        metrics.offers_made = self.db.scalar(
            select(func.count(JobOffer.id))
        ) or 0
        metrics.offers_accepted = self.db.scalar(
            select(func.count(JobOffer.id)).where(
                JobOffer.status == JobOfferStatus.ACCEPTED
            )
        ) or 0

        return metrics
