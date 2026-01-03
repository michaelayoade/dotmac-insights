"""
Job Offers Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.services.audit_logger import AuditLogger
from app.models.hr_recruitment import JobApplicant, JobOffer, JobOfferStatus
from app.services.hr.recruitment import RecruitmentService
from app.services.hr.recruitment_types import (
    JobOfferCreateData,
    JobOfferFilters,
    JobOfferUpdateData,
    OfferTermData,
)
from app.services.hr.errors import (
    ApplicantPipelineError,
    JobOfferNotFoundError,
    OfferExpiredError,
    ValidationError,
)
from app.services.types import PaginationParams
from .helpers import decimal_or_default, status_counts

router = APIRouter()


# =============================================================================
# SCHEMAS
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


class VoidOfferPayload(BaseModel):
    reason: str


class BulkSendOffersPayload(BaseModel):
    offer_ids: List[int]


# =============================================================================
# HELPERS
# =============================================================================

def _require_offer_status(offer: JobOffer, allowed: List[JobOfferStatus]):
    if offer.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {offer.status.value if offer.status else None}",
        )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/job-offers", dependencies=[Depends(Require("hr:read"))])
async def list_job_offers(
    status: Optional[str] = None,
    job_applicant_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List job offers with filtering."""
    status_enum = None
    if status:
        try:
            status_enum = JobOfferStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = RecruitmentService(db)
    result = service.list_job_offers(
        JobOfferFilters(
            status=status_enum,
            job_applicant_id=job_applicant_id,
            company=company,
            from_date=from_date,
            to_date=to_date,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    offers = result.items
    total = result.total

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
    service = RecruitmentService(db)
    try:
        o = service.get_job_offer(offer_id)
    except JobOfferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

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
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new job offer with terms."""
    service = RecruitmentService(db, principal)
    applicant_id = payload.job_applicant_id
    if applicant_id is None and payload.job_applicant:
        applicant = db.query(JobApplicant).filter(JobApplicant.erpnext_id == payload.job_applicant).first()
        applicant_id = applicant.id if applicant else None
    if applicant_id is None:
        raise HTTPException(status_code=400, detail="job_applicant_id is required")
    job_applicant_ref = payload.job_applicant or str(applicant_id)

    terms = []
    if payload.terms:
        for idx, t in enumerate(payload.terms):
            if t.offer_term or t.value:
                terms.append(
                    OfferTermData(
                        offer_term=t.offer_term or "",
                        value=t.value or "",
                        idx=t.idx if t.idx is not None else idx,
                    )
                )
    try:
        offer = service.create_job_offer(
            JobOfferCreateData(
                job_applicant_id=applicant_id,
                job_applicant=job_applicant_ref,
                applicant_name=payload.applicant_name,
                applicant_email=payload.applicant_email,
                designation=payload.designation,
                offer_date=payload.offer_date,
                company=payload.company,
                base=decimal_or_default(payload.base),
                salary_structure=payload.salary_structure,
                terms=terms,
            )
        )
        if payload.status and payload.status != JobOfferStatus.PENDING:
            if payload.status == JobOfferStatus.AWAITING_RESPONSE:
                service.send_job_offer(offer.id)
            elif payload.status == JobOfferStatus.ACCEPTED:
                service.accept_job_offer(offer.id)
            elif payload.status == JobOfferStatus.REJECTED:
                service.reject_job_offer(offer.id)
            else:
                raise HTTPException(status_code=400, detail="Unsupported status transition on create")
        db.commit()
    except (ApplicantPipelineError, ValidationError, OfferExpiredError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_offer(offer.id, db)


@router.patch("/job-offers/{offer_id}", dependencies=[Depends(Require("hr:write"))])
async def update_job_offer(
    offer_id: int,
    payload: JobOfferUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a job offer and optionally replace terms."""
    service = RecruitmentService(db, principal)
    terms = None
    if payload.terms is not None:
        terms = []
        for idx, t in enumerate(payload.terms):
            if t.offer_term or t.value:
                terms.append(
                    OfferTermData(
                        offer_term=t.offer_term or "",
                        value=t.value or "",
                        idx=t.idx if t.idx is not None else idx,
                    )
                )

    try:
        service.update_job_offer(
            offer_id,
            JobOfferUpdateData(
                offer_date=payload.offer_date,
                designation=payload.designation,
                base=decimal_or_default(payload.base) if payload.base is not None else None,
                salary_structure=payload.salary_structure,
                terms=terms,
            ),
        )
        if payload.status:
            if payload.status == JobOfferStatus.AWAITING_RESPONSE:
                service.send_job_offer(offer_id)
            elif payload.status == JobOfferStatus.ACCEPTED:
                service.accept_job_offer(offer_id)
            elif payload.status == JobOfferStatus.REJECTED:
                service.reject_job_offer(offer_id)
            elif payload.status == JobOfferStatus.PENDING:
                pass
            else:
                raise HTTPException(status_code=400, detail="Unsupported status transition")
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (ApplicantPipelineError, ValidationError, OfferExpiredError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_offer(offer_id, db)


@router.delete("/job-offers/{offer_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a job offer and its terms."""
    service = RecruitmentService(db, principal)
    try:
        service.delete_job_offer(offer_id)
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Job offer deleted", "id": offer_id}


@router.post("/job-offers/{offer_id}/send", dependencies=[Depends(Require("hr:write"))])
async def send_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a job offer to the applicant."""
    service = RecruitmentService(db)
    try:
        offer = service.get_job_offer(offer_id)
        _require_offer_status(offer, [JobOfferStatus.PENDING])
        service.send_job_offer(offer_id)
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_job_offer(offer_id, db)


@router.post("/job-offers/{offer_id}/accept", dependencies=[Depends(Require("hr:write"))])
async def accept_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a job offer as accepted."""
    service = RecruitmentService(db)
    try:
        offer = service.get_job_offer(offer_id)
        _require_offer_status(offer, [JobOfferStatus.AWAITING_RESPONSE])
        service.accept_job_offer(offer_id)
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except OfferExpiredError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_offer(offer_id, db)


@router.post("/job-offers/{offer_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_job_offer(
    offer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a job offer as rejected."""
    service = RecruitmentService(db)
    try:
        offer = service.get_job_offer(offer_id)
        _require_offer_status(offer, [JobOfferStatus.AWAITING_RESPONSE])
        service.reject_job_offer(offer_id)
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_job_offer(offer_id, db)


@router.post("/job-offers/{offer_id}/void", dependencies=[Depends(Require("hr:write"))])
async def void_job_offer(
    offer_id: int,
    payload: VoidOfferPayload,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Void a job offer with reason."""
    service = RecruitmentService(db, principal)
    try:
        offer = service.get_job_offer(offer_id)
        _require_offer_status(offer, [JobOfferStatus.PENDING, JobOfferStatus.AWAITING_RESPONSE])
        service.void_job_offer(offer_id, payload.reason)

        audit = AuditLogger(db)
        audit.log_cancel(
            doctype="job_offer",
            document_id=offer.id,
            user_id=principal.user_id if principal else None,
            document_name=f"{offer.applicant_name}",
            remarks=f"Voided: {payload.reason}",
        )
        db.commit()
    except JobOfferNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ApplicantPipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_job_offer(offer_id, db)


@router.post("/job-offers/bulk/send", dependencies=[Depends(Require("hr:write"))])
async def bulk_send_job_offers(
    payload: BulkSendOffersPayload,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk send job offers to applicants."""
    sent = 0
    skipped = []
    service = RecruitmentService(db, principal)
    for offer_id in payload.offer_ids:
        try:
            offer = service.get_job_offer(offer_id)
            if offer.status == JobOfferStatus.PENDING:
                service.send_job_offer(offer_id)
                sent += 1
            else:
                skipped.append({
                    "id": offer_id,
                    "reason": f"Invalid status: {offer.status.value if offer.status else 'unknown'}",
                })
        except JobOfferNotFoundError:
            skipped.append({"id": offer_id, "reason": "Not found"})
    db.commit()
    return {"sent": sent, "skipped": len(skipped), "requested": len(payload.offer_ids), "skipped_details": skipped}
