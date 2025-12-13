"""
Recruitment Management Router

Endpoints for JobOpening, JobApplicant, JobOffer, Interview.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_recruitment import (
    JobOpening,
    JobOpeningStatus,
    JobApplicant,
    JobApplicantStatus,
    JobOffer,
    JobOfferStatus,
    JobOfferTerm,
    Interview,
    InterviewStatus,
    InterviewResult,
)
from .helpers import decimal_or_default, csv_response, status_counts, now

router = APIRouter()


# =============================================================================
# JOB OPENING
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


@router.get("/job-openings", dependencies=[Depends(Require("hr:read"))])
async def list_job_openings(
    status: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    publish: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List job openings with filtering."""
    query = db.query(JobOpening)

    if status:
        try:
            status_enum = JobOpeningStatus(status)
            query = query.filter(JobOpening.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if department:
        query = query.filter(JobOpening.department.ilike(f"%{department}%"))
    if designation:
        query = query.filter(JobOpening.designation.ilike(f"%{designation}%"))
    if company:
        query = query.filter(JobOpening.company.ilike(f"%{company}%"))
    if search:
        query = query.filter(JobOpening.job_title.ilike(f"%{search}%"))
    if publish is not None:
        query = query.filter(JobOpening.publish == publish)

    total = query.count()
    openings = query.order_by(JobOpening.created_at.desc()).offset(offset).limit(limit).all()

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
    j = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job opening not found")

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
) -> Dict[str, Any]:
    """Create a new job opening."""
    opening = JobOpening(
        job_title=payload.job_title,
        designation=payload.designation,
        designation_id=payload.designation_id,
        department=payload.department,
        department_id=payload.department_id,
        company=payload.company,
        status=payload.status or JobOpeningStatus.OPEN,
        publish=payload.publish or False,
        route=payload.route,
        description=payload.description,
        lower_range=decimal_or_default(payload.lower_range),
        upper_range=decimal_or_default(payload.upper_range),
        currency=payload.currency or "USD",
    )
    db.add(opening)
    db.commit()
    return await get_job_opening(opening.id, db)


@router.patch("/job-openings/{opening_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_opening(
    opening_id: int,
    payload: JobOpeningUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a job opening."""
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    decimal_fields = ["lower_range", "upper_range"]
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field in decimal_fields:
                setattr(opening, field, decimal_or_default(value))
            else:
                setattr(opening, field, value)

    db.commit()
    return await get_job_opening(opening.id, db)


@router.delete("/job-openings/{opening_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a job opening."""
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    db.delete(opening)
    db.commit()
    return {"message": "Job opening deleted", "id": opening_id}


@router.post("/job-openings/{opening_id}/close", dependencies=[Depends(Require("hr:write"))])
async def close_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Close a job opening."""
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    if opening.status != JobOpeningStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open positions can be closed")

    opening.status = JobOpeningStatus.CLOSED
    db.commit()
    return await get_job_opening(opening_id, db)


@router.post("/job-openings/{opening_id}/hold", dependencies=[Depends(Require("hr:write"))])
async def hold_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Put a job opening on hold."""
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    if opening.status != JobOpeningStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open positions can be put on hold")

    opening.status = JobOpeningStatus.ON_HOLD
    db.commit()
    return await get_job_opening(opening_id, db)


@router.post("/job-openings/{opening_id}/reopen", dependencies=[Depends(Require("hr:write"))])
async def reopen_job_opening(
    opening_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reopen a job opening."""
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    if opening.status == JobOpeningStatus.OPEN:
        raise HTTPException(status_code=400, detail="Position is already open")

    opening.status = JobOpeningStatus.OPEN
    db.commit()
    return await get_job_opening(opening_id, db)


# =============================================================================
# JOB APPLICANT
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


@router.get("/job-applicants", dependencies=[Depends(Require("hr:read"))])
async def list_job_applicants(
    status: Optional[str] = None,
    job_opening_id: Optional[int] = None,
    source: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
            a.id,
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
# JOB OFFER
# =============================================================================

class JobOfferTermPayload(BaseModel):
    offer_term: Optional[str] = None
    value: Optional[str] = None
    idx: Optional[int] = 0


class JobOfferCreate(BaseModel):
    job_applicant: str
    job_applicant_id: Optional[int] = None
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    designation: Optional[str] = None
    offer_date: date
    status: Optional[JobOfferStatus] = JobOfferStatus.PENDING
    company: Optional[str] = None
    base: Optional[Decimal] = Decimal("0")
    salary_structure: Optional[str] = None
    terms: Optional[List[JobOfferTermPayload]] = Field(default=None)


class JobOfferUpdate(BaseModel):
    job_applicant: Optional[str] = None
    job_applicant_id: Optional[int] = None
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    designation: Optional[str] = None
    offer_date: Optional[date] = None
    status: Optional[JobOfferStatus] = None
    company: Optional[str] = None
    base: Optional[Decimal] = None
    salary_structure: Optional[str] = None
    terms: Optional[List[JobOfferTermPayload]] = Field(default=None)


def _require_offer_status(offer: JobOffer, allowed: List[JobOfferStatus]):
    if offer.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {offer.status.value if offer.status else None}",
        )


def _load_offer(db: Session, offer_id: int) -> JobOffer:
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Job offer not found")
    return offer


@router.get("/job-offers", dependencies=[Depends(Require("hr:read"))])
async def list_job_offers(
    status: Optional[str] = None,
    job_applicant_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List job offers with filtering."""
    query = db.query(JobOffer)

    if status:
        try:
            status_enum = JobOfferStatus(status)
            query = query.filter(JobOffer.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if job_applicant_id:
        query = query.filter(JobOffer.job_applicant_id == job_applicant_id)
    if company:
        query = query.filter(JobOffer.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(JobOffer.offer_date >= from_date)
    if to_date:
        query = query.filter(JobOffer.offer_date <= to_date)

    total = query.count()
    offers = query.order_by(JobOffer.offer_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": o.id,
                "erpnext_id": o.erpnext_id,
                "job_applicant": o.job_applicant,
                "job_applicant_id": o.job_applicant_id,
                "applicant_name": o.applicant_name,
                "designation": o.designation,
                "offer_date": o.offer_date.isoformat() if o.offer_date else None,
                "status": o.status.value if o.status else None,
                "base": float(o.base) if o.base else 0,
                "company": o.company,
            }
            for o in offers
        ],
    }


@router.get("/job-offers/summary", dependencies=[Depends(Require("hr:read"))])
async def job_offers_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job offers summary by status."""
    query = db.query(JobOffer.status, func.count(JobOffer.id))

    if company:
        query = query.filter(JobOffer.company.ilike(f"%{company}%"))

    results = query.group_by(JobOffer.status).all()

    return {"status_counts": status_counts(results)}


@router.get("/job-offers/{offer_id}", dependencies=[Depends(Require("hr:read"))])
async def get_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job offer detail with terms."""
    o = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Job offer not found")

    terms = [
        {
            "id": t.id,
            "offer_term": t.offer_term,
            "value": t.value,
            "idx": t.idx,
        }
        for t in sorted(o.terms, key=lambda x: x.idx)
    ]

    return {
        "id": o.id,
        "erpnext_id": o.erpnext_id,
        "job_applicant": o.job_applicant,
        "job_applicant_id": o.job_applicant_id,
        "applicant_name": o.applicant_name,
        "applicant_email": o.applicant_email,
        "designation": o.designation,
        "offer_date": o.offer_date.isoformat() if o.offer_date else None,
        "status": o.status.value if o.status else None,
        "company": o.company,
        "base": float(o.base) if o.base else 0,
        "salary_structure": o.salary_structure,
        "terms": terms,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


@router.post("/job-offers", dependencies=[Depends(Require("hr:write"))])
async def create_job_offer(
    payload: JobOfferCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new job offer with terms."""
    offer = JobOffer(
        job_applicant=payload.job_applicant,
        job_applicant_id=payload.job_applicant_id,
        applicant_name=payload.applicant_name,
        applicant_email=payload.applicant_email,
        designation=payload.designation,
        offer_date=payload.offer_date,
        status=payload.status or JobOfferStatus.PENDING,
        company=payload.company,
        base=decimal_or_default(payload.base),
        salary_structure=payload.salary_structure,
    )
    db.add(offer)
    db.flush()

    if payload.terms:
        for idx, t in enumerate(payload.terms):
            term = JobOfferTerm(
                job_offer_id=offer.id,
                offer_term=t.offer_term,
                value=t.value,
                idx=t.idx if t.idx is not None else idx,
            )
            db.add(term)

    db.commit()
    return await get_job_offer(offer.id, db)


@router.patch("/job-offers/{offer_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_offer(
    offer_id: int,
    payload: JobOfferUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a job offer and optionally replace terms."""
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Job offer not found")

    update_data = payload.model_dump(exclude_unset=True)
    terms_data = update_data.pop("terms", None)

    for field, value in update_data.items():
        if value is not None:
            if field == "base":
                setattr(offer, field, decimal_or_default(value))
            else:
                setattr(offer, field, value)

    if terms_data is not None:
        db.query(JobOfferTerm).filter(JobOfferTerm.job_offer_id == offer.id).delete(synchronize_session=False)
        for idx, t in enumerate(terms_data):
            term = JobOfferTerm(
                job_offer_id=offer.id,
                offer_term=t.get("offer_term"),
                value=t.get("value"),
                idx=t.get("idx") if t.get("idx") is not None else idx,
            )
            db.add(term)

    db.commit()
    return await get_job_offer(offer.id, db)


@router.delete("/job-offers/{offer_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a job offer and its terms."""
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Job offer not found")

    db.delete(offer)
    db.commit()
    return {"message": "Job offer deleted", "id": offer_id}


@router.post("/job-offers/{offer_id}/send", dependencies=[Depends(Require("hr:write"))])
async def send_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a job offer to the applicant."""
    offer = _load_offer(db, offer_id)
    _require_offer_status(offer, [JobOfferStatus.PENDING])
    offer.status = JobOfferStatus.AWAITING_RESPONSE
    db.commit()
    return await get_job_offer(offer_id, db)


@router.post("/job-offers/{offer_id}/accept", dependencies=[Depends(Require("hr:write"))])
async def accept_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a job offer as accepted."""
    offer = _load_offer(db, offer_id)
    _require_offer_status(offer, [JobOfferStatus.AWAITING_RESPONSE])

    # Check if offer has expired
    if offer.expiry_date and offer.expiry_date < date.today():
        offer.status = JobOfferStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Offer has expired on {offer.expiry_date.isoformat()}"
        )

    offer.status = JobOfferStatus.ACCEPTED
    db.commit()
    return await get_job_offer(offer_id, db)


@router.post("/job-offers/{offer_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a job offer as rejected."""
    offer = _load_offer(db, offer_id)
    _require_offer_status(offer, [JobOfferStatus.AWAITING_RESPONSE])
    offer.status = JobOfferStatus.REJECTED
    db.commit()
    return await get_job_offer(offer_id, db)


# =============================================================================
# JOB APPLICANT STAGE TRANSITIONS
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


# =============================================================================
# JOB OFFER VOID/EXPIRY
# =============================================================================

class VoidOfferPayload(BaseModel):
    reason: str


@router.post("/job-offers/{offer_id}/void", dependencies=[Depends(Require("hr:write"))])
async def void_job_offer(
    offer_id: int,
    payload: VoidOfferPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Void a job offer with reason."""
    offer = _load_offer(db, offer_id)
    _require_offer_status(offer, [JobOfferStatus.PENDING, JobOfferStatus.AWAITING_RESPONSE])

    offer.status = JobOfferStatus.VOIDED
    offer.voided_at = now()
    offer.voided_by_id = current_user.id if current_user else None
    offer.void_reason = payload.reason
    offer.status_changed_by_id = current_user.id if current_user else None
    offer.status_changed_at = now()

    # Log audit event
    audit = AuditLogger(db)
    audit.log_cancel(
        doctype="job_offer",
        document_id=offer.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{offer.applicant_name}",
        remarks=f"Voided: {payload.reason}",
    )

    db.commit()
    return await get_job_offer(offer_id, db)


class BulkSendOffersPayload(BaseModel):
    offer_ids: List[int]


@router.post("/job-offers/bulk/send", dependencies=[Depends(Require("hr:write"))])
async def bulk_send_job_offers(
    payload: BulkSendOffersPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk send job offers to applicants."""
    sent = 0
    skipped = []
    for offer_id in payload.offer_ids:
        offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
        if offer and offer.status == JobOfferStatus.PENDING:
            offer.status = JobOfferStatus.AWAITING_RESPONSE
            offer.status_changed_by_id = current_user.id if current_user else None
            offer.status_changed_at = now()
            sent += 1
        else:
            skipped.append({
                "id": offer_id,
                "reason": "Not found" if not offer else f"Invalid status: {offer.status.value}"
            })
    db.commit()
    return {"sent": sent, "skipped": len(skipped), "requested": len(payload.offer_ids), "skipped_details": skipped}


# =============================================================================
# INTERVIEW
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


@router.get("/interviews", dependencies=[Depends(Require("hr:read"))])
async def list_interviews(
    job_applicant_id: Optional[int] = None,
    interviewer_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
