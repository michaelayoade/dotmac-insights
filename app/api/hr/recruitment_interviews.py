"""
Interviews Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.hr_recruitment import (
    Interview,
    InterviewStatus,
    InterviewResult,
)
from app.services.hr.recruitment import RecruitmentService
from app.services.hr.recruitment_types import (
    InterviewFeedbackData,
    InterviewFilters,
    InterviewScheduleData,
    InterviewUpdateData,
)
from app.services.hr.errors import (
    ApplicantNotFoundError,
    ApplicantPipelineError,
    InterviewNotFoundError,
    ValidationError,
)
from app.services.types import PaginationParams

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
    status_enum = None
    if status:
        try:
            status_enum = InterviewStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = RecruitmentService(db)
    result = service.list_interviews(
        InterviewFilters(
            job_applicant_id=job_applicant_id,
            interviewer_id=interviewer_id,
            status=status_enum,
            from_date=from_date,
            to_date=to_date,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    interviews = result.items
    total = result.total

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
    service = RecruitmentService(db)
    try:
        i = service.get_interview(interview_id)
    except InterviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

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
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Schedule a new interview. Automatically moves applicant to INTERVIEW stage if in an earlier stage."""
    service = RecruitmentService(db, principal)
    try:
        interview = service.schedule_interview(
            InterviewScheduleData(
                job_applicant_id=payload.job_applicant_id,
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
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (ApplicantPipelineError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_interview(interview.id, db)


@router.patch("/interviews/{interview_id}", dependencies=[Depends(Require("hr:write"))])
async def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an interview (reschedule, add feedback, etc.). Only SCHEDULED interviews can be modified."""
    if payload.feedback or payload.rating is not None:
        raise HTTPException(status_code=400, detail="Use /complete to record feedback or rating")

    service = RecruitmentService(db, principal)
    try:
        interview = service.get_interview(interview_id)
        if interview.status != InterviewStatus.SCHEDULED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot update interview in {interview.status.value if interview.status else 'unknown'} status. "
                       f"Only scheduled interviews can be modified."
            )
        service.update_interview(
            interview_id,
            InterviewUpdateData(
                scheduled_date=payload.scheduled_date,
                duration_minutes=payload.duration_minutes,
                interviewer_id=payload.interviewer_id,
                interviewer_name=payload.interviewer_name,
                interview_type=payload.interview_type,
                location=payload.location,
                meeting_link=payload.meeting_link,
                notes=payload.notes,
            ),
        )
        db.commit()
    except InterviewNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_interview(interview_id, db)


@router.delete("/interviews/{interview_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an interview."""
    service = RecruitmentService(db, principal)
    try:
        service.delete_interview(interview_id)
        db.commit()
    except InterviewNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Interview deleted", "id": interview_id}


@router.post("/interviews/{interview_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_interview(
    interview_id: int,
    payload: CompleteInterviewPayload,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark interview as completed with result and optional feedback."""
    if payload.rating is not None and (payload.rating < 1 or payload.rating > 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    service = RecruitmentService(db, principal)
    try:
        interview = service.get_interview(interview_id)
        _require_interview_status(interview, [InterviewStatus.SCHEDULED])
        service.record_interview_feedback(
            interview_id,
            InterviewFeedbackData(
                result=payload.result,
                feedback=payload.feedback,
                rating=payload.rating,
            ),
        )
        db.commit()
    except InterviewNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_interview(interview_id, db)


@router.post("/interviews/{interview_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a scheduled interview."""
    service = RecruitmentService(db, principal)
    try:
        interview = service.get_interview(interview_id)
        _require_interview_status(interview, [InterviewStatus.SCHEDULED])
        service.cancel_interview(interview_id)
        db.commit()
    except InterviewNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_interview(interview_id, db)


@router.post("/interviews/{interview_id}/no-show", dependencies=[Depends(Require("hr:write"))])
async def mark_interview_no_show(
    interview_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark interview as no-show."""
    service = RecruitmentService(db, principal)
    try:
        interview = service.get_interview(interview_id)
        _require_interview_status(interview, [InterviewStatus.SCHEDULED])
        service.mark_no_show(interview_id)
        db.commit()
    except InterviewNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_interview(interview_id, db)
