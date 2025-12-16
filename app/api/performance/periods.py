"""
Evaluation Periods API - Period lifecycle management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    EvaluationPeriod,
    EvaluationPeriodType,
    EvaluationPeriodStatus,
    EmployeeScorecardInstance,
)

router = APIRouter(prefix="/periods", tags=["performance-periods"])


# ============= SCHEMAS =============
class PeriodTypeEnum(str, Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    semi_annual = "semi_annual"
    annual = "annual"
    custom = "custom"


class PeriodStatusEnum(str, Enum):
    draft = "draft"
    active = "active"
    scoring = "scoring"
    review = "review"
    finalized = "finalized"
    archived = "archived"


class PeriodCreate(BaseModel):
    code: str
    name: str
    period_type: PeriodTypeEnum
    start_date: date
    end_date: date
    scoring_deadline: Optional[date] = None
    review_deadline: Optional[date] = None


class PeriodUpdate(BaseModel):
    name: Optional[str] = None
    scoring_deadline: Optional[date] = None
    review_deadline: Optional[date] = None


class PeriodResponse(BaseModel):
    id: int
    code: str
    name: str
    period_type: str
    status: str
    start_date: date
    end_date: date
    scoring_deadline: Optional[date]
    review_deadline: Optional[date]
    created_at: datetime
    updated_at: datetime
    scorecard_count: int = 0
    computed_count: int = 0
    finalized_count: int = 0

    class Config:
        from_attributes = True


class PeriodListResponse(BaseModel):
    items: List[PeriodResponse]
    total: int


# ============= ENDPOINTS =============
@router.get("", response_model=PeriodListResponse, dependencies=[Depends(Require("performance:read"))])
async def list_periods(
    status: Optional[PeriodStatusEnum] = None,
    period_type: Optional[PeriodTypeEnum] = None,
    year: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List evaluation periods with filtering."""
    query = db.query(EvaluationPeriod)

    if status:
        query = query.filter(EvaluationPeriod.status == EvaluationPeriodStatus(status.value))

    if period_type:
        query = query.filter(EvaluationPeriod.period_type == EvaluationPeriodType(period_type.value))

    if year:
        query = query.filter(
            func.extract('year', EvaluationPeriod.start_date) == year
        )

    total = query.count()
    periods = query.order_by(EvaluationPeriod.start_date.desc()).offset(offset).limit(limit).all()

    items = []
    for p in periods:
        # Get scorecard stats
        scorecard_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == p.id
        ).scalar() or 0

        computed_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == p.id,
            EmployeeScorecardInstance.status.in_(['computed', 'in_review', 'approved', 'finalized'])
        ).scalar() or 0

        finalized_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == p.id,
            EmployeeScorecardInstance.status == 'finalized'
        ).scalar() or 0

        items.append(PeriodResponse(
            id=p.id,
            code=p.code,
            name=p.name,
            period_type=p.period_type.value,
            status=p.status.value,
            start_date=p.start_date,
            end_date=p.end_date,
            scoring_deadline=p.scoring_deadline,
            review_deadline=p.review_deadline,
            created_at=p.created_at,
            updated_at=p.updated_at,
            scorecard_count=scorecard_count,
            computed_count=computed_count,
            finalized_count=finalized_count,
        ))

    return PeriodListResponse(items=items, total=total)


@router.get("/{period_id}", response_model=PeriodResponse, dependencies=[Depends(Require("performance:read"))])
async def get_period(period_id: int, db: Session = Depends(get_db)):
    """Get a single evaluation period."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    scorecard_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period.id
    ).scalar() or 0

    computed_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period.id,
        EmployeeScorecardInstance.status.in_(['computed', 'in_review', 'approved', 'finalized'])
    ).scalar() or 0

    finalized_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period.id,
        EmployeeScorecardInstance.status == 'finalized'
    ).scalar() or 0

    return PeriodResponse(
        id=period.id,
        code=period.code,
        name=period.name,
        period_type=period.period_type.value,
        status=period.status.value,
        start_date=period.start_date,
        end_date=period.end_date,
        scoring_deadline=period.scoring_deadline,
        review_deadline=period.review_deadline,
        created_at=period.created_at,
        updated_at=period.updated_at,
        scorecard_count=scorecard_count,
        computed_count=computed_count,
        finalized_count=finalized_count,
    )


@router.post("", response_model=PeriodResponse, dependencies=[Depends(Require("performance:write"))])
async def create_period(payload: PeriodCreate, db: Session = Depends(get_db)):
    """Create a new evaluation period."""
    # Check code uniqueness
    existing = db.query(EvaluationPeriod).filter(EvaluationPeriod.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Period with code '{payload.code}' already exists")

    period = EvaluationPeriod(
        code=payload.code,
        name=payload.name,
        period_type=EvaluationPeriodType(payload.period_type.value),
        status=EvaluationPeriodStatus.DRAFT,
        start_date=payload.start_date,
        end_date=payload.end_date,
        scoring_deadline=payload.scoring_deadline,
        review_deadline=payload.review_deadline,
    )
    db.add(period)
    db.commit()
    db.refresh(period)

    return PeriodResponse(
        id=period.id,
        code=period.code,
        name=period.name,
        period_type=period.period_type.value,
        status=period.status.value,
        start_date=period.start_date,
        end_date=period.end_date,
        scoring_deadline=period.scoring_deadline,
        review_deadline=period.review_deadline,
        created_at=period.created_at,
        updated_at=period.updated_at,
        scorecard_count=0,
        computed_count=0,
        finalized_count=0,
    )


@router.patch("/{period_id}", response_model=PeriodResponse, dependencies=[Depends(Require("performance:write"))])
async def update_period(period_id: int, payload: PeriodUpdate, db: Session = Depends(get_db)):
    """Update an evaluation period."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status == EvaluationPeriodStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Cannot update finalized period")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(period, key, value)

    db.commit()
    db.refresh(period)

    return await get_period(period_id, db)


@router.post("/{period_id}/activate", dependencies=[Depends(Require("performance:admin"))])
async def activate_period(period_id: int, db: Session = Depends(get_db)):
    """Activate a draft period."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status != EvaluationPeriodStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Can only activate draft periods. Current status: {period.status.value}")

    period.status = EvaluationPeriodStatus.ACTIVE
    db.commit()

    return {"success": True, "message": "Period activated", "status": "active"}


@router.post("/{period_id}/start-scoring", dependencies=[Depends(Require("performance:admin"))])
async def start_scoring(period_id: int, db: Session = Depends(get_db)):
    """Transition period to scoring phase and trigger computation."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status not in [EvaluationPeriodStatus.ACTIVE, EvaluationPeriodStatus.SCORING]:
        raise HTTPException(status_code=400, detail=f"Can only start scoring for active periods. Current status: {period.status.value}")

    period.status = EvaluationPeriodStatus.SCORING
    db.commit()

    # TODO: Queue Celery task to compute scorecards
    # from app.tasks.performance_tasks import compute_period_metrics
    # compute_period_metrics.delay(period_id)

    return {"success": True, "message": "Scoring phase started", "status": "scoring"}


@router.post("/{period_id}/start-review", dependencies=[Depends(Require("performance:admin"))])
async def start_review(period_id: int, db: Session = Depends(get_db)):
    """Transition period to review phase."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status != EvaluationPeriodStatus.SCORING:
        raise HTTPException(status_code=400, detail=f"Can only start review after scoring. Current status: {period.status.value}")

    period.status = EvaluationPeriodStatus.REVIEW
    db.commit()

    return {"success": True, "message": "Review phase started", "status": "review"}


@router.post("/{period_id}/finalize", dependencies=[Depends(Require("performance:admin"))])
async def finalize_period(period_id: int, db: Session = Depends(get_db)):
    """Finalize period and lock all scorecards."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status != EvaluationPeriodStatus.REVIEW:
        raise HTTPException(status_code=400, detail=f"Can only finalize periods in review. Current status: {period.status.value}")

    # Mark all scorecards as finalized
    db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id,
        EmployeeScorecardInstance.status.in_(['computed', 'in_review', 'approved'])
    ).update(
        {
            EmployeeScorecardInstance.status: 'finalized',
            EmployeeScorecardInstance.finalized_at: datetime.utcnow(),
        },
        synchronize_session=False
    )

    period.status = EvaluationPeriodStatus.FINALIZED
    db.commit()

    # TODO: Generate performance snapshots
    # from app.tasks.performance_tasks import generate_snapshots
    # generate_snapshots.delay(period_id)

    return {"success": True, "message": "Period finalized", "status": "finalized"}


@router.delete("/{period_id}", dependencies=[Depends(Require("performance:admin"))])
async def delete_period(period_id: int, db: Session = Depends(get_db)):
    """Delete a draft period."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status != EvaluationPeriodStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only delete draft periods")

    # Check for existing scorecards
    scorecard_count = db.query(func.count(EmployeeScorecardInstance.id)).filter(
        EmployeeScorecardInstance.evaluation_period_id == period_id
    ).scalar() or 0

    if scorecard_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete period with {scorecard_count} existing scorecards")

    db.delete(period)
    db.commit()

    return {"success": True, "message": "Period deleted"}
