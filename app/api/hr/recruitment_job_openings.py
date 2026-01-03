"""
Job Openings Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.hr_recruitment import JobOpening, JobOpeningStatus
from app.services.hr.recruitment import RecruitmentService
from app.services.hr.recruitment_types import (
    JobOpeningCreateData,
    JobOpeningFilters,
    JobOpeningUpdateData,
)
from app.services.hr.errors import JobOpeningNotFoundError, ValidationError
from app.services.types import PaginationParams
from .helpers import decimal_or_default, status_counts

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class JobOpeningCreate(BaseModel):
    job_title: str
    designation: Optional[str] = None
    designation_id: Optional[int] = None
    department: Optional[str] = None
    department_id: Optional[int] = None
    company: Optional[str] = None
    status: Optional[JobOpeningStatus] = JobOpeningStatus.OPEN
    publish: Optional[bool] = False
    route: Optional[str] = None
    description: Optional[str] = None
    lower_range: Optional[Decimal] = Decimal("0")
    upper_range: Optional[Decimal] = Decimal("0")
    currency: Optional[str] = "USD"


class JobOpeningUpdate(BaseModel):
    job_title: Optional[str] = None
    designation: Optional[str] = None
    designation_id: Optional[int] = None
    department: Optional[str] = None
    department_id: Optional[int] = None
    company: Optional[str] = None
    status: Optional[JobOpeningStatus] = None
    publish: Optional[bool] = None
    route: Optional[str] = None
    description: Optional[str] = None
    lower_range: Optional[Decimal] = None
    upper_range: Optional[Decimal] = None
    currency: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/job-openings", dependencies=[Depends(Require("hr:read"))])
async def list_job_openings(
    status: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    publish: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List job openings with filtering."""
    status_enum = None
    if status:
        try:
            status_enum = JobOpeningStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = RecruitmentService(db)
    result = service.list_job_openings(
        JobOpeningFilters(
            status=status_enum,
            department=department,
            designation=designation,
            company=company,
            publish=publish,
            search=search,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    openings = result.items
    total = result.total

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": j.id,
                "erpnext_id": j.erpnext_id,
                "job_title": j.job_title,
                "designation": j.designation,
                "department": j.department,
                "company": j.company,
                "status": j.status.value if j.status else None,
                "publish": j.publish,
                "lower_range": float(j.lower_range) if j.lower_range else 0,
                "upper_range": float(j.upper_range) if j.upper_range else 0,
                "currency": j.currency,
            }
            for j in openings
        ],
    }


@router.get("/job-openings/summary", dependencies=[Depends(Require("hr:read"))])
async def job_openings_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job openings summary by status."""
    query = db.query(JobOpening.status, func.count(JobOpening.id))

    if company:
        query = query.filter(JobOpening.company.ilike(f"%{company}%"))

    results = query.group_by(JobOpening.status).all()

    return {"status_counts": status_counts(results)}


@router.get("/job-openings/{opening_id}", dependencies=[Depends(Require("hr:read"))])
async def get_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job opening detail."""
    service = RecruitmentService(db)
    try:
        j = service.get_job_opening(opening_id)
    except JobOpeningNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "id": j.id,
        "erpnext_id": j.erpnext_id,
        "job_title": j.job_title,
        "designation": j.designation,
        "designation_id": j.designation_id,
        "department": j.department,
        "department_id": j.department_id,
        "company": j.company,
        "status": j.status.value if j.status else None,
        "publish": j.publish,
        "route": j.route,
        "description": j.description,
        "lower_range": float(j.lower_range) if j.lower_range else 0,
        "upper_range": float(j.upper_range) if j.upper_range else 0,
        "currency": j.currency,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


@router.post("/job-openings", dependencies=[Depends(Require("hr:write"))])
async def create_job_opening(
    payload: JobOpeningCreate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new job opening."""
    service = RecruitmentService(db, principal)
    try:
        opening = service.create_job_opening(
            JobOpeningCreateData(
                job_title=payload.job_title,
                designation=payload.designation,
                designation_id=payload.designation_id,
                department=payload.department,
                department_id=payload.department_id,
                company=payload.company,
                description=payload.description,
                lower_range=decimal_or_default(payload.lower_range),
                upper_range=decimal_or_default(payload.upper_range),
                currency=payload.currency or "USD",
                publish=payload.publish or False,
            )
        )
        if payload.status and payload.status != JobOpeningStatus.OPEN:
            service.update_job_opening(
                opening.id,
                JobOpeningUpdateData(status=payload.status),
            )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_opening(opening.id, db)


@router.patch("/job-openings/{opening_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_opening(
    opening_id: int,
    payload: JobOpeningUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a job opening."""
    service = RecruitmentService(db, principal)
    try:
        service.update_job_opening(
            opening_id,
            JobOpeningUpdateData(
                job_title=payload.job_title,
                designation=payload.designation,
                designation_id=payload.designation_id,
                department=payload.department,
                department_id=payload.department_id,
                description=payload.description,
                lower_range=decimal_or_default(payload.lower_range) if payload.lower_range is not None else None,
                upper_range=decimal_or_default(payload.upper_range) if payload.upper_range is not None else None,
                currency=payload.currency,
                publish=payload.publish,
                status=payload.status,
            ),
        )
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_opening(opening_id, db)


@router.delete("/job-openings/{opening_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a job opening."""
    service = RecruitmentService(db, principal)
    try:
        service.delete_job_opening(opening_id)
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Job opening deleted", "id": opening_id}


@router.post("/job-openings/{opening_id}/close", dependencies=[Depends(Require("hr:write"))])
async def close_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Close a job opening."""
    service = RecruitmentService(db, principal)
    try:
        opening = service.get_job_opening(opening_id)
        if opening.status != JobOpeningStatus.OPEN:
            raise HTTPException(status_code=400, detail="Only open positions can be closed")
        service.close_job_opening(opening_id)
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_job_opening(opening_id, db)


@router.post("/job-openings/{opening_id}/hold", dependencies=[Depends(Require("hr:write"))])
async def hold_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Put a job opening on hold."""
    service = RecruitmentService(db, principal)
    try:
        opening = service.get_job_opening(opening_id)
        if opening.status != JobOpeningStatus.OPEN:
            raise HTTPException(status_code=400, detail="Only open positions can be put on hold")
        service.update_job_opening(
            opening_id,
            JobOpeningUpdateData(status=JobOpeningStatus.ON_HOLD),
        )
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_opening(opening_id, db)


@router.post("/job-openings/{opening_id}/reopen", dependencies=[Depends(Require("hr:write"))])
async def reopen_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reopen a job opening."""
    service = RecruitmentService(db, principal)
    try:
        opening = service.get_job_opening(opening_id)
        if opening.status == JobOpeningStatus.OPEN:
            raise HTTPException(status_code=400, detail="Position is already open")
        service.update_job_opening(
            opening_id,
            JobOpeningUpdateData(status=JobOpeningStatus.OPEN),
        )
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_opening(opening_id, db)
