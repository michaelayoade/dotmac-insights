"""
Evaluation Periods API - Period lifecycle management

Routes are thin wrappers that delegate to EvaluationPeriodService.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict
from enum import Enum

from app.database import get_db
from app.auth import Require
from app.models.performance import EvaluationPeriodStatus
from app.services.performance import (
    EvaluationPeriodService,
    PeriodFilters,
    PeriodCreateData,
    PeriodUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError


def get_period_service(db: Session = Depends(get_db)) -> EvaluationPeriodService:
    return EvaluationPeriodService(db)


def handle_service_error(e: Exception):
    """Convert service errors to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail=str(e))

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

    model_config = ConfigDict(from_attributes=True)


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
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """List evaluation periods with filtering."""
    filters = PeriodFilters(
        status=status.value if status else None,
        period_type=period_type.value if period_type else None,
        year=year,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    try:
        result = service.list_periods(filters, pagination)
    except (ValidationError, NotFoundError) as e:
        handle_service_error(e)

    items = []
    for p in result.data:
        stats = service.get_period_stats(p.id)
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
            scorecard_count=stats.scorecard_count,
            computed_count=stats.computed_count,
            finalized_count=stats.finalized_count,
        ))

    return PeriodListResponse(items=items, total=result.total)


@router.get("/{period_id}", response_model=PeriodResponse, dependencies=[Depends(Require("performance:read"))])
async def get_period(
    period_id: int,
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Get a single evaluation period."""
    try:
        period = service.get_period(period_id)
        stats = service.get_period_stats(period_id)
    except NotFoundError as e:
        handle_service_error(e)

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
        scorecard_count=stats.scorecard_count,
        computed_count=stats.computed_count,
        finalized_count=stats.finalized_count,
    )


@router.post("", response_model=PeriodResponse, dependencies=[Depends(Require("performance:write"))])
async def create_period(
    payload: PeriodCreate,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Create a new evaluation period."""
    data = PeriodCreateData(
        code=payload.code,
        name=payload.name,
        period_type=payload.period_type.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        scoring_deadline=payload.scoring_deadline,
        review_deadline=payload.review_deadline,
    )

    try:
        period = service.create_period(data)
        db.commit()
    except (ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

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
async def update_period(
    period_id: int,
    payload: PeriodUpdate,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Update an evaluation period."""
    data = PeriodUpdateData(
        name=payload.name,
        scoring_deadline=payload.scoring_deadline,
        review_deadline=payload.review_deadline,
    )

    try:
        service.update_period(period_id, data)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return await get_period(period_id, service)


@router.post("/{period_id}/activate", dependencies=[Depends(Require("performance:admin"))])
async def activate_period(
    period_id: int,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Activate a draft period."""
    try:
        service.activate_period(period_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"success": True, "message": "Period activated", "status": "active"}


@router.post("/{period_id}/start-scoring", dependencies=[Depends(Require("performance:admin"))])
async def start_scoring(
    period_id: int,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Transition period to scoring phase and trigger computation."""
    try:
        service.start_scoring(period_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    # TODO: Queue Celery task to compute scorecards
    # from app.tasks.performance_tasks import compute_period_metrics
    # compute_period_metrics.delay(period_id)

    return {"success": True, "message": "Scoring phase started", "status": "scoring"}


@router.post("/{period_id}/start-review", dependencies=[Depends(Require("performance:admin"))])
async def start_review(
    period_id: int,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Transition period to review phase."""
    try:
        service.start_review(period_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"success": True, "message": "Review phase started", "status": "review"}


@router.post("/{period_id}/finalize", dependencies=[Depends(Require("performance:admin"))])
async def finalize_period(
    period_id: int,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Finalize period and lock all scorecards."""
    try:
        result = service.finalize_period(period_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    # TODO: Generate performance snapshots
    # from app.tasks.performance_tasks import generate_snapshots
    # generate_snapshots.delay(period_id)

    return {"success": True, "message": "Period finalized", "status": "finalized", **result}


@router.delete("/{period_id}", dependencies=[Depends(Require("performance:admin"))])
async def delete_period(
    period_id: int,
    db: Session = Depends(get_db),
    service: EvaluationPeriodService = Depends(get_period_service),
):
    """Delete a draft period."""
    try:
        service.delete_period(period_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"success": True, "message": "Period deleted"}
