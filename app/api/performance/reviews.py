"""
Reviews API - Manager review workflows and score overrides
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    EvaluationPeriod,
    ScoreOverride,
    OverrideReason,
    PerformanceReviewNote,
    KPIResult,
    KRAResult,
)
from app.models.employee import Employee
from app.services.performance_notification_service import PerformanceNotificationService

router = APIRouter(prefix="/reviews", tags=["performance-reviews"])


# ============= SCHEMAS =============
class OverrideReasonEnum(str, Enum):
    data_correction = "data_correction"
    extenuating_circumstances = "extenuating_circumstances"
    partial_period = "partial_period"
    system_error = "system_error"
    managerial_discretion = "managerial_discretion"
    other = "other"


class OverrideCreate(BaseModel):
    override_type: str  # 'kpi', 'kra', or 'overall'
    kpi_result_id: Optional[int] = None
    kra_result_id: Optional[int] = None
    new_score: float
    reason: OverrideReasonEnum
    justification: Optional[str] = None


class OverrideResponse(BaseModel):
    id: int
    scorecard_instance_id: int
    override_type: str
    kpi_result_id: Optional[int]
    kra_result_id: Optional[int]
    original_score: Optional[float]
    overridden_score: Optional[float]
    reason: str
    justification: Optional[str]
    overridden_by_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewNoteCreate(BaseModel):
    content: str
    note_type: Optional[str] = None  # general, improvement, recognition, etc
    kpi_result_id: Optional[int] = None
    kra_result_id: Optional[int] = None
    is_private: bool = False


class ReviewNoteResponse(BaseModel):
    id: int
    scorecard_instance_id: int
    note_type: Optional[str]
    content: str
    kpi_result_id: Optional[int]
    kra_result_id: Optional[int]
    is_private: bool
    created_by_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewQueueItem(BaseModel):
    scorecard_id: int
    employee_id: int
    employee_name: str
    department: Optional[str]
    designation: Optional[str]
    period_name: str
    status: str
    total_score: Optional[float]
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItem]
    total: int
    pending_count: int
    in_review_count: int


# ============= ENDPOINTS =============
@router.get("/queue", response_model=ReviewQueueResponse, dependencies=[Depends(Require("performance:review"))])
async def get_review_queue(
    period_id: Optional[int] = None,
    department: Optional[str] = None,
    # current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get manager's review queue - scorecards pending review."""
    # TODO: Filter by manager's team when auth is implemented

    query = db.query(EmployeeScorecardInstance).filter(
        or_(
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.COMPUTED,
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.IN_REVIEW,
            EmployeeScorecardInstance.status == 'computed',
            EmployeeScorecardInstance.status == 'in_review',
        )
    )

    if period_id:
        query = query.filter(EmployeeScorecardInstance.evaluation_period_id == period_id)

    if department:
        query = query.join(Employee, EmployeeScorecardInstance.employee_id == Employee.id).filter(
            Employee.department == department
        )

    total = query.count()

    # Get counts by status
    pending_count = query.filter(
        or_(
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.COMPUTED,
            EmployeeScorecardInstance.status == 'computed'
        )
    ).count()

    in_review_count = query.filter(
        or_(
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.IN_REVIEW,
            EmployeeScorecardInstance.status == 'in_review'
        )
    ).count()

    scorecards = query.order_by(EmployeeScorecardInstance.updated_at.desc()).offset(offset).limit(limit).all()

    items = []
    for sc in scorecards:
        employee = db.query(Employee).filter(Employee.id == sc.employee_id).first()
        period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == sc.evaluation_period_id).first()

        items.append(ReviewQueueItem(
            scorecard_id=sc.id,
            employee_id=sc.employee_id,
            employee_name=employee.name if employee else "Unknown",
            department=employee.department if employee else None,
            designation=employee.designation if employee else None,
            period_name=period.name if period else "",
            status=sc.status.value if isinstance(sc.status, ScorecardInstanceStatus) else sc.status,
            total_score=float(sc.total_weighted_score) if sc.total_weighted_score else None,
            submitted_at=sc.updated_at,
        ))

    return ReviewQueueResponse(
        items=items,
        total=total,
        pending_count=pending_count,
        in_review_count=in_review_count,
    )


@router.post("/scorecards/{scorecard_id}/approve", dependencies=[Depends(Require("performance:review"))])
async def approve_scorecard(
    scorecard_id: int,
    # current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a scorecard after review."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    valid_statuses = ['computed', 'in_review', ScorecardInstanceStatus.COMPUTED, ScorecardInstanceStatus.IN_REVIEW]
    if scorecard.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Cannot approve scorecard in {scorecard.status} status")

    scorecard.status = ScorecardInstanceStatus.APPROVED
    scorecard.reviewed_at = datetime.utcnow()
    # scorecard.reviewed_by_id = current_user.id  # TODO
    db.commit()

    # Send notification to employee
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    if period:
        notification_service = PerformanceNotificationService(db)
        notification_service.notify_scorecard_approved(scorecard, period, None)

    return {"success": True, "message": "Scorecard approved", "status": "approved"}


@router.post("/scorecards/{scorecard_id}/reject", dependencies=[Depends(Require("performance:review"))])
async def reject_scorecard(
    scorecard_id: int,
    reason: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    """Reject a scorecard (send back for recomputation)."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    valid_statuses = ['computed', 'in_review', ScorecardInstanceStatus.COMPUTED, ScorecardInstanceStatus.IN_REVIEW]
    if scorecard.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Cannot reject scorecard in {scorecard.status} status")

    # Add rejection note
    note = PerformanceReviewNote(
        scorecard_instance_id=scorecard_id,
        note_type="rejection",
        content=f"Scorecard rejected: {reason}",
        is_private=False,
    )
    db.add(note)

    scorecard.status = ScorecardInstanceStatus.DISPUTED
    db.commit()

    # Send notification to employee
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    if period:
        notification_service = PerformanceNotificationService(db)
        notification_service.notify_scorecard_rejected(scorecard, period, reason)

    return {"success": True, "message": "Scorecard rejected", "status": "disputed"}


@router.post("/scorecards/{scorecard_id}/override", response_model=OverrideResponse, dependencies=[Depends(Require("performance:review"))])
async def create_override(
    scorecard_id: int,
    payload: OverrideCreate,
    db: Session = Depends(get_db),
):
    """Create a score override for KPI, KRA, or overall score."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    # Validate override type and get original score
    original_score = None
    if payload.override_type == 'kpi':
        if not payload.kpi_result_id:
            raise HTTPException(status_code=400, detail="kpi_result_id required for KPI override")
        kpi_result = db.query(KPIResult).filter(KPIResult.id == payload.kpi_result_id).first()
        if not kpi_result:
            raise HTTPException(status_code=404, detail="KPI result not found")
        original_score = kpi_result.final_score or kpi_result.computed_score
        kpi_result.final_score = Decimal(str(payload.new_score))

    elif payload.override_type == 'kra':
        if not payload.kra_result_id:
            raise HTTPException(status_code=400, detail="kra_result_id required for KRA override")
        kra_result = db.query(KRAResult).filter(KRAResult.id == payload.kra_result_id).first()
        if not kra_result:
            raise HTTPException(status_code=404, detail="KRA result not found")
        original_score = kra_result.final_score or kra_result.computed_score
        kra_result.final_score = Decimal(str(payload.new_score))

    elif payload.override_type == 'overall':
        original_score = scorecard.total_weighted_score
        scorecard.total_weighted_score = Decimal(str(payload.new_score))

    else:
        raise HTTPException(status_code=400, detail="override_type must be 'kpi', 'kra', or 'overall'")

    # Create audit record
    override = ScoreOverride(
        scorecard_instance_id=scorecard_id,
        override_type=payload.override_type,
        kpi_result_id=payload.kpi_result_id,
        kra_result_id=payload.kra_result_id,
        original_score=original_score,
        overridden_score=Decimal(str(payload.new_score)),
        reason=OverrideReason(payload.reason.value),
        justification=payload.justification,
        # overridden_by_id=current_user.id,  # TODO
    )
    db.add(override)
    db.commit()
    db.refresh(override)

    # Send notification to employee about score override
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    if period:
        notification_service = PerformanceNotificationService(db)
        notification_service.notify_score_overridden(
            scorecard, period,
            float(original_score) if original_score else 0,
            payload.new_score,
            payload.reason.value
        )

    return OverrideResponse(
        id=override.id,
        scorecard_instance_id=override.scorecard_instance_id,
        override_type=override.override_type,
        kpi_result_id=override.kpi_result_id,
        kra_result_id=override.kra_result_id,
        original_score=float(override.original_score) if override.original_score else None,
        overridden_score=float(override.overridden_score) if override.overridden_score else None,
        reason=override.reason.value,
        justification=override.justification,
        overridden_by_id=override.overridden_by_id,
        created_at=override.created_at,
    )


@router.get("/scorecards/{scorecard_id}/overrides", response_model=List[OverrideResponse], dependencies=[Depends(Require("performance:read"))])
async def list_overrides(scorecard_id: int, db: Session = Depends(get_db)):
    """List all overrides for a scorecard."""
    overrides = db.query(ScoreOverride).filter(
        ScoreOverride.scorecard_instance_id == scorecard_id
    ).order_by(ScoreOverride.created_at.desc()).all()

    return [
        OverrideResponse(
            id=o.id,
            scorecard_instance_id=o.scorecard_instance_id,
            override_type=o.override_type,
            kpi_result_id=o.kpi_result_id,
            kra_result_id=o.kra_result_id,
            original_score=float(o.original_score) if o.original_score else None,
            overridden_score=float(o.overridden_score) if o.overridden_score else None,
            reason=o.reason.value,
            justification=o.justification,
            overridden_by_id=o.overridden_by_id,
            created_at=o.created_at,
        )
        for o in overrides
    ]


# ============= NOTES =============
@router.get("/scorecards/{scorecard_id}/notes", response_model=List[ReviewNoteResponse], dependencies=[Depends(Require("performance:read"))])
async def list_notes(
    scorecard_id: int,
    include_private: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List review notes for a scorecard."""
    query = db.query(PerformanceReviewNote).filter(
        PerformanceReviewNote.scorecard_instance_id == scorecard_id
    )

    if not include_private:
        query = query.filter(PerformanceReviewNote.is_private == False)

    notes = query.order_by(PerformanceReviewNote.created_at.desc()).all()

    return [
        ReviewNoteResponse(
            id=n.id,
            scorecard_instance_id=n.scorecard_instance_id,
            note_type=n.note_type,
            content=n.content,
            kpi_result_id=n.kpi_result_id,
            kra_result_id=n.kra_result_id,
            is_private=n.is_private,
            created_by_id=n.created_by_id,
            created_at=n.created_at,
        )
        for n in notes
    ]


@router.post("/scorecards/{scorecard_id}/notes", response_model=ReviewNoteResponse, dependencies=[Depends(Require("performance:review"))])
async def create_note(
    scorecard_id: int,
    payload: ReviewNoteCreate,
    db: Session = Depends(get_db),
):
    """Add a review note to a scorecard."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    note = PerformanceReviewNote(
        scorecard_instance_id=scorecard_id,
        note_type=payload.note_type,
        content=payload.content,
        kpi_result_id=payload.kpi_result_id,
        kra_result_id=payload.kra_result_id,
        is_private=payload.is_private,
        # created_by_id=current_user.id,  # TODO
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return ReviewNoteResponse(
        id=note.id,
        scorecard_instance_id=note.scorecard_instance_id,
        note_type=note.note_type,
        content=note.content,
        kpi_result_id=note.kpi_result_id,
        kra_result_id=note.kra_result_id,
        is_private=note.is_private,
        created_by_id=note.created_by_id,
        created_at=note.created_at,
    )


@router.delete("/scorecards/{scorecard_id}/notes/{note_id}", dependencies=[Depends(Require("performance:review"))])
async def delete_note(scorecard_id: int, note_id: int, db: Session = Depends(get_db)):
    """Delete a review note."""
    note = db.query(PerformanceReviewNote).filter(
        PerformanceReviewNote.id == note_id,
        PerformanceReviewNote.scorecard_instance_id == scorecard_id
    ).first()

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    db.delete(note)
    db.commit()

    return {"success": True, "message": "Note deleted"}


@router.post("/scorecards/{scorecard_id}/finalize", dependencies=[Depends(Require("performance:admin"))])
async def finalize_scorecard(scorecard_id: int, db: Session = Depends(get_db)):
    """Finalize a scorecard (HR action)."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    valid_statuses = ['approved', ScorecardInstanceStatus.APPROVED]
    if scorecard.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Can only finalize approved scorecards")

    scorecard.status = ScorecardInstanceStatus.FINALIZED
    scorecard.finalized_at = datetime.utcnow()
    # scorecard.finalized_by_id = current_user.id  # TODO
    db.commit()

    # Send notifications to employee
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    if period:
        notification_service = PerformanceNotificationService(db)
        notification_service.notify_scorecard_finalized(scorecard, period)
        notification_service.notify_rating_published(scorecard, period)

    return {"success": True, "message": "Scorecard finalized", "status": "finalized"}
