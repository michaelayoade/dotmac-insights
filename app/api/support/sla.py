"""SLA policies and business calendar endpoints."""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.support_sla import (
    BusinessCalendar,
    BusinessCalendarHoliday,
    SLAPolicy,
    SLATarget,
    SLABreachLog,
    SLATargetType,
    BusinessHourType,
)
from app.models.ticket import Ticket
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BusinessCalendarCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    calendar_type: str = BusinessHourType.STANDARD.value
    timezone: str = "UTC"
    schedule: Optional[dict] = None
    is_default: bool = False
    is_active: bool = True


class BusinessCalendarUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    calendar_type: Optional[str] = None
    timezone: Optional[str] = None
    schedule: Optional[dict] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class HolidayCreateRequest(BaseModel):
    holiday_date: date
    name: str
    is_recurring: bool = False


class SLAPolicyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    calendar_id: Optional[int] = None
    conditions: Optional[dict] = None
    is_default: bool = False
    priority: int = 100
    is_active: bool = True


class SLAPolicyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    calendar_id: Optional[int] = None
    conditions: Optional[dict] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class SLATargetCreateRequest(BaseModel):
    target_type: str
    priority: Optional[str] = None
    target_hours: Decimal
    warning_threshold_pct: int = 80


class SLACalculateRequest(BaseModel):
    ticket_id: int


# =============================================================================
# BUSINESS CALENDARS
# =============================================================================

@router.get("/calendars", dependencies=[Depends(Require("support:sla:read"))])
def list_calendars(
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all business calendars."""
    query = db.query(BusinessCalendar)
    if active_only:
        query = query.filter(BusinessCalendar.is_active == True)
    calendars = query.order_by(BusinessCalendar.name).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "calendar_type": c.calendar_type,
            "timezone": c.timezone,
            "is_default": c.is_default,
            "is_active": c.is_active,
            "holiday_count": len(c.holidays),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calendars
    ]


@router.post("/calendars", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def create_calendar(
    payload: BusinessCalendarCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a business calendar."""
    # Validate calendar type
    try:
        BusinessHourType(payload.calendar_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid calendar_type: {payload.calendar_type}")

    # Check name uniqueness
    existing = db.query(BusinessCalendar).filter(BusinessCalendar.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Calendar with name '{payload.name}' already exists")

    # If setting as default, unset other defaults
    if payload.is_default:
        db.query(BusinessCalendar).filter(BusinessCalendar.is_default == True).update({"is_default": False})

    calendar = BusinessCalendar(
        name=payload.name,
        description=payload.description,
        calendar_type=payload.calendar_type,
        timezone=payload.timezone,
        schedule=payload.schedule,
        is_default=payload.is_default,
        is_active=payload.is_active,
    )
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return {"id": calendar.id, "name": calendar.name}


@router.get("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:read"))])
def get_calendar(
    calendar_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get calendar details with holidays."""
    calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    return {
        "id": calendar.id,
        "name": calendar.name,
        "description": calendar.description,
        "calendar_type": calendar.calendar_type,
        "timezone": calendar.timezone,
        "schedule": calendar.schedule,
        "is_default": calendar.is_default,
        "is_active": calendar.is_active,
        "holidays": [
            {
                "id": h.id,
                "holiday_date": h.holiday_date.isoformat(),
                "name": h.name,
                "is_recurring": h.is_recurring,
            }
            for h in calendar.holidays
        ],
        "created_at": calendar.created_at.isoformat() if calendar.created_at else None,
        "updated_at": calendar.updated_at.isoformat() if calendar.updated_at else None,
    }


@router.patch("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:write"))])
def update_calendar(
    calendar_id: int,
    payload: BusinessCalendarUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a business calendar."""
    calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    if payload.name is not None:
        existing = db.query(BusinessCalendar).filter(
            BusinessCalendar.name == payload.name,
            BusinessCalendar.id != calendar_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Calendar with name '{payload.name}' already exists")
        calendar.name = payload.name

    if payload.calendar_type is not None:
        try:
            BusinessHourType(payload.calendar_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid calendar_type: {payload.calendar_type}")
        calendar.calendar_type = payload.calendar_type

    if payload.description is not None:
        calendar.description = payload.description
    if payload.timezone is not None:
        calendar.timezone = payload.timezone
    if payload.schedule is not None:
        calendar.schedule = payload.schedule
    if payload.is_active is not None:
        calendar.is_active = payload.is_active
    if payload.is_default is not None:
        if payload.is_default:
            db.query(BusinessCalendar).filter(
                BusinessCalendar.is_default == True,
                BusinessCalendar.id != calendar_id
            ).update({"is_default": False})
        calendar.is_default = payload.is_default

    db.commit()
    db.refresh(calendar)
    return {"id": calendar.id, "name": calendar.name}


@router.delete("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:write"))])
def delete_calendar(
    calendar_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a business calendar."""
    calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    # Check if in use
    policy_count = db.query(SLAPolicy).filter(SLAPolicy.calendar_id == calendar_id).count()
    if policy_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete calendar: {policy_count} SLA policies reference it"
        )

    db.delete(calendar)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# CALENDAR HOLIDAYS
# =============================================================================

@router.post("/calendars/{calendar_id}/holidays", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def add_holiday(
    calendar_id: int,
    payload: HolidayCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a holiday to a calendar."""
    calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    holiday = BusinessCalendarHoliday(
        calendar_id=calendar_id,
        holiday_date=payload.holiday_date,
        name=payload.name,
        is_recurring=payload.is_recurring,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return {"id": holiday.id, "holiday_date": holiday.holiday_date.isoformat()}


@router.delete(
    "/calendars/{calendar_id}/holidays/{holiday_id}",
    dependencies=[Depends(Require("support:sla:write"))],
)
def remove_holiday(
    calendar_id: int,
    holiday_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Remove a holiday from a calendar."""
    holiday = db.query(BusinessCalendarHoliday).filter(
        BusinessCalendarHoliday.id == holiday_id,
        BusinessCalendarHoliday.calendar_id == calendar_id
    ).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# SLA POLICIES
# =============================================================================

@router.get("/policies", dependencies=[Depends(Require("support:sla:read"))])
def list_policies(
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all SLA policies."""
    query = db.query(SLAPolicy)
    if active_only:
        query = query.filter(SLAPolicy.is_active == True)
    policies = query.order_by(SLAPolicy.priority, SLAPolicy.name).all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "calendar_id": p.calendar_id,
            "calendar_name": p.calendar.name if p.calendar else None,
            "conditions": p.conditions,
            "is_default": p.is_default,
            "priority": p.priority,
            "is_active": p.is_active,
            "target_count": len(p.targets),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]


@router.post("/policies", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def create_policy(
    payload: SLAPolicyCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an SLA policy."""
    # Check name uniqueness
    existing = db.query(SLAPolicy).filter(SLAPolicy.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy with name '{payload.name}' already exists")

    # Validate calendar if provided
    if payload.calendar_id:
        calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == payload.calendar_id).first()
        if not calendar:
            raise HTTPException(status_code=400, detail="Invalid calendar_id")

    # If setting as default, unset other defaults
    if payload.is_default:
        db.query(SLAPolicy).filter(SLAPolicy.is_default == True).update({"is_default": False})

    policy = SLAPolicy(
        name=payload.name,
        description=payload.description,
        calendar_id=payload.calendar_id,
        conditions=payload.conditions,
        is_default=payload.is_default,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"id": policy.id, "name": policy.name}


@router.get("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:read"))])
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get SLA policy with targets."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "calendar_id": policy.calendar_id,
        "calendar_name": policy.calendar.name if policy.calendar else None,
        "conditions": policy.conditions,
        "is_default": policy.is_default,
        "priority": policy.priority,
        "is_active": policy.is_active,
        "targets": [
            {
                "id": t.id,
                "target_type": t.target_type,
                "priority": t.priority,
                "target_hours": float(t.target_hours),
                "warning_threshold_pct": t.warning_threshold_pct,
            }
            for t in policy.targets
        ],
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


@router.patch("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:write"))])
def update_policy(
    policy_id: int,
    payload: SLAPolicyUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an SLA policy."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if payload.name is not None:
        existing = db.query(SLAPolicy).filter(
            SLAPolicy.name == payload.name,
            SLAPolicy.id != policy_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Policy with name '{payload.name}' already exists")
        policy.name = payload.name

    if payload.description is not None:
        policy.description = payload.description
    if payload.calendar_id is not None:
        if payload.calendar_id:
            calendar = db.query(BusinessCalendar).filter(BusinessCalendar.id == payload.calendar_id).first()
            if not calendar:
                raise HTTPException(status_code=400, detail="Invalid calendar_id")
        policy.calendar_id = payload.calendar_id
    if payload.conditions is not None:
        policy.conditions = payload.conditions
    if payload.priority is not None:
        policy.priority = payload.priority
    if payload.is_active is not None:
        policy.is_active = payload.is_active
    if payload.is_default is not None:
        if payload.is_default:
            db.query(SLAPolicy).filter(
                SLAPolicy.is_default == True,
                SLAPolicy.id != policy_id
            ).update({"is_default": False})
        policy.is_default = payload.is_default

    db.commit()
    db.refresh(policy)
    return {"id": policy.id, "name": policy.name}


@router.delete("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:write"))])
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an SLA policy."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# SLA TARGETS
# =============================================================================

@router.post("/policies/{policy_id}/targets", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def add_target(
    policy_id: int,
    payload: SLATargetCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add or update an SLA target for a policy."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Validate target type
    try:
        SLATargetType(payload.target_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid target_type: {payload.target_type}")

    # Check for existing target with same type and priority
    existing = db.query(SLATarget).filter(
        SLATarget.policy_id == policy_id,
        SLATarget.target_type == payload.target_type,
        SLATarget.priority == payload.priority
    ).first()

    if existing:
        # Update existing target
        existing.target_hours = payload.target_hours
        existing.warning_threshold_pct = payload.warning_threshold_pct
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "updated": True}

    # Create new target
    target = SLATarget(
        policy_id=policy_id,
        target_type=payload.target_type,
        priority=payload.priority,
        target_hours=payload.target_hours,
        warning_threshold_pct=payload.warning_threshold_pct,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return {"id": target.id, "updated": False}


@router.delete(
    "/policies/{policy_id}/targets/{target_id}",
    dependencies=[Depends(Require("support:sla:write"))],
)
def remove_target(
    policy_id: int,
    target_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Remove an SLA target."""
    target = db.query(SLATarget).filter(
        SLATarget.id == target_id,
        SLATarget.policy_id == policy_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    db.delete(target)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# SLA CALCULATION
# =============================================================================

@router.post("/calculate", dependencies=[Depends(Require("support:sla:read"))])
def calculate_sla(
    payload: SLACalculateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate SLA status for a ticket.

    Returns applicable policy, targets, and current status.
    This is a preview - actual SLA assignment happens via the SLA engine service.
    """
    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Find applicable policy (simplified - full logic in sla_engine)
    policy = db.query(SLAPolicy).filter(
        SLAPolicy.is_active == True
    ).order_by(SLAPolicy.priority).first()

    if not policy:
        return {
            "ticket_id": ticket.id,
            "policy": None,
            "message": "No applicable SLA policy found",
        }

    targets = []
    for target in policy.targets:
        # Filter by ticket priority if target has priority specified
        if target.priority and target.priority != ticket.priority.value:
            continue
        targets.append({
            "target_type": target.target_type,
            "priority": target.priority,
            "target_hours": float(target.target_hours),
            "warning_threshold_pct": target.warning_threshold_pct,
        })

    return {
        "ticket_id": ticket.id,
        "policy": {
            "id": policy.id,
            "name": policy.name,
            "calendar_id": policy.calendar_id,
        },
        "applicable_targets": targets,
        "ticket_priority": ticket.priority.value if ticket.priority else None,
        "ticket_created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "first_response_at": ticket.first_response_at.isoformat() if ticket.first_response_at else None,
        "response_by": ticket.response_by.isoformat() if ticket.response_by else None,
        "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
    }


# =============================================================================
# SLA BREACHES
# =============================================================================

@router.get("/breaches", dependencies=[Depends(Require("support:sla:read"))])
def list_breaches(
    policy_id: Optional[int] = None,
    target_type: Optional[str] = None,
    days: int = Query(default=30, le=90),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List SLA breaches."""
    start_dt = datetime.utcnow() - __import__('datetime').timedelta(days=days)

    query = db.query(SLABreachLog).filter(SLABreachLog.breached_at >= start_dt)

    if policy_id:
        query = query.filter(SLABreachLog.policy_id == policy_id)
    if target_type:
        query = query.filter(SLABreachLog.target_type == target_type)

    total = query.count()
    breaches = query.order_by(SLABreachLog.breached_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": b.id,
                "ticket_id": b.ticket_id,
                "policy_id": b.policy_id,
                "target_type": b.target_type,
                "target_hours": float(b.target_hours),
                "actual_hours": float(b.actual_hours),
                "breached_at": b.breached_at.isoformat(),
                "was_warned": b.was_warned,
                "warned_at": b.warned_at.isoformat() if b.warned_at else None,
            }
            for b in breaches
        ],
    }


@router.get("/breaches/summary", dependencies=[Depends(Require("analytics:read"))])
@cached("sla-breaches-summary", ttl=CACHE_TTL["medium"])
async def breach_summary(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get SLA breach summary statistics."""
    start_dt = datetime.utcnow() - __import__('datetime').timedelta(days=days)

    # Total breaches
    total_breaches = db.query(func.count(SLABreachLog.id)).filter(
        SLABreachLog.breached_at >= start_dt
    ).scalar() or 0

    # Breaches by type
    by_type = db.query(
        SLABreachLog.target_type,
        func.count(SLABreachLog.id).label("count"),
        func.avg(SLABreachLog.actual_hours - SLABreachLog.target_hours).label("avg_overrun_hours"),
    ).filter(
        SLABreachLog.breached_at >= start_dt
    ).group_by(SLABreachLog.target_type).all()

    # Breaches by policy
    by_policy = db.query(
        SLABreachLog.policy_id,
        SLAPolicy.name,
        func.count(SLABreachLog.id).label("count"),
    ).join(SLAPolicy, SLABreachLog.policy_id == SLAPolicy.id, isouter=True).filter(
        SLABreachLog.breached_at >= start_dt
    ).group_by(SLABreachLog.policy_id, SLAPolicy.name).all()

    return {
        "period_days": days,
        "total_breaches": total_breaches,
        "by_target_type": [
            {
                "target_type": row.target_type,
                "count": row.count,
                "avg_overrun_hours": round(float(row.avg_overrun_hours or 0), 2),
            }
            for row in by_type
        ],
        "by_policy": [
            {
                "policy_id": row.policy_id,
                "policy_name": row.name,
                "count": row.count,
            }
            for row in by_policy
        ],
    }
