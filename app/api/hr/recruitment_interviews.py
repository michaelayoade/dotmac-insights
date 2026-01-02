"""
Interviews Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_recruitment import (
    Interview,
    InterviewStatus,
    InterviewResult,
    JobApplicant,
    JobApplicantStatus,
)
from .helpers import now

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class InterviewCreate(BaseModel):
    job_applicant_id: int
    scheduled_date: datetime
    duration_minutes: Optional[int] = 60
    interviewer_id: Optional[int] = None
    interviewer_name: Optional[str] = None
    interview_type: Optional[str] = None  # phone, video, onsite
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class InterviewUpdate(BaseModel):
    """Update interview details. Note: status/result changes should use dedicated action endpoints
    (complete, cancel, no-show) which enforce proper state transitions."""
    scheduled_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    interviewer_id: Optional[int] = None
    interviewer_name: Optional[str] = None
    interview_type: Optional[str] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    # status deliberately excluded - use /complete, /cancel, /no-show endpoints
    # result deliberately excluded - set via /complete endpoint
    feedback: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


class CompleteInterviewPayload(BaseModel):
    result: InterviewResult
    feedback: Optional[str] = None
    rating: Optional[int] = None


# =============================================================================
# HELPERS
# =============================================================================

def _load_interview(db: Session, interview_id: int) -> Interview:
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def _require_interview_status(interview: Interview, allowed: List[InterviewStatus]):
    if interview.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {interview.status.value if interview.status else None}",
        )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/interviews", dependencies=[Depends(Require("hr:read"))])
async def list_interviews(
    job_applicant_id: Optional[int] = None,
    interviewer_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List interviews with filtering."""
    query = db.query(Interview)

    if job_applicant_id:
        query = query.filter(Interview.job_applicant_id == job_applicant_id)
    if interviewer_id:
        query = query.filter(Interview.interviewer_id == interviewer_id)
    if status:
        try:
            status_enum = InterviewStatus(status)
            query = query.filter(Interview.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(func.date(Interview.scheduled_date) >= from_date)
    if to_date:
        query = query.filter(func.date(Interview.scheduled_date) <= to_date)

    total = query.count()
    interviews = query.order_by(Interview.scheduled_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": i.id,
                "job_applicant_id": i.job_applicant_id,
                "scheduled_date": i.scheduled_date.isoformat() if i.scheduled_date else None,
                "duration_minutes": i.duration_minutes,
                "interviewer_id": i.interviewer_id,
                "interviewer_name": i.interviewer_name,
                "interview_type": i.interview_type,
                "status": i.status.value if i.status else None,
                "result": i.result.value if i.result else None,
                "rating": i.rating,
            }
            for i in interviews
        ],
    }


@router.get("/interviews/{interview_id}", dependencies=[Depends(Require("hr:read"))])
async def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get interview detail."""
    i = db.query(Interview).filter(Interview.id == interview_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {
        "id": i.id,
        "job_applicant_id": i.job_applicant_id,
        "scheduled_date": i.scheduled_date.isoformat() if i.scheduled_date else None,
        "duration_minutes": i.duration_minutes,
        "interviewer_id": i.interviewer_id,
        "interviewer_name": i.interviewer_name,
        "interview_type": i.interview_type,
        "location": i.location,
        "meeting_link": i.meeting_link,
        "status": i.status.value if i.status else None,
        "result": i.result.value if i.result else None,
        "feedback": i.feedback,
        "rating": i.rating,
        "notes": i.notes,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


@router.post("/interviews", dependencies=[Depends(Require("hr:write"))])
async def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Schedule a new interview. Automatically moves applicant to INTERVIEW stage if in an earlier stage."""
    # Verify applicant exists
    applicant = db.query(JobApplicant).filter(JobApplicant.id == payload.job_applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Job applicant not found")

    # Validate applicant is in a schedulable status
    schedulable_statuses = [
        JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED,
        JobApplicantStatus.SCREENING, JobApplicantStatus.INTERVIEW,
    ]
    if applicant.status not in schedulable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot schedule interview for applicant in {applicant.status.value if applicant.status else 'unknown'} status"
        )

    # Automatically move applicant to INTERVIEW stage if in an earlier stage
    earlier_stages = [JobApplicantStatus.OPEN, JobApplicantStatus.REPLIED, JobApplicantStatus.SCREENING]
    applicant_moved = False
    if applicant.status in earlier_stages:
        applicant.status = JobApplicantStatus.INTERVIEW
        applicant.status_changed_by_id = current_user.id if current_user else None
        applicant.status_changed_at = now()
        applicant_moved = True

    interview = Interview(
        job_applicant_id=payload.job_applicant_id,
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
    db.commit()

    result = await get_interview(interview.id, db)
    if applicant_moved:
        result["applicant_status_changed"] = True
        result["applicant_new_status"] = JobApplicantStatus.INTERVIEW.value
    return result


@router.patch("/interviews/{interview_id}", dependencies=[Depends(Require("hr:write"))])
async def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an interview (reschedule, add feedback, etc.). Only SCHEDULED interviews can be modified."""
    interview = _load_interview(db, interview_id)

    # Only allow updates on scheduled interviews
    if interview.status != InterviewStatus.SCHEDULED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update interview in {interview.status.value if interview.status else 'unknown'} status. "
                   f"Only scheduled interviews can be modified."
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(interview, field, value)

    interview.updated_by_id = current_user.id if current_user else None
    db.commit()
    return await get_interview(interview_id, db)


@router.delete("/interviews/{interview_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an interview."""
    interview = _load_interview(db, interview_id)
    db.delete(interview)
    db.commit()
    return {"message": "Interview deleted", "id": interview_id}


@router.post("/interviews/{interview_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_interview(
    interview_id: int,
    payload: CompleteInterviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark interview as completed with result and optional feedback."""
    interview = _load_interview(db, interview_id)
    _require_interview_status(interview, [InterviewStatus.SCHEDULED])

    interview.status = InterviewStatus.COMPLETED
    interview.result = payload.result
    if payload.feedback:
        interview.feedback = payload.feedback
    if payload.rating is not None:
        if payload.rating < 1 or payload.rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        interview.rating = payload.rating
    interview.status_changed_by_id = current_user.id if current_user else None
    interview.status_changed_at = now()
    interview.updated_by_id = current_user.id if current_user else None

    db.commit()
    return await get_interview(interview_id, db)


@router.post("/interviews/{interview_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a scheduled interview."""
    interview = _load_interview(db, interview_id)
    _require_interview_status(interview, [InterviewStatus.SCHEDULED])

    interview.status = InterviewStatus.CANCELLED
    interview.status_changed_by_id = current_user.id if current_user else None
    interview.status_changed_at = now()
    interview.updated_by_id = current_user.id if current_user else None

    db.commit()
    return await get_interview(interview_id, db)


@router.post("/interviews/{interview_id}/no-show", dependencies=[Depends(Require("hr:write"))])
async def mark_interview_no_show(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark interview as no-show."""
    interview = _load_interview(db, interview_id)
    _require_interview_status(interview, [InterviewStatus.SCHEDULED])

    interview.status = InterviewStatus.NO_SHOW
    interview.status_changed_by_id = current_user.id if current_user else None
    interview.status_changed_at = now()
    interview.updated_by_id = current_user.id if current_user else None

    db.commit()
    return await get_interview(interview_id, db)
