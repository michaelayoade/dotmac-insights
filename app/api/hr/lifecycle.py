"""
Employee Lifecycle Management Router

Endpoints for EmployeeOnboarding, EmployeeSeparation, EmployeePromotion, EmployeeTransfer.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_lifecycle import (
    EmployeeOnboarding,
    EmployeeOnboardingActivity,
    EmployeeSeparation,
    EmployeeSeparationActivity,
    EmployeePromotion,
    EmployeePromotionDetail,
    EmployeeTransfer,
    EmployeeTransferDetail,
    BoardingStatus,
)
from .helpers import csv_response, status_counts

router = APIRouter()


# =============================================================================
# EMPLOYEE ONBOARDING
# =============================================================================

class OnboardingActivityPayload(BaseModel):
    activity_name: str
    user: Optional[str] = None
    role: Optional[str] = None
    required_for_employee_creation: Optional[bool] = False
    status: Optional[str] = None
    completed_on: Optional[date] = None
    idx: Optional[int] = 0


class EmployeeOnboardingCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    job_applicant: Optional[str] = None
    job_offer: Optional[str] = None
    date_of_joining: Optional[date] = None
    boarding_status: Optional[BoardingStatus] = BoardingStatus.PENDING
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_onboarding_template: Optional[str] = None
    activities: Optional[List[OnboardingActivityPayload]] = Field(default=None)


class EmployeeOnboardingUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    job_applicant: Optional[str] = None
    job_offer: Optional[str] = None
    date_of_joining: Optional[date] = None
    boarding_status: Optional[BoardingStatus] = None
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_onboarding_template: Optional[str] = None
    activities: Optional[List[OnboardingActivityPayload]] = Field(default=None)


def _require_boarding_status(obj, allowed: List[BoardingStatus]):
    if obj.boarding_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {obj.boarding_status.value if obj.boarding_status else None}",
        )


@router.get("/onboardings", dependencies=[Depends(Require("hr:read"))])
async def list_onboardings(
    employee_id: Optional[int] = None,
    boarding_status: Optional[str] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee onboardings with filtering."""
    query = db.query(EmployeeOnboarding)

    if employee_id:
        query = query.filter(EmployeeOnboarding.employee_id == employee_id)
    if boarding_status:
        try:
            status_enum = BoardingStatus(boarding_status)
            query = query.filter(EmployeeOnboarding.boarding_status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {boarding_status}")
    if company:
        query = query.filter(EmployeeOnboarding.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(EmployeeOnboarding.date_of_joining >= from_date)
    if to_date:
        query = query.filter(EmployeeOnboarding.date_of_joining <= to_date)

    total = query.count()
    onboardings = query.order_by(EmployeeOnboarding.date_of_joining.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": o.id,
                "erpnext_id": o.erpnext_id,
                "employee": o.employee,
                "employee_id": o.employee_id,
                "employee_name": o.employee_name,
                "date_of_joining": o.date_of_joining.isoformat() if o.date_of_joining else None,
                "boarding_status": o.boarding_status.value if o.boarding_status else None,
                "company": o.company,
                "department": o.department,
                "activity_count": len(o.activities),
            }
            for o in onboardings
        ],
    }


@router.get("/onboardings/summary", dependencies=[Depends(Require("hr:read"))])
async def onboardings_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get onboardings summary by status."""
    query = db.query(EmployeeOnboarding.boarding_status, func.count(EmployeeOnboarding.id))

    if company:
        query = query.filter(EmployeeOnboarding.company.ilike(f"%{company}%"))

    results = query.group_by(EmployeeOnboarding.boarding_status).all()

    return {"status_counts": status_counts(results)}


@router.get("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:read"))])
async def get_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get onboarding detail with activities."""
    o = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    activities = [
        {
            "id": a.id,
            "activity_name": a.activity_name,
            "user": a.user,
            "role": a.role,
            "required_for_employee_creation": a.required_for_employee_creation,
            "status": a.status,
            "completed_on": a.completed_on.isoformat() if a.completed_on else None,
            "idx": a.idx,
        }
        for a in sorted(o.activities, key=lambda x: x.idx)
    ]

    return {
        "id": o.id,
        "erpnext_id": o.erpnext_id,
        "employee": o.employee,
        "employee_id": o.employee_id,
        "employee_name": o.employee_name,
        "job_applicant": o.job_applicant,
        "job_offer": o.job_offer,
        "date_of_joining": o.date_of_joining.isoformat() if o.date_of_joining else None,
        "boarding_status": o.boarding_status.value if o.boarding_status else None,
        "company": o.company,
        "department": o.department,
        "designation": o.designation,
        "employee_onboarding_template": o.employee_onboarding_template,
        "activities": activities,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


@router.post("/onboardings", dependencies=[Depends(Require("hr:write"))])
async def create_onboarding(
    payload: EmployeeOnboardingCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new onboarding with activities."""
    onboarding = EmployeeOnboarding(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        job_applicant=payload.job_applicant,
        job_offer=payload.job_offer,
        date_of_joining=payload.date_of_joining,
        boarding_status=payload.boarding_status or BoardingStatus.PENDING,
        company=payload.company,
        department=payload.department,
        designation=payload.designation,
        employee_onboarding_template=payload.employee_onboarding_template,
    )
    db.add(onboarding)
    db.flush()

    if payload.activities:
        for idx, a in enumerate(payload.activities):
            activity = EmployeeOnboardingActivity(
                employee_onboarding_id=onboarding.id,
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                required_for_employee_creation=a.required_for_employee_creation or False,
                status=a.status,
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            )
            db.add(activity)

    db.commit()
    return await get_onboarding(onboarding.id, db)


@router.patch("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:write"))])
async def update_onboarding(
    onboarding_id: int,
    payload: EmployeeOnboardingUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an onboarding and optionally replace activities."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    update_data = payload.model_dump(exclude_unset=True)
    activities_data = update_data.pop("activities", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(onboarding, field, value)

    if activities_data is not None:
        db.query(EmployeeOnboardingActivity).filter(
            EmployeeOnboardingActivity.employee_onboarding_id == onboarding.id
        ).delete(synchronize_session=False)
        for idx, a in enumerate(activities_data):
            activity = EmployeeOnboardingActivity(
                employee_onboarding_id=onboarding.id,
                activity_name=a.get("activity_name"),
                user=a.get("user"),
                role=a.get("role"),
                required_for_employee_creation=a.get("required_for_employee_creation", False),
                status=a.get("status"),
                completed_on=a.get("completed_on"),
                idx=a.get("idx") if a.get("idx") is not None else idx,
            )
            db.add(activity)

    db.commit()
    return await get_onboarding(onboarding.id, db)


@router.delete("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an onboarding."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    db.delete(onboarding)
    db.commit()
    return {"message": "Onboarding deleted", "id": onboarding_id}


@router.post("/onboardings/{onboarding_id}/start", dependencies=[Depends(Require("hr:write"))])
async def start_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark onboarding as in progress."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")
    _require_boarding_status(onboarding, [BoardingStatus.PENDING])
    onboarding.boarding_status = BoardingStatus.IN_PROGRESS
    db.commit()
    return await get_onboarding(onboarding_id, db)


@router.post("/onboardings/{onboarding_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark onboarding as completed."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")
    _require_boarding_status(onboarding, [BoardingStatus.IN_PROGRESS])
    onboarding.boarding_status = BoardingStatus.COMPLETED
    db.commit()
    return await get_onboarding(onboarding_id, db)


# =============================================================================
# EMPLOYEE SEPARATION
# =============================================================================

class SeparationActivityPayload(BaseModel):
    activity_name: str
    user: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    completed_on: Optional[date] = None
    idx: Optional[int] = 0


class EmployeeSeparationCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    resignation_letter_date: Optional[date] = None
    separation_date: Optional[date] = None
    boarding_status: Optional[BoardingStatus] = BoardingStatus.PENDING
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    reason_for_leaving: Optional[str] = None
    exit_interview: Optional[str] = None
    employee_separation_template: Optional[str] = None
    activities: Optional[List[SeparationActivityPayload]] = Field(default=None)


class EmployeeSeparationUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    resignation_letter_date: Optional[date] = None
    separation_date: Optional[date] = None
    boarding_status: Optional[BoardingStatus] = None
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    reason_for_leaving: Optional[str] = None
    exit_interview: Optional[str] = None
    employee_separation_template: Optional[str] = None
    activities: Optional[List[SeparationActivityPayload]] = Field(default=None)


@router.get("/separations", dependencies=[Depends(Require("hr:read"))])
async def list_separations(
    employee_id: Optional[int] = None,
    boarding_status: Optional[str] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee separations with filtering."""
    query = db.query(EmployeeSeparation)

    if employee_id:
        query = query.filter(EmployeeSeparation.employee_id == employee_id)
    if boarding_status:
        try:
            status_enum = BoardingStatus(boarding_status)
            query = query.filter(EmployeeSeparation.boarding_status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {boarding_status}")
    if company:
        query = query.filter(EmployeeSeparation.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(EmployeeSeparation.separation_date >= from_date)
    if to_date:
        query = query.filter(EmployeeSeparation.separation_date <= to_date)

    total = query.count()
    separations = query.order_by(EmployeeSeparation.separation_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "employee": s.employee,
                "employee_id": s.employee_id,
                "employee_name": s.employee_name,
                "separation_date": s.separation_date.isoformat() if s.separation_date else None,
                "boarding_status": s.boarding_status.value if s.boarding_status else None,
                "company": s.company,
                "activity_count": len(s.activities),
            }
            for s in separations
        ],
    }


@router.get("/separations/summary", dependencies=[Depends(Require("hr:read"))])
async def separations_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get separations summary by status."""
    query = db.query(EmployeeSeparation.boarding_status, func.count(EmployeeSeparation.id))

    if company:
        query = query.filter(EmployeeSeparation.company.ilike(f"%{company}%"))

    results = query.group_by(EmployeeSeparation.boarding_status).all()

    return {"status_counts": status_counts(results)}


@router.get("/separations/{separation_id}", dependencies=[Depends(Require("hr:read"))])
async def get_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get separation detail with activities."""
    s = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Separation not found")

    activities = [
        {
            "id": a.id,
            "activity_name": a.activity_name,
            "user": a.user,
            "role": a.role,
            "status": a.status,
            "completed_on": a.completed_on.isoformat() if a.completed_on else None,
            "idx": a.idx,
        }
        for a in sorted(s.activities, key=lambda x: x.idx)
    ]

    return {
        "id": s.id,
        "erpnext_id": s.erpnext_id,
        "employee": s.employee,
        "employee_id": s.employee_id,
        "employee_name": s.employee_name,
        "resignation_letter_date": s.resignation_letter_date.isoformat() if s.resignation_letter_date else None,
        "separation_date": s.separation_date.isoformat() if s.separation_date else None,
        "boarding_status": s.boarding_status.value if s.boarding_status else None,
        "company": s.company,
        "department": s.department,
        "designation": s.designation,
        "reason_for_leaving": s.reason_for_leaving,
        "exit_interview": s.exit_interview,
        "employee_separation_template": s.employee_separation_template,
        "activities": activities,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post("/separations", dependencies=[Depends(Require("hr:write"))])
async def create_separation(
    payload: EmployeeSeparationCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new separation with activities."""
    separation = EmployeeSeparation(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        resignation_letter_date=payload.resignation_letter_date,
        separation_date=payload.separation_date,
        boarding_status=payload.boarding_status or BoardingStatus.PENDING,
        company=payload.company,
        department=payload.department,
        designation=payload.designation,
        reason_for_leaving=payload.reason_for_leaving,
        exit_interview=payload.exit_interview,
        employee_separation_template=payload.employee_separation_template,
    )
    db.add(separation)
    db.flush()

    if payload.activities:
        for idx, a in enumerate(payload.activities):
            activity = EmployeeSeparationActivity(
                employee_separation_id=separation.id,
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                status=a.status,
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            )
            db.add(activity)

    db.commit()
    return await get_separation(separation.id, db)


@router.patch("/separations/{separation_id}", dependencies=[Depends(Require("hr:write"))])
async def update_separation(
    separation_id: int,
    payload: EmployeeSeparationUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a separation and optionally replace activities."""
    separation = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()
    if not separation:
        raise HTTPException(status_code=404, detail="Separation not found")

    update_data = payload.model_dump(exclude_unset=True)
    activities_data = update_data.pop("activities", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(separation, field, value)

    if activities_data is not None:
        db.query(EmployeeSeparationActivity).filter(
            EmployeeSeparationActivity.employee_separation_id == separation.id
        ).delete(synchronize_session=False)
        for idx, a in enumerate(activities_data):
            activity = EmployeeSeparationActivity(
                employee_separation_id=separation.id,
                activity_name=a.get("activity_name"),
                user=a.get("user"),
                role=a.get("role"),
                status=a.get("status"),
                completed_on=a.get("completed_on"),
                idx=a.get("idx") if a.get("idx") is not None else idx,
            )
            db.add(activity)

    db.commit()
    return await get_separation(separation.id, db)


@router.delete("/separations/{separation_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a separation."""
    separation = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()
    if not separation:
        raise HTTPException(status_code=404, detail="Separation not found")

    db.delete(separation)
    db.commit()
    return {"message": "Separation deleted", "id": separation_id}


@router.post("/separations/{separation_id}/start", dependencies=[Depends(Require("hr:write"))])
async def start_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark separation as in progress."""
    separation = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()
    if not separation:
        raise HTTPException(status_code=404, detail="Separation not found")
    _require_boarding_status(separation, [BoardingStatus.PENDING])
    separation.boarding_status = BoardingStatus.IN_PROGRESS
    db.commit()
    return await get_separation(separation_id, db)


@router.post("/separations/{separation_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark separation as completed."""
    separation = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()
    if not separation:
        raise HTTPException(status_code=404, detail="Separation not found")
    _require_boarding_status(separation, [BoardingStatus.IN_PROGRESS])
    separation.boarding_status = BoardingStatus.COMPLETED
    db.commit()
    return await get_separation(separation_id, db)


# =============================================================================
# EMPLOYEE PROMOTION
# =============================================================================

class PromotionDetailPayload(BaseModel):
    property: str
    current: Optional[str] = None
    new: Optional[str] = None
    idx: Optional[int] = 0


class EmployeePromotionCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    promotion_date: date
    company: Optional[str] = None
    docstatus: Optional[int] = 0
    details: Optional[List[PromotionDetailPayload]] = Field(default=None)


class EmployeePromotionUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    promotion_date: Optional[date] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None
    details: Optional[List[PromotionDetailPayload]] = Field(default=None)


@router.get("/promotions", dependencies=[Depends(Require("hr:read"))])
async def list_promotions(
    employee_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee promotions with filtering."""
    query = db.query(EmployeePromotion)

    if employee_id:
        query = query.filter(EmployeePromotion.employee_id == employee_id)
    if company:
        query = query.filter(EmployeePromotion.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(EmployeePromotion.promotion_date >= from_date)
    if to_date:
        query = query.filter(EmployeePromotion.promotion_date <= to_date)

    total = query.count()
    promotions = query.order_by(EmployeePromotion.promotion_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "employee": p.employee,
                "employee_id": p.employee_id,
                "employee_name": p.employee_name,
                "promotion_date": p.promotion_date.isoformat() if p.promotion_date else None,
                "company": p.company,
                "detail_count": len(p.details),
            }
            for p in promotions
        ],
    }


@router.get("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:read"))])
async def get_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get promotion detail with changes."""
    p = db.query(EmployeePromotion).filter(EmployeePromotion.id == promotion_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Promotion not found")

    details = [
        {
            "id": d.id,
            "property": d.property,
            "current": d.current,
            "new": d.new,
            "idx": d.idx,
        }
        for d in sorted(p.details, key=lambda x: x.idx)
    ]

    return {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "employee": p.employee,
        "employee_id": p.employee_id,
        "employee_name": p.employee_name,
        "promotion_date": p.promotion_date.isoformat() if p.promotion_date else None,
        "company": p.company,
        "docstatus": p.docstatus,
        "details": details,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/promotions", dependencies=[Depends(Require("hr:write"))])
async def create_promotion(
    payload: EmployeePromotionCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new promotion with details."""
    promotion = EmployeePromotion(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        promotion_date=payload.promotion_date,
        company=payload.company,
        docstatus=payload.docstatus or 0,
    )
    db.add(promotion)
    db.flush()

    if payload.details:
        for idx, d in enumerate(payload.details):
            detail = EmployeePromotionDetail(
                employee_promotion_id=promotion.id,
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_promotion(promotion.id, db)


@router.patch("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:write"))])
async def update_promotion(
    promotion_id: int,
    payload: EmployeePromotionUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a promotion and optionally replace details."""
    promotion = db.query(EmployeePromotion).filter(EmployeePromotion.id == promotion_id).first()
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    update_data = payload.model_dump(exclude_unset=True)
    details_data = update_data.pop("details", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(promotion, field, value)

    if details_data is not None:
        db.query(EmployeePromotionDetail).filter(
            EmployeePromotionDetail.employee_promotion_id == promotion.id
        ).delete(synchronize_session=False)
        for idx, d in enumerate(details_data):
            detail = EmployeePromotionDetail(
                employee_promotion_id=promotion.id,
                property=d.get("property"),
                current=d.get("current"),
                new=d.get("new"),
                idx=d.get("idx") if d.get("idx") is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_promotion(promotion.id, db)


@router.delete("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a promotion."""
    promotion = db.query(EmployeePromotion).filter(EmployeePromotion.id == promotion_id).first()
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    db.delete(promotion)
    db.commit()
    return {"message": "Promotion deleted", "id": promotion_id}


# =============================================================================
# EMPLOYEE TRANSFER
# =============================================================================

class TransferDetailPayload(BaseModel):
    property: str
    current: Optional[str] = None
    new: Optional[str] = None
    idx: Optional[int] = 0


class EmployeeTransferCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    transfer_date: date
    company: Optional[str] = None
    new_company: Optional[str] = None
    docstatus: Optional[int] = 0
    details: Optional[List[TransferDetailPayload]] = Field(default=None)


class EmployeeTransferUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    transfer_date: Optional[date] = None
    company: Optional[str] = None
    new_company: Optional[str] = None
    docstatus: Optional[int] = None
    details: Optional[List[TransferDetailPayload]] = Field(default=None)


@router.get("/transfers", dependencies=[Depends(Require("hr:read"))])
async def list_transfers(
    employee_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee transfers with filtering."""
    query = db.query(EmployeeTransfer)

    if employee_id:
        query = query.filter(EmployeeTransfer.employee_id == employee_id)
    if company:
        query = query.filter(EmployeeTransfer.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(EmployeeTransfer.transfer_date >= from_date)
    if to_date:
        query = query.filter(EmployeeTransfer.transfer_date <= to_date)

    total = query.count()
    transfers = query.order_by(EmployeeTransfer.transfer_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "employee": t.employee,
                "employee_id": t.employee_id,
                "employee_name": t.employee_name,
                "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
                "company": t.company,
                "new_company": t.new_company,
                "detail_count": len(t.details),
            }
            for t in transfers
        ],
    }


@router.get("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:read"))])
async def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get transfer detail with changes."""
    t = db.query(EmployeeTransfer).filter(EmployeeTransfer.id == transfer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transfer not found")

    details = [
        {
            "id": d.id,
            "property": d.property,
            "current": d.current,
            "new": d.new,
            "idx": d.idx,
        }
        for d in sorted(t.details, key=lambda x: x.idx)
    ]

    return {
        "id": t.id,
        "erpnext_id": t.erpnext_id,
        "employee": t.employee,
        "employee_id": t.employee_id,
        "employee_name": t.employee_name,
        "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
        "company": t.company,
        "new_company": t.new_company,
        "docstatus": t.docstatus,
        "details": details,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.post("/transfers", dependencies=[Depends(Require("hr:write"))])
async def create_transfer(
    payload: EmployeeTransferCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new transfer with details."""
    transfer = EmployeeTransfer(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        transfer_date=payload.transfer_date,
        company=payload.company,
        new_company=payload.new_company,
        docstatus=payload.docstatus or 0,
    )
    db.add(transfer)
    db.flush()

    if payload.details:
        for idx, d in enumerate(payload.details):
            detail = EmployeeTransferDetail(
                employee_transfer_id=transfer.id,
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_transfer(transfer.id, db)


@router.patch("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:write"))])
async def update_transfer(
    transfer_id: int,
    payload: EmployeeTransferUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a transfer and optionally replace details."""
    transfer = db.query(EmployeeTransfer).filter(EmployeeTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    update_data = payload.model_dump(exclude_unset=True)
    details_data = update_data.pop("details", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(transfer, field, value)

    if details_data is not None:
        db.query(EmployeeTransferDetail).filter(
            EmployeeTransferDetail.employee_transfer_id == transfer.id
        ).delete(synchronize_session=False)
        for idx, d in enumerate(details_data):
            detail = EmployeeTransferDetail(
                employee_transfer_id=transfer.id,
                property=d.get("property"),
                current=d.get("current"),
                new=d.get("new"),
                idx=d.get("idx") if d.get("idx") is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_transfer(transfer.id, db)


@router.delete("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a transfer."""
    transfer = db.query(EmployeeTransfer).filter(EmployeeTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    db.delete(transfer)
    db.commit()
    return {"message": "Transfer deleted", "id": transfer_id}
