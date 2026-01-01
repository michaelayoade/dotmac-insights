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
from app.models.auth import User
from app.services.audit_logger import AuditLogger
from app.models.hr_recruitment import JobOffer, JobOfferStatus, JobOfferTerm
from .helpers import decimal_or_default, status_counts, now

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


def _load_offer(db: Session, offer_id: int) -> JobOffer:
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Job offer not found")
    return offer


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
