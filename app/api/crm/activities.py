"""
Activities API - Calls, meetings, emails, tasks tracking
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime, date, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.crm import Activity, ActivityType, ActivityStatus

router = APIRouter(prefix="/activities", tags=["crm-activities"])


# ============= SCHEMAS =============
class ActivityBase(BaseModel):
    activity_type: str
    subject: str
    description: Optional[str] = None
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    owner_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: Optional[str] = "medium"
    reminder_at: Optional[datetime] = None
    call_direction: Optional[str] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    subject: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: Optional[str] = None
    reminder_at: Optional[datetime] = None
    call_outcome: Optional[str] = None


class ActivityResponse(BaseModel):
    id: int
    activity_type: str
    subject: str
    description: Optional[str]
    status: str
    lead_id: Optional[int]
    customer_id: Optional[int]
    opportunity_id: Optional[int]
    contact_id: Optional[int]
    scheduled_at: Optional[datetime]
    duration_minutes: Optional[int]
    completed_at: Optional[datetime]
    owner_id: Optional[int]
    assigned_to_id: Optional[int]
    priority: Optional[str]
    reminder_at: Optional[datetime]
    call_direction: Optional[str]
    call_outcome: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    items: List[ActivityResponse]
    total: int
    page: int
    page_size: int


class ActivitySummaryResponse(BaseModel):
    total_activities: int
    by_type: dict
    by_status: dict
    overdue_count: int
    today_count: int
    upcoming_week: int


# ============= ENDPOINTS =============
@router.get("", response_model=ActivityListResponse, dependencies=[Depends(Require("crm:read"))])
async def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """List activities with filtering and pagination."""
    query = db.query(Activity)

    if activity_type:
        try:
            type_enum = ActivityType(activity_type.lower())
            query = query.filter(Activity.activity_type == type_enum)
        except ValueError:
            pass

    if status:
        try:
            status_enum = ActivityStatus(status.lower())
            query = query.filter(Activity.status == status_enum)
        except ValueError:
            pass

    if lead_id:
        query = query.filter(Activity.lead_id == lead_id)

    if customer_id:
        query = query.filter(Activity.customer_id == customer_id)

    if opportunity_id:
        query = query.filter(Activity.opportunity_id == opportunity_id)

    if owner_id:
        query = query.filter(Activity.owner_id == owner_id)

    if assigned_to_id:
        query = query.filter(Activity.assigned_to_id == assigned_to_id)

    if start_date:
        query = query.filter(Activity.scheduled_at >= datetime.combine(start_date, datetime.min.time()))

    if end_date:
        query = query.filter(Activity.scheduled_at <= datetime.combine(end_date, datetime.max.time()))

    total = query.count()
    activities = query.order_by(Activity.scheduled_at.desc().nullslast(), Activity.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return ActivityListResponse(
        items=[_activity_to_response(a) for a in activities],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=ActivitySummaryResponse, dependencies=[Depends(Require("crm:read"))])
async def get_activities_summary(db: Session = Depends(get_db)):
    """Get activity summary statistics."""
    total = db.query(func.count(Activity.id)).scalar() or 0

    # By type
    type_counts = db.query(Activity.activity_type, func.count(Activity.id)).group_by(Activity.activity_type).all()
    by_type = {t.value if t else "unknown": c for t, c in type_counts}

    # By status
    status_counts = db.query(Activity.status, func.count(Activity.id)).group_by(Activity.status).all()
    by_status = {s.value if s else "unknown": c for s, c in status_counts}

    # Overdue (scheduled in past, not completed)
    now = datetime.utcnow()
    overdue = db.query(func.count(Activity.id)).filter(
        Activity.status == ActivityStatus.PLANNED,
        Activity.scheduled_at < now
    ).scalar() or 0

    # Today
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    today_count = db.query(func.count(Activity.id)).filter(
        Activity.scheduled_at >= today_start,
        Activity.scheduled_at <= today_end
    ).scalar() or 0

    # Upcoming week
    week_end = now + timedelta(days=7)
    upcoming = db.query(func.count(Activity.id)).filter(
        Activity.status == ActivityStatus.PLANNED,
        Activity.scheduled_at >= now,
        Activity.scheduled_at <= week_end
    ).scalar() or 0

    return ActivitySummaryResponse(
        total_activities=total,
        by_type=by_type,
        by_status=by_status,
        overdue_count=overdue,
        today_count=today_count,
        upcoming_week=upcoming,
    )


@router.get("/timeline", dependencies=[Depends(Require("crm:read"))])
async def get_activity_timeline(
    customer_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get activity timeline for a customer, lead, or opportunity."""
    query = db.query(Activity)

    if customer_id:
        query = query.filter(Activity.customer_id == customer_id)
    elif lead_id:
        query = query.filter(Activity.lead_id == lead_id)
    elif opportunity_id:
        query = query.filter(Activity.opportunity_id == opportunity_id)
    else:
        raise HTTPException(status_code=400, detail="Provide customer_id, lead_id, or opportunity_id")

    activities = query.order_by(Activity.created_at.desc()).limit(limit).all()

    return {
        "items": [_activity_to_response(a) for a in activities],
        "count": len(activities),
    }


@router.get("/{activity_id}", response_model=ActivityResponse, dependencies=[Depends(Require("crm:read"))])
async def get_activity(activity_id: int, db: Session = Depends(get_db)):
    """Get a single activity by ID."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    return _activity_to_response(activity)


@router.post("", response_model=ActivityResponse, dependencies=[Depends(Require("crm:write"))])
async def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    """Create a new activity."""
    try:
        activity_type = ActivityType(payload.activity_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid activity type: {payload.activity_type}")

    activity = Activity(
        activity_type=activity_type,
        subject=payload.subject,
        description=payload.description,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        contact_id=payload.contact_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        owner_id=payload.owner_id,
        assigned_to_id=payload.assigned_to_id,
        priority=payload.priority,
        reminder_at=payload.reminder_at,
        call_direction=payload.call_direction,
        status=ActivityStatus.PLANNED,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return _activity_to_response(activity)


@router.patch("/{activity_id}", response_model=ActivityResponse, dependencies=[Depends(Require("crm:write"))])
async def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_db)):
    """Update an activity."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(activity, key, value)

    db.commit()
    db.refresh(activity)

    return _activity_to_response(activity)


@router.post("/{activity_id}/complete", dependencies=[Depends(Require("crm:write"))])
async def complete_activity(
    activity_id: int,
    outcome: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Mark an activity as completed."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity.status = ActivityStatus.COMPLETED
    activity.completed_at = datetime.utcnow()

    if outcome and activity.activity_type == ActivityType.CALL:
        activity.call_outcome = outcome

    if notes:
        activity.description = f"{activity.description or ''}\n\nCompletion notes: {notes}".strip()

    db.commit()

    return {"success": True, "message": "Activity completed"}


@router.post("/{activity_id}/cancel", dependencies=[Depends(Require("crm:write"))])
async def cancel_activity(activity_id: int, db: Session = Depends(get_db)):
    """Cancel an activity."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity.status = ActivityStatus.CANCELLED
    db.commit()

    return {"success": True, "message": "Activity cancelled"}


@router.delete("/{activity_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    """Delete an activity."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    db.delete(activity)
    db.commit()

    return {"success": True, "message": "Activity deleted"}


def _activity_to_response(activity: Activity) -> ActivityResponse:
    """Convert Activity model to response."""
    return ActivityResponse(
        id=activity.id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        description=activity.description,
        status=activity.status.value,
        lead_id=activity.lead_id,
        customer_id=activity.customer_id,
        opportunity_id=activity.opportunity_id,
        contact_id=activity.contact_id,
        scheduled_at=activity.scheduled_at,
        duration_minutes=activity.duration_minutes,
        completed_at=activity.completed_at,
        owner_id=activity.owner_id,
        assigned_to_id=activity.assigned_to_id,
        priority=activity.priority,
        reminder_at=activity.reminder_at,
        call_direction=activity.call_direction,
        call_outcome=activity.call_outcome,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )
