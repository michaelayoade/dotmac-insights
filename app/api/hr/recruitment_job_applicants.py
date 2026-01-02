"""
Job Applicants Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_recruitment import (
    JobApplicant,
    JobApplicantStatus,
    Interview,
    InterviewStatus,
)
from .helpers import csv_response, status_counts, now

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class JobApplicantCreate(BaseModel):
    applicant_name: str
    email_id: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    job_title: Optional[str] = None
    job_opening: Optional[str] = None
    job_opening_id: Optional[int] = None
    status: Optional[JobApplicantStatus] = JobApplicantStatus.OPEN
    cover_letter: Optional[str] = None
    resume_attachment: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None
    company: Optional[str] = None


class JobApplicantUpdate(BaseModel):
    applicant_name: Optional[str] = None
    email_id: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    job_title: Optional[str] = None
    job_opening: Optional[str] = None
    job_opening_id: Optional[int] = None
    status: Optional[JobApplicantStatus] = None
    cover_letter: Optional[str] = None
    resume_attachment: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None
    company: Optional[str] = None


class JobApplicantBulkAction(BaseModel):
    applicant_ids: List[int]


class ScheduleInterviewPayload(BaseModel):
    """Optional interview scheduling details for schedule-interview endpoint."""
    scheduled_date: Optional[datetime] = None
    duration_minutes: Optional[int] = 60
    interviewer_id: Optional[int] = None
    interviewer_name: Optional[str] = None
    interview_type: Optional[str] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# HELPERS
# =============================================================================

def _require_applicant_status(applicant: JobApplicant, allowed: List[JobApplicantStatus]):
    if applicant.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {applicant.status.value if applicant.status else None}",
        )


def _load_applicant(db: Session, applicant_id: int) -> JobApplicant:
    applicant = db.query(JobApplicant).filter(JobApplicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Job applicant not found")
    return applicant


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/job-applicants", dependencies=[Depends(Require("hr:read"))])
async def list_job_applicants(
    status: Optional[str] = None,
    job_opening_id: Optional[int] = None,
    source: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List job applicants with filtering."""
    query = db.query(JobApplicant)

    if status:
        try:
            status_enum = JobApplicantStatus(status)
            query = query.filter(JobApplicant.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if job_opening_id:
        query = query.filter(JobApplicant.job_opening_id == job_opening_id)
    if source:
        query = query.filter(JobApplicant.source.ilike(f"%{source}%"))
    if company:
        query = query.filter(JobApplicant.company.ilike(f"%{company}%"))
    if search:
        query = query.filter(
            (JobApplicant.applicant_name.ilike(f"%{search}%")) |
            (JobApplicant.email_id.ilike(f"%{search}%"))
        )

    total = query.count()
    applicants = query.order_by(JobApplicant.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": a.id,
                "erpnext_id": a.erpnext_id,
                "applicant_name": a.applicant_name,
                "email_id": a.email_id,
                "phone_number": a.phone_number,
                "job_title": a.job_title,
                "job_opening": a.job_opening,
                "job_opening_id": a.job_opening_id,
                "status": a.status.value if a.status else None,
                "source": a.source,
                "company": a.company,
            }
            for a in applicants
        ],
    }


@router.get("/job-applicants/export", dependencies=[Depends(Require("hr:read"))])
async def export_job_applicants(
    status: Optional[str] = None,
    job_opening_id: Optional[int] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export job applicants to CSV."""
    query = db.query(JobApplicant)
    if status:
        try:
            status_enum = JobApplicantStatus(status)
            query = query.filter(JobApplicant.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if job_opening_id:
        query = query.filter(JobApplicant.job_opening_id == job_opening_id)
    if company:
        query = query.filter(JobApplicant.company.ilike(f"%{company}%"))

    rows = [["id", "applicant_name", "email_id", "phone_number", "job_title", "status", "source", "company"]]
    for a in query.order_by(JobApplicant.created_at.desc()).all():
        rows.append([
            str(a.id),
            a.applicant_name,
            a.email_id or "",
            a.phone_number or "",
            a.job_title or "",
            a.status.value if a.status else "",
            a.source or "",
            a.company or "",
        ])
    return csv_response(rows, "job_applicants.csv")


@router.get("/job-applicants/summary", dependencies=[Depends(Require("hr:read"))])
async def job_applicants_summary(
    job_opening_id: Optional[int] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job applicants summary by status."""
    query = db.query(JobApplicant.status, func.count(JobApplicant.id))

    if job_opening_id:
        query = query.filter(JobApplicant.job_opening_id == job_opening_id)
    if company:
        query = query.filter(JobApplicant.company.ilike(f"%{company}%"))

    results = query.group_by(JobApplicant.status).all()

    return {"status_counts": status_counts(results)}


@router.get("/job-applicants/{applicant_id}", dependencies=[Depends(Require("hr:read"))])
async def get_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job applicant detail."""
    a = db.query(JobApplicant).filter(JobApplicant.id == applicant_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Job applicant not found")

    return {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "applicant_name": a.applicant_name,
        "email_id": a.email_id,
        "phone_number": a.phone_number,
        "country": a.country,
        "job_title": a.job_title,
        "job_opening": a.job_opening,
        "job_opening_id": a.job_opening_id,
        "status": a.status.value if a.status else None,
        "cover_letter": a.cover_letter,
        "resume_attachment": a.resume_attachment,
        "source": a.source,
        "source_name": a.source_name,
        "company": a.company,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/job-applicants", dependencies=[Depends(Require("hr:write"))])
async def create_job_applicant(
    payload: JobApplicantCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new job applicant."""
    applicant = JobApplicant(
        applicant_name=payload.applicant_name,
        email_id=payload.email_id,
        phone_number=payload.phone_number,
        country=payload.country,
        job_title=payload.job_title,
        job_opening=payload.job_opening,
        job_opening_id=payload.job_opening_id,
        status=payload.status or JobApplicantStatus.OPEN,
        cover_letter=payload.cover_letter,
        resume_attachment=payload.resume_attachment,
        source=payload.source,
        source_name=payload.source_name,
        company=payload.company,
    )
    db.add(applicant)
    db.commit()
    return await get_job_applicant(applicant.id, db)


@router.patch("/job-applicants/{applicant_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_applicant(
    applicant_id: int,
    payload: JobApplicantUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a job applicant."""
    applicant = db.query(JobApplicant).filter(JobApplicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Job applicant not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(applicant, field, value)

    db.commit()
    return await get_job_applicant(applicant.id, db)


@router.delete("/job-applicants/{applicant_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a job applicant."""
    applicant = db.query(JobApplicant).filter(JobApplicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Job applicant not found")

    db.delete(applicant)
    db.commit()
    return {"message": "Job applicant deleted", "id": applicant_id}


@router.post("/job-applicants/{applicant_id}/accept", dependencies=[Depends(Require("hr:write"))])
async def accept_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Accept a job applicant."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED])
    applicant.status = JobApplicantStatus.ACCEPTED
    db.commit()
    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reject a job applicant."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED, JobApplicantStatus.HOLD])
    applicant.status = JobApplicantStatus.REJECTED
    db.commit()
    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/hold", dependencies=[Depends(Require("hr:write"))])
async def hold_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Put a job applicant on hold."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED])
    applicant.status = JobApplicantStatus.HOLD
    db.commit()
    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/bulk/accept", dependencies=[Depends(Require("hr:write"))])
async def bulk_accept_job_applicants(
    payload: JobApplicantBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk accept job applicants."""
    updated = 0
    for app_id in payload.applicant_ids:
        applicant = db.query(JobApplicant).filter(JobApplicant.id == app_id).first()
        if applicant and applicant.status in [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED]:
            applicant.status = JobApplicantStatus.ACCEPTED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.applicant_ids)}


@router.post("/job-applicants/bulk/reject", dependencies=[Depends(Require("hr:write"))])
async def bulk_reject_job_applicants(
    payload: JobApplicantBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk reject job applicants."""
    updated = 0
    for app_id in payload.applicant_ids:
        applicant = db.query(JobApplicant).filter(JobApplicant.id == app_id).first()
        if applicant and applicant.status in [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED, JobApplicantStatus.HOLD]:
            applicant.status = JobApplicantStatus.REJECTED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.applicant_ids)}


# =============================================================================
# STAGE TRANSITIONS
# =============================================================================

@router.post("/job-applicants/{applicant_id}/screen", dependencies=[Depends(Require("hr:write"))])
async def screen_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to screening stage."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED])

    applicant.status = JobApplicantStatus.SCREENING
    applicant.status_changed_by_id = current_user.id if current_user else None
    applicant.status_changed_at = now()
    db.commit()
    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/schedule-interview", dependencies=[Depends(Require("hr:write"))])
async def schedule_interview_for_applicant(
    applicant_id: int,
    payload: Optional[ScheduleInterviewPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to interview stage. Optionally creates an interview record if scheduling details provided."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED, JobApplicantStatus.SCREENING])

    applicant.status = JobApplicantStatus.INTERVIEW
    applicant.status_changed_by_id = current_user.id if current_user else None
    applicant.status_changed_at = now()

    interview_created = None
    # Create interview record if scheduling details provided
    if payload and payload.scheduled_date:
        interview = Interview(
            job_applicant_id=applicant_id,
            scheduled_date=payload.scheduled_date,
            duration_minutes=payload.duration_minutes or 60,
            interviewer_id=payload.interviewer_id,
            interviewer_name=payload.interviewer_name,
            interview_type=payload.interview_type,
            location=payload.location,
            meeting_link=payload.meeting_link,
            notes=payload.notes,
            status=InterviewStatus.SCHEDULED,
            created_by_id=current_user.id if current_user else None,
            updated_by_id=current_user.id if current_user else None,
        )
        db.add(interview)
        db.flush()  # Get the interview ID
        interview_created = interview.id

    db.commit()

    result = await get_job_applicant(applicant_id, db)
    if interview_created:
        result["interview_id"] = interview_created
    return result


@router.post("/job-applicants/{applicant_id}/make-offer", dependencies=[Depends(Require("hr:write"))])
async def make_offer_to_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to offer stage."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [JobApplicantStatus.INTERVIEW, JobApplicantStatus.SCREENING])

    applicant.status = JobApplicantStatus.OFFER
    applicant.status_changed_by_id = current_user.id if current_user else None
    applicant.status_changed_at = now()
    db.commit()
    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/withdraw", dependencies=[Depends(Require("hr:write"))])
async def withdraw_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark applicant as withdrawn."""
    applicant = _load_applicant(db, applicant_id)
    _require_applicant_status(applicant, [
        JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED,
        JobApplicantStatus.SCREENING, JobApplicantStatus.INTERVIEW,
        JobApplicantStatus.OFFER, JobApplicantStatus.HOLD
    ])

    applicant.status = JobApplicantStatus.WITHDRAWN
    applicant.status_changed_by_id = current_user.id if current_user else None
    applicant.status_changed_at = now()
    db.commit()
    return await get_job_applicant(applicant_id, db)
