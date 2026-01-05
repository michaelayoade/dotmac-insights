"""
Employee Lifecycle Management Router

Endpoints for EmployeeOnboarding, EmployeeSeparation, EmployeePromotion, EmployeeTransfer.
Uses LifecycleService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_lifecycle import BoardingStatus
from app.services.hr.lifecycle import (
    LifecycleService,
    OnboardingNotFoundError,
    SeparationNotFoundError,
    PromotionNotFoundError,
    TransferNotFoundError,
    LifecycleStatusError,
)
from app.services.hr.lifecycle_types import (
    OnboardingFilters,
    OnboardingCreateData,
    OnboardingUpdateData,
    OnboardingActivityData,
    SeparationFilters,
    SeparationCreateData,
    SeparationUpdateData,
    SeparationActivityData,
    PromotionFilters,
    PromotionCreateData,
    PromotionUpdateData,
    PromotionDetailData,
    TransferFilters,
    TransferCreateData,
    TransferUpdateData,
    TransferDetailData,
)
from app.services.hr.errors import ValidationError as HRValidationError
from app.services.base import Pagination

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _serialize_onboarding(o) -> Dict[str, Any]:
    """Serialize an onboarding for API response."""
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
        "activities": [
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
        ],
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


def _serialize_separation(s) -> Dict[str, Any]:
    """Serialize a separation for API response."""
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
        "activities": [
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
        ],
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _serialize_promotion(p) -> Dict[str, Any]:
    """Serialize a promotion for API response."""
    return {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "employee": p.employee,
        "employee_id": p.employee_id,
        "employee_name": p.employee_name,
        "promotion_date": p.promotion_date.isoformat() if p.promotion_date else None,
        "company": p.company,
        "docstatus": p.docstatus,
        "details": [
            {
                "id": d.id,
                "property": d.property,
                "current": d.current,
                "new": d.new,
                "idx": d.idx,
            }
            for d in sorted(p.details, key=lambda x: x.idx)
        ],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_transfer(t) -> Dict[str, Any]:
    """Serialize a transfer for API response."""
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
        "details": [
            {
                "id": d.id,
                "property": d.property,
                "current": d.current,
                "new": d.new,
                "idx": d.idx,
            }
            for d in sorted(t.details, key=lambda x: x.idx)
        ],
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# =============================================================================
# EMPLOYEE ONBOARDING
# =============================================================================

@router.get("/onboardings", dependencies=[Depends(Require("hr:read"))])
async def list_onboardings(
    employee_id: Optional[int] = None,
    boarding_status: Optional[str] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee onboardings with filtering."""
    service = LifecycleService(db)

    # Parse status enum
    status_enum = None
    if boarding_status:
        try:
            status_enum = BoardingStatus(boarding_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {boarding_status}")

    filters = OnboardingFilters(
        employee_id=employee_id,
        boarding_status=status_enum,
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    pagination = Pagination(offset=offset, limit=limit)

    result = service.list_onboardings(filters, pagination)

    return {
        "total": result.total,
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
            for o in result.items
        ],
    }


@router.get("/onboardings/summary", dependencies=[Depends(Require("hr:read"))])
async def onboardings_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get onboardings summary by status."""
    service = LifecycleService(db)
    metrics = service.get_metrics(company)

    return {
        "status_counts": {
            "Pending": metrics.pending_onboardings,
            "In Progress": metrics.in_progress_onboardings,
            "Completed": metrics.completed_onboardings,
        }
    }


@router.get("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:read"))])
async def get_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get onboarding detail with activities."""
    service = LifecycleService(db)

    try:
        onboarding = service.get_onboarding(onboarding_id)
    except OnboardingNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    return _serialize_onboarding(onboarding)


@router.post("/onboardings", dependencies=[Depends(Require("hr:write"))])
async def create_onboarding(
    payload: EmployeeOnboardingCreate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new onboarding with activities."""
    service = LifecycleService(db, principal)

    # Convert activities to dataclass
    activities = []
    if payload.activities:
        for idx, a in enumerate(payload.activities):
            activities.append(OnboardingActivityData(
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                required_for_employee_creation=a.required_for_employee_creation or False,
                status=a.status or "Pending",
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            ))

    try:
        data = OnboardingCreateData(
            employee_id=payload.employee_id or 0,
            employee=payload.employee,
            employee_name=payload.employee_name,
            date_of_joining=payload.date_of_joining or date.today(),
            job_applicant=payload.job_applicant,
            job_offer=payload.job_offer,
            company=payload.company,
            department=payload.department,
            designation=payload.designation,
            employee_onboarding_template=payload.employee_onboarding_template,
            activities=activities,
        )
        onboarding = service.create_onboarding(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_onboarding(onboarding)


@router.patch("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:write"))])
async def update_onboarding(
    onboarding_id: int,
    payload: EmployeeOnboardingUpdate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an onboarding and optionally replace activities."""
    service = LifecycleService(db, principal)

    # Convert activities if provided
    activities = None
    if payload.activities is not None:
        activities = []
        for idx, a in enumerate(payload.activities):
            activities.append(OnboardingActivityData(
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                required_for_employee_creation=a.required_for_employee_creation or False,
                status=a.status or "Pending",
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            ))

    try:
        data = OnboardingUpdateData(
            date_of_joining=payload.date_of_joining,
            department=payload.department,
            designation=payload.designation,
            activities=activities,
        )
        onboarding = service.update_onboarding(onboarding_id, data)
        db.commit()
    except OnboardingNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Onboarding not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_onboarding(onboarding)


@router.delete("/onboardings/{onboarding_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an onboarding."""
    service = LifecycleService(db)

    try:
        onboarding = service.get_onboarding(onboarding_id)
        db.delete(onboarding)
        db.commit()
    except OnboardingNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    return {"message": "Onboarding deleted", "id": onboarding_id}


@router.post("/onboardings/{onboarding_id}/start", dependencies=[Depends(Require("hr:write"))])
async def start_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark onboarding as in progress."""
    service = LifecycleService(db, principal)

    try:
        onboarding = service.start_onboarding(onboarding_id)
        db.commit()
    except OnboardingNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Onboarding not found")
    except LifecycleStatusError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_onboarding(onboarding)


@router.post("/onboardings/{onboarding_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark onboarding as completed."""
    service = LifecycleService(db, principal)

    try:
        onboarding = service.complete_onboarding(onboarding_id)
        db.commit()
    except OnboardingNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Onboarding not found")
    except (LifecycleStatusError, HRValidationError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_onboarding(onboarding)


# =============================================================================
# EMPLOYEE SEPARATION
# =============================================================================

@router.get("/separations", dependencies=[Depends(Require("hr:read"))])
async def list_separations(
    employee_id: Optional[int] = None,
    boarding_status: Optional[str] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee separations with filtering."""
    service = LifecycleService(db)

    # Parse status enum
    status_enum = None
    if boarding_status:
        try:
            status_enum = BoardingStatus(boarding_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {boarding_status}")

    filters = SeparationFilters(
        employee_id=employee_id,
        boarding_status=status_enum,
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    pagination = Pagination(offset=offset, limit=limit)

    result = service.list_separations(filters, pagination)

    return {
        "total": result.total,
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
            for s in result.items
        ],
    }


@router.get("/separations/summary", dependencies=[Depends(Require("hr:read"))])
async def separations_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get separations summary by status."""
    service = LifecycleService(db)
    metrics = service.get_metrics(company)

    return {
        "status_counts": {
            "Pending": metrics.pending_separations,
            "In Progress": metrics.in_progress_separations,
            "Completed": metrics.completed_separations,
        }
    }


@router.get("/separations/{separation_id}", dependencies=[Depends(Require("hr:read"))])
async def get_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get separation detail with activities."""
    service = LifecycleService(db)

    try:
        separation = service.get_separation(separation_id)
    except SeparationNotFoundError:
        raise HTTPException(status_code=404, detail="Separation not found")

    return _serialize_separation(separation)


@router.post("/separations", dependencies=[Depends(Require("hr:write"))])
async def create_separation(
    payload: EmployeeSeparationCreate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new separation with activities."""
    service = LifecycleService(db, principal)

    # Convert activities to dataclass
    activities = []
    if payload.activities:
        for idx, a in enumerate(payload.activities):
            activities.append(SeparationActivityData(
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                status=a.status or "Pending",
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            ))

    try:
        data = SeparationCreateData(
            employee_id=payload.employee_id or 0,
            employee=payload.employee,
            employee_name=payload.employee_name,
            separation_date=payload.separation_date or date.today(),
            resignation_letter_date=payload.resignation_letter_date,
            company=payload.company,
            department=payload.department,
            designation=payload.designation,
            reason_for_leaving=payload.reason_for_leaving,
            exit_interview=payload.exit_interview,
            employee_separation_template=payload.employee_separation_template,
            activities=activities,
        )
        separation = service.create_separation(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_separation(separation)


@router.patch("/separations/{separation_id}", dependencies=[Depends(Require("hr:write"))])
async def update_separation(
    separation_id: int,
    payload: EmployeeSeparationUpdate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a separation and optionally replace activities."""
    service = LifecycleService(db, principal)

    # Convert activities if provided
    activities = None
    if payload.activities is not None:
        activities = []
        for idx, a in enumerate(payload.activities):
            activities.append(SeparationActivityData(
                activity_name=a.activity_name,
                user=a.user,
                role=a.role,
                status=a.status or "Pending",
                completed_on=a.completed_on,
                idx=a.idx if a.idx is not None else idx,
            ))

    try:
        data = SeparationUpdateData(
            separation_date=payload.separation_date,
            resignation_letter_date=payload.resignation_letter_date,
            reason_for_leaving=payload.reason_for_leaving,
            exit_interview=payload.exit_interview,
            activities=activities,
        )
        separation = service.update_separation(separation_id, data)
        db.commit()
    except SeparationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Separation not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_separation(separation)


@router.delete("/separations/{separation_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_separation(
    separation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a separation."""
    service = LifecycleService(db)

    try:
        separation = service.get_separation(separation_id)
        db.delete(separation)
        db.commit()
    except SeparationNotFoundError:
        raise HTTPException(status_code=404, detail="Separation not found")

    return {"message": "Separation deleted", "id": separation_id}


@router.post("/separations/{separation_id}/start", dependencies=[Depends(Require("hr:write"))])
async def start_separation(
    separation_id: int,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark separation as in progress."""
    service = LifecycleService(db, principal)

    try:
        separation = service.start_separation(separation_id)
        db.commit()
    except SeparationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Separation not found")
    except LifecycleStatusError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_separation(separation)


@router.post("/separations/{separation_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_separation(
    separation_id: int,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark separation as completed."""
    service = LifecycleService(db, principal)

    try:
        separation = service.complete_separation(separation_id)
        db.commit()
    except SeparationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Separation not found")
    except (LifecycleStatusError, HRValidationError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_separation(separation)


# =============================================================================
# EMPLOYEE PROMOTION
# =============================================================================

@router.get("/promotions", dependencies=[Depends(Require("hr:read"))])
async def list_promotions(
    employee_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee promotions with filtering."""
    service = LifecycleService(db)

    filters = PromotionFilters(
        employee_id=employee_id,
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    pagination = Pagination(offset=offset, limit=limit)

    result = service.list_promotions(filters, pagination)

    return {
        "total": result.total,
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
            for p in result.items
        ],
    }


@router.get("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:read"))])
async def get_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get promotion detail with changes."""
    service = LifecycleService(db)

    try:
        promotion = service.get_promotion(promotion_id)
    except PromotionNotFoundError:
        raise HTTPException(status_code=404, detail="Promotion not found")

    return _serialize_promotion(promotion)


@router.post("/promotions", dependencies=[Depends(Require("hr:write"))])
async def create_promotion(
    payload: EmployeePromotionCreate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new promotion with details."""
    service = LifecycleService(db, principal)

    # Convert details to dataclass
    details = []
    if payload.details:
        for idx, d in enumerate(payload.details):
            details.append(PromotionDetailData(
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            ))

    try:
        data = PromotionCreateData(
            employee_id=payload.employee_id or 0,
            employee=payload.employee,
            employee_name=payload.employee_name,
            promotion_date=payload.promotion_date,
            company=payload.company,
            details=details,
        )
        promotion = service.create_promotion(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_promotion(promotion)


@router.patch("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:write"))])
async def update_promotion(
    promotion_id: int,
    payload: EmployeePromotionUpdate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a promotion and optionally replace details."""
    service = LifecycleService(db, principal)

    # Convert details if provided
    details = None
    if payload.details is not None:
        details = []
        for idx, d in enumerate(payload.details):
            details.append(PromotionDetailData(
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            ))

    try:
        data = PromotionUpdateData(
            promotion_date=payload.promotion_date,
            details=details,
        )
        promotion = service.update_promotion(promotion_id, data)
        db.commit()
    except PromotionNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Promotion not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_promotion(promotion)


@router.delete("/promotions/{promotion_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a promotion."""
    service = LifecycleService(db)

    try:
        promotion = service.get_promotion(promotion_id)
        db.delete(promotion)
        db.commit()
    except PromotionNotFoundError:
        raise HTTPException(status_code=404, detail="Promotion not found")

    return {"message": "Promotion deleted", "id": promotion_id}


# =============================================================================
# EMPLOYEE TRANSFER
# =============================================================================

@router.get("/transfers", dependencies=[Depends(Require("hr:read"))])
async def list_transfers(
    employee_id: Optional[int] = None,
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employee transfers with filtering."""
    service = LifecycleService(db)

    filters = TransferFilters(
        employee_id=employee_id,
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    pagination = Pagination(offset=offset, limit=limit)

    result = service.list_transfers(filters, pagination)

    return {
        "total": result.total,
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
            for t in result.items
        ],
    }


@router.get("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:read"))])
async def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get transfer detail with changes."""
    service = LifecycleService(db)

    try:
        transfer = service.get_transfer(transfer_id)
    except TransferNotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")

    return _serialize_transfer(transfer)


@router.post("/transfers", dependencies=[Depends(Require("hr:write"))])
async def create_transfer(
    payload: EmployeeTransferCreate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new transfer with details."""
    service = LifecycleService(db, principal)

    # Convert details to dataclass
    details = []
    if payload.details:
        for idx, d in enumerate(payload.details):
            details.append(TransferDetailData(
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            ))

    try:
        data = TransferCreateData(
            employee_id=payload.employee_id or 0,
            employee=payload.employee,
            employee_name=payload.employee_name,
            transfer_date=payload.transfer_date,
            company=payload.company,
            new_company=payload.new_company,
            details=details,
        )
        transfer = service.create_transfer(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_transfer(transfer)


@router.patch("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:write"))])
async def update_transfer(
    transfer_id: int,
    payload: EmployeeTransferUpdate,
    db: Session = Depends(get_db),
    principal: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a transfer and optionally replace details."""
    service = LifecycleService(db, principal)

    # Convert details if provided
    details = None
    if payload.details is not None:
        details = []
        for idx, d in enumerate(payload.details):
            details.append(TransferDetailData(
                property=d.property,
                current=d.current,
                new=d.new,
                idx=d.idx if d.idx is not None else idx,
            ))

    try:
        data = TransferUpdateData(
            transfer_date=payload.transfer_date,
            new_company=payload.new_company,
            details=details,
        )
        transfer = service.update_transfer(transfer_id, data)
        db.commit()
    except TransferNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Transfer not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return _serialize_transfer(transfer)


@router.delete("/transfers/{transfer_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a transfer."""
    service = LifecycleService(db)

    try:
        transfer = service.get_transfer(transfer_id)
        db.delete(transfer)
        db.commit()
    except TransferNotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")

    return {"message": "Transfer deleted", "id": transfer_id}
