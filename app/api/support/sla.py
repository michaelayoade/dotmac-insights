"""SLA policies and business calendar endpoints.

These routes are thin wrappers around SLAService.
All business logic resides in the service layer.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.support_sla import BusinessHourType, SLATargetType
from app.auth import Require, get_current_user, Principal
from app.cache import cached, CACHE_TTL
from app.services.support import SLAService
from app.services.support.types import (
    BusinessCalendarCreate,
    BusinessCalendarUpdate,
    HolidayCreate,
    SLAPolicyCreate,
    SLAPolicyUpdate,
    SLATargetCreate,
    SLATargetUpdate,
    SLABreachFilters,
)
from app.services.errors import NotFoundError, ValidationError, DuplicateError

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


class SLATargetUpdateRequest(BaseModel):
    target_type: Optional[str] = None
    priority: Optional[str] = None
    target_hours: Optional[Decimal] = None
    warning_threshold_pct: Optional[int] = None


class SLACalculateRequest(BaseModel):
    ticket_id: int


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_sla_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
) -> SLAService:
    """Provide SLAService instance for dependency injection."""
    return SLAService(db, principal)


# =============================================================================
# BUSINESS CALENDARS
# =============================================================================

@router.get("/calendars", dependencies=[Depends(Require("support:sla:read"))])
def list_calendars(
    active_only: bool = True,
    service: SLAService = Depends(get_sla_service),
) -> List[Dict[str, Any]]:
    """List all business calendars."""
    calendars = service.list_calendars(is_active=True if active_only else None)

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "calendar_type": c.calendar_type,
            "timezone": c.timezone,
            "is_default": c.is_default,
            "is_active": c.is_active,
            "holiday_count": len(c.holidays) if c.holidays else 0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calendars
    ]


@router.post("/calendars", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def create_calendar(
    payload: BusinessCalendarCreateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Create a business calendar."""
    try:
        calendar = service.create_calendar(BusinessCalendarCreate(
            name=payload.name,
            description=payload.description,
            calendar_type=payload.calendar_type,
            timezone=payload.timezone,
            schedule=payload.schedule,
            is_default=payload.is_default,
        ))
        db.commit()
        return {"id": calendar.id, "name": calendar.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:read"))])
def get_calendar(
    calendar_id: int,
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Get calendar details with holidays."""
    calendar = service.get_calendar(calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    holidays = service.list_holidays(calendar_id)

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
            for h in holidays
        ],
        "created_at": calendar.created_at.isoformat() if calendar.created_at else None,
        "updated_at": calendar.updated_at.isoformat() if calendar.updated_at else None,
    }


@router.patch("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:write"))])
def update_calendar(
    calendar_id: int,
    payload: BusinessCalendarUpdateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Update a business calendar."""
    try:
        calendar = service.update_calendar(
            calendar_id,
            BusinessCalendarUpdate(
                name=payload.name,
                description=payload.description,
                calendar_type=payload.calendar_type,
                timezone=payload.timezone,
                schedule=payload.schedule,
                is_default=payload.is_default,
                is_active=payload.is_active,
            ),
        )
        if not calendar:
            raise HTTPException(status_code=404, detail="Calendar not found")

        db.commit()
        return {"id": calendar.id, "name": calendar.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/calendars/{calendar_id}", dependencies=[Depends(Require("support:sla:write"))])
def delete_calendar(
    calendar_id: int,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Response:
    """Delete a business calendar."""
    try:
        if not service.delete_calendar(calendar_id):
            raise HTTPException(status_code=404, detail="Calendar not found")
        db.commit()
        return Response(status_code=204)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# CALENDAR HOLIDAYS
# =============================================================================

@router.post("/calendars/{calendar_id}/holidays", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def add_holiday(
    calendar_id: int,
    payload: HolidayCreateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Add a holiday to a calendar."""
    try:
        holiday = service.add_holiday(
            calendar_id,
            HolidayCreate(
                name=payload.name,
                holiday_date=datetime.combine(payload.holiday_date, datetime.min.time()),
                is_recurring=payload.is_recurring,
            ),
        )
        db.commit()
        return {"id": holiday.id, "holiday_date": holiday.holiday_date.isoformat()}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/calendars/{calendar_id}/holidays/{holiday_id}",
    dependencies=[Depends(Require("support:sla:write"))],
)
def remove_holiday(
    calendar_id: int,
    holiday_id: int,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Response:
    """Remove a holiday from a calendar."""
    if not service.remove_holiday(calendar_id, holiday_id):
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.commit()
    return Response(status_code=204)


# =============================================================================
# SLA POLICIES
# =============================================================================

@router.get("/policies", dependencies=[Depends(Require("support:sla:read"))])
def list_policies(
    active_only: bool = True,
    service: SLAService = Depends(get_sla_service),
) -> List[Dict[str, Any]]:
    """List all SLA policies."""
    policies = service.list_policies(is_active=True if active_only else None)

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
            "target_count": len(p.targets) if p.targets else 0,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]


@router.post("/policies", dependencies=[Depends(Require("support:sla:write"))], status_code=201)
def create_policy(
    payload: SLAPolicyCreateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Create an SLA policy."""
    try:
        # Convert dict conditions to list format if needed
        conditions = None
        if payload.conditions:
            conditions = [payload.conditions] if isinstance(payload.conditions, dict) else payload.conditions

        policy = service.create_policy(SLAPolicyCreate(
            name=payload.name,
            description=payload.description,
            calendar_id=payload.calendar_id,
            conditions=conditions,
            is_default=payload.is_default,
            priority=payload.priority,
        ))
        db.commit()
        return {"id": policy.id, "name": policy.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:read"))])
def get_policy(
    policy_id: int,
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Get SLA policy with targets."""
    policy = service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    targets = service.list_targets(policy_id)

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
            for t in targets
        ],
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


@router.patch("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:write"))])
def update_policy(
    policy_id: int,
    payload: SLAPolicyUpdateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Update an SLA policy."""
    try:
        # Convert dict conditions to list format if needed
        conditions = None
        if payload.conditions is not None:
            conditions = [payload.conditions] if isinstance(payload.conditions, dict) else payload.conditions

        policy = service.update_policy(
            policy_id,
            SLAPolicyUpdate(
                name=payload.name,
                description=payload.description,
                calendar_id=payload.calendar_id,
                conditions=conditions,
                is_default=payload.is_default,
                priority=payload.priority,
                is_active=payload.is_active,
            ),
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        db.commit()
        return {"id": policy.id, "name": policy.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/policies/{policy_id}", dependencies=[Depends(Require("support:sla:write"))])
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Response:
    """Delete an SLA policy."""
    if not service.delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
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
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Add or update an SLA target for a policy."""
    try:
        target = service.add_target(
            policy_id,
            SLATargetCreate(
                target_type=payload.target_type,
                priority=payload.priority,
                target_hours=float(payload.target_hours),
                warning_threshold_pct=payload.warning_threshold_pct,
            ),
        )
        db.commit()
        return {"id": target.id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/policies/{policy_id}/targets/{target_id}",
    dependencies=[Depends(Require("support:sla:write"))],
)
def update_target(
    policy_id: int,
    target_id: int,
    payload: SLATargetUpdateRequest,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Update an SLA target."""
    try:
        target = service.update_target(
            policy_id,
            target_id,
            SLATargetUpdate(
                target_type=payload.target_type,
                priority=payload.priority,
                target_hours=float(payload.target_hours) if payload.target_hours else None,
                warning_threshold_pct=payload.warning_threshold_pct,
            ),
        )
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        db.commit()
        return {"id": target.id}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/policies/{policy_id}/targets/{target_id}",
    dependencies=[Depends(Require("support:sla:write"))],
)
def remove_target(
    policy_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    service: SLAService = Depends(get_sla_service),
) -> Response:
    """Remove an SLA target."""
    if not service.remove_target(policy_id, target_id):
        raise HTTPException(status_code=404, detail="Target not found")
    db.commit()
    return Response(status_code=204)


# =============================================================================
# SLA CALCULATION
# =============================================================================

@router.post("/calculate", dependencies=[Depends(Require("support:sla:read"))])
def calculate_sla(
    payload: SLACalculateRequest,
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Calculate SLA status for a ticket.

    Returns applicable policy, targets, and current status.
    This is a preview - actual SLA assignment happens via the SLA engine service.
    """
    result = service.calculate_policy_deadlines(payload.ticket_id)

    if not result.get("policy"):
        return {
            "ticket_id": payload.ticket_id,
            "policy": None,
            "message": result.get("message", "No applicable SLA policy found"),
        }

    return {
        "ticket_id": payload.ticket_id,
        "policy": result["policy"],
        "applicable_targets": result.get("targets", []),
        "response_by": result.get("response_by"),
        "resolution_by": result.get("resolution_by"),
        "ticket_priority": result.get("ticket_priority"),
        "ticket_created_at": result.get("ticket_created_at"),
        "first_response_at": result.get("first_response_at"),
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
    offset: int = Query(default=0, ge=0),
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """List SLA breaches."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    filters = SLABreachFilters(
        policy_id=policy_id,
        target_type=target_type,
        start_date=start_dt,
    )

    breaches, total = service.list_breaches(filters=filters, skip=offset, limit=limit)

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
    service: SLAService = Depends(get_sla_service),
) -> Dict[str, Any]:
    """Get SLA breach summary statistics."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    summary = service.get_breach_summary(start_date=start_dt)

    return {
        "period_days": days,
        "total_breaches": summary.total_breaches,
        "by_target_type": [
            {"target_type": ttype, "count": count}
            for ttype, count in summary.by_target_type.items()
        ],
        "by_policy": [
            {"policy_name": name, "count": count}
            for name, count in summary.by_policy.items()
        ],
        "avg_overdue_hours": round(summary.avg_overdue_hours, 2),
    }
