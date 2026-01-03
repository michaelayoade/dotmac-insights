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
from app.models.hr_recruitment import (
    JobApplicant,
    JobApplicantStatus,
)
from app.services.hr.recruitment import RecruitmentService
from app.services.hr.recruitment_types import (
    ApplicantCreateData,
    ApplicantFilters,
    ApplicantPipelineMove,
    ApplicantUpdateData,
    InterviewScheduleData,
)
from app.services.hr.errors import (
    ApplicantNotFoundError,
    ApplicantPipelineError,
    ValidationError,
)
from app.services.types import PaginationParams
from .helpers import csv_response, status_counts

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
    status_enum = None
    if status:
        try:
            status_enum = JobApplicantStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = RecruitmentService(db)
    result = service.list_applicants(
        ApplicantFilters(
            job_opening_id=job_opening_id,
            status=status_enum,
            source=source,
            company=company,
            search=search,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    applicants = result.items
    total = result.total

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
    service = RecruitmentService(db)
    try:
        a = service.get_applicant(applicant_id)
    except ApplicantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

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
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new job applicant."""
    service = RecruitmentService(db, principal)
    try:
        applicant = service.create_applicant(
            ApplicantCreateData(
                applicant_name=payload.applicant_name,
                email_id=payload.email_id,
                phone_number=payload.phone_number,
                country=payload.country,
                job_title=payload.job_title,
                job_opening=payload.job_opening,
                job_opening_id=payload.job_opening_id,
                cover_letter=payload.cover_letter,
                resume_attachment=payload.resume_attachment,
                source=payload.source,
                source_name=payload.source_name,
                company=payload.company,
            )
        )
        if payload.status and payload.status != JobApplicantStatus.OPEN:
            service.advance_applicant(
                applicant.id,
                ApplicantPipelineMove(to_status=payload.status),
            )
        db.commit()
    except (ApplicantPipelineError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant.id, db)


@router.patch("/job-applicants/{applicant_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_applicant(
    applicant_id: int,
    payload: JobApplicantUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a job applicant."""
    service = RecruitmentService(db, principal)
    try:
        applicant = service.update_applicant(
            applicant_id,
            ApplicantUpdateData(
                applicant_name=payload.applicant_name,
                email_id=payload.email_id,
                phone_number=payload.phone_number,
                country=payload.country,
                cover_letter=payload.cover_letter,
                resume_attachment=payload.resume_attachment,
                source=payload.source,
                source_name=payload.source_name,
            ),
        )
        if payload.status and payload.status != applicant.status:
            service.advance_applicant(
                applicant_id,
                ApplicantPipelineMove(to_status=payload.status),
            )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (ApplicantPipelineError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant.id, db)


@router.delete("/job-applicants/{applicant_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a job applicant."""
    service = RecruitmentService(db, principal)
    try:
        service.delete_applicant(applicant_id)
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Job applicant deleted", "id": applicant_id}


@router.post("/job-applicants/{applicant_id}/accept", dependencies=[Depends(Require("hr:write"))])
async def accept_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Accept a job applicant."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.ACCEPTED),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject a job applicant."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.REJECTED),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/hold", dependencies=[Depends(Require("hr:write"))])
async def hold_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Put a job applicant on hold."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.HOLD),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/bulk/accept", dependencies=[Depends(Require("hr:write"))])
async def bulk_accept_job_applicants(
    payload: JobApplicantBulkAction,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk accept job applicants."""
    updated = 0
    service = RecruitmentService(db, principal)
    for app_id in payload.applicant_ids:
        try:
            service.advance_applicant(
                app_id,
                ApplicantPipelineMove(to_status=JobApplicantStatus.ACCEPTED),
            )
            updated += 1
        except (ApplicantNotFoundError, ApplicantPipelineError):
            continue
    db.commit()
    return {"updated": updated, "requested": len(payload.applicant_ids)}


@router.post("/job-applicants/bulk/reject", dependencies=[Depends(Require("hr:write"))])
async def bulk_reject_job_applicants(
    payload: JobApplicantBulkAction,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reject job applicants."""
    updated = 0
    service = RecruitmentService(db, principal)
    for app_id in payload.applicant_ids:
        try:
            service.advance_applicant(
                app_id,
                ApplicantPipelineMove(to_status=JobApplicantStatus.REJECTED),
            )
            updated += 1
        except (ApplicantNotFoundError, ApplicantPipelineError):
            continue
    db.commit()
    return {"updated": updated, "requested": len(payload.applicant_ids)}


# =============================================================================
# STAGE TRANSITIONS
# =============================================================================

@router.post("/job-applicants/{applicant_id}/screen", dependencies=[Depends(Require("hr:write"))])
async def screen_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to screening stage."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.SCREENING),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/schedule-interview", dependencies=[Depends(Require("hr:write"))])
async def schedule_interview_for_applicant(
    applicant_id: int,
    payload: Optional[ScheduleInterviewPayload] = None,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to interview stage. Optionally creates an interview record if scheduling details provided."""
    service = RecruitmentService(db, principal)
    interview_created = None
    try:
        if payload and payload.scheduled_date:
            interview = service.schedule_interview(
                InterviewScheduleData(
                    job_applicant_id=applicant_id,
                    scheduled_date=payload.scheduled_date,
                    duration_minutes=payload.duration_minutes or 60,
                    interviewer_id=payload.interviewer_id,
                    interviewer_name=payload.interviewer_name,
                    interview_type=payload.interview_type,
                    location=payload.location,
                    meeting_link=payload.meeting_link,
                    notes=payload.notes,
                )
            )
            interview_created = interview.id
        else:
            service.advance_applicant(
                applicant_id,
                ApplicantPipelineMove(to_status=JobApplicantStatus.INTERVIEW),
            )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (ApplicantPipelineError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    result = await get_job_applicant(applicant_id, db)
    if interview_created:
        result["interview_id"] = interview_created
    return result


@router.post("/job-applicants/{applicant_id}/make-offer", dependencies=[Depends(Require("hr:write"))])
async def make_offer_to_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Move applicant to offer stage."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.OFFER),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)


@router.post("/job-applicants/{applicant_id}/withdraw", dependencies=[Depends(Require("hr:write"))])
async def withdraw_job_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark applicant as withdrawn."""
    service = RecruitmentService(db, principal)
    try:
        service.advance_applicant(
            applicant_id,
            ApplicantPipelineMove(to_status=JobApplicantStatus.WITHDRAWN),
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_applicant(applicant_id, db)
