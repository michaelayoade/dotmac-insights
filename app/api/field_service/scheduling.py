"""
Scheduling and Dispatch API

Calendar views, availability checking, and bulk operations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, time
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.services.field_service import (
    ScheduleService,
    DispatchService,
    CalendarFilters,
    BulkAssignData,
)
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class BulkAssignRequest(BaseModel):
    """Schema for bulk assigning orders."""
    order_ids: List[int]
    technician_id: int
    team_id: Optional[int] = None
    notify_customers: bool = True


class AvailabilityCheckRequest(BaseModel):
    """Schema for checking availability."""
    technician_id: int
    date: date
    start_time: Optional[time] = None
    duration_hours: float = 1.0


# =============================================================================
# CALENDAR VIEWS
# =============================================================================

@router.get("/schedule/calendar", dependencies=[Depends(Require("explorer:read"))])
async def get_calendar(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    technician_id: Optional[int] = None,
    team_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get calendar view of scheduled orders."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    service = ScheduleService(db, principal)
    filters = CalendarFilters(
        start_date=start,
        end_date=end,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
    )

    try:
        view = service.get_calendar(filters)
    except ValidationError as e:
        raise HTTPException(400, str(e))

    return {
        "start_date": view.start_date,
        "end_date": view.end_date,
        "calendar": view.calendar,
        "daily_summary": {
            k: {
                "total": v.total,
                "completed": v.completed,
                "in_progress": v.in_progress,
                "scheduled": v.scheduled,
                "urgent": v.urgent,
            }
            for k, v in view.daily_summary.items()
        },
    }


@router.get("/schedule/technician/{technician_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_technician_schedule(
    technician_id: int,
    date_param: Optional[str] = Query(None, alias="date", description="Date (YYYY-MM-DD)"),
    days: int = Query(default=7, le=30),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get a technician's schedule."""
    start = date.fromisoformat(date_param) if date_param else date.today()

    service = ScheduleService(db, principal)
    try:
        schedule = service.get_technician_schedule(
            technician_id=technician_id,
            start_date=start,
            days=days,
        )
    except NotFoundError:
        raise HTTPException(404, "Technician not found")

    return {
        "technician": {
            "id": schedule.technician_id,
            "name": schedule.technician_name,
            "email": schedule.technician_email,
        },
        "start_date": schedule.start_date,
        "end_date": schedule.end_date,
        "schedule": schedule.schedule,
        "summary": {
            "total_orders": schedule.total_orders,
            "total_hours_scheduled": schedule.total_hours_scheduled,
            "completed": schedule.completed,
        },
    }


# =============================================================================
# AVAILABILITY
# =============================================================================

@router.get("/schedule/availability", dependencies=[Depends(Require("explorer:read"))])
async def check_availability(
    date_param: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    technician_id: Optional[int] = None,
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Check technician availability for a given date."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    service = ScheduleService(db, principal)
    availability_list = service.check_availability(
        check_date=check_date,
        technician_id=technician_id,
        team_id=team_id,
    )

    return {
        "date": date_param,
        "availability": [
            {
                "technician_id": a.technician_id,
                "technician_name": a.technician_name,
                "date": a.date,
                "scheduled_orders": a.scheduled_orders,
                "scheduled_hours": a.scheduled_hours,
                "available_hours": a.available_hours,
                "available_slots": a.available_slots,
                "is_available": a.is_available,
                "scheduled_slots": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "order_id": s.order_id,
                        "title": s.title,
                    }
                    for s in a.scheduled_slots
                ],
            }
            for a in availability_list
        ],
    }


@router.get("/schedule/available-technicians", dependencies=[Depends(Require("explorer:read"))])
async def get_available_technicians(
    date_param: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    start_time: Optional[str] = None,
    duration_hours: float = 1.0,
    zone_id: Optional[int] = None,
    skill_type: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get list of available technicians for a given date/time."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    service = ScheduleService(db, principal)
    available_list = service.get_available_technicians(
        check_date=check_date,
        duration_hours=duration_hours,
        zone_id=zone_id,
        skill_type=skill_type,
    )

    return {
        "date": date_param,
        "duration_hours": duration_hours,
        "available_technicians": [
            {
                "technician_id": t.technician_id,
                "technician_name": t.technician_name,
                "email": t.email,
                "phone": t.phone,
                "scheduled_orders": t.scheduled_orders,
                "scheduled_hours": t.scheduled_hours,
                "available_hours": t.available_hours,
            }
            for t in available_list
        ],
        "total_available": len(available_list),
    }


# =============================================================================
# DISPATCH OPERATIONS
# =============================================================================

@router.get("/schedule/dispatch-board", dependencies=[Depends(Require("field-service:dispatch"))])
async def get_dispatch_board(
    date_param: Optional[str] = Query(None, alias="date", description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get dispatch board view for a given date."""
    check_date = date.fromisoformat(date_param) if date_param else date.today()

    service = DispatchService(db, principal)
    board = service.get_dispatch_board(board_date=check_date)

    return {
        "date": board.date,
        "orders": {
            k: [
                {
                    "id": o.id,
                    "order_number": o.order_number,
                    "title": o.title,
                    "order_type": o.order_type,
                    "status": o.status,
                    "priority": o.priority,
                    "scheduled_start_time": o.scheduled_start_time,
                    "estimated_duration_hours": o.estimated_duration_hours,
                    "customer_name": o.customer_name,
                    "service_address": o.service_address,
                    "city": o.city,
                    "technician_id": o.technician_id,
                    "technician_name": o.technician_name,
                    "team_id": o.team_id,
                    "is_overdue": o.is_overdue,
                }
                for o in v
            ]
            for k, v in board.orders.items()
        },
        "summary": {
            "total": board.summary.total,
            "unassigned": board.summary.unassigned,
            "assigned": board.summary.assigned,
            "in_field": board.summary.in_field,
            "completed": board.summary.completed,
        },
        "technician_workload": [
            {
                "technician_id": w.technician_id,
                "technician_name": w.technician_name,
                "total_orders": w.total_orders,
                "completed": w.completed,
                "in_progress": w.in_progress,
                "pending": w.pending,
            }
            for w in board.technician_workload
        ],
    }


@router.post("/schedule/bulk-assign", dependencies=[Depends(Require("field-service:dispatch"))])
async def bulk_assign_orders(
    request: BulkAssignRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk assign orders to a technician."""
    service = DispatchService(db, principal)

    data = BulkAssignData(
        order_ids=request.order_ids,
        technician_id=request.technician_id,
        team_id=request.team_id,
        notify_customers=request.notify_customers,
    )

    try:
        result = service.bulk_assign(data)
        db.commit()
    except NotFoundError as e:
        raise HTTPException(400, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))

    return {
        "assigned": result.assigned,
        "assigned_count": result.assigned_count,
        "technician_name": result.technician_name,
        "errors": [
            {"order_id": e.order_id, "error": e.error}
            for e in result.errors
        ],
    }


# =============================================================================
# ROUTE OPTIMIZATION
# =============================================================================

@router.get("/schedule/optimize", dependencies=[Depends(Require("field-service:dispatch"))])
async def get_route_suggestions(
    date_param: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    technician_id: Optional[int] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get route optimization suggestions for a given date."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    service = DispatchService(db, principal)
    result = service.get_route_suggestions(suggestion_date=check_date)

    return {
        "date": result.date,
        "unassigned_count": result.unassigned_count,
        "suggestions": [
            {
                "order_id": s.order_id,
                "order_number": s.order_number,
                "title": s.title,
                "customer_name": s.customer_name,
                "service_address": s.service_address,
                "city": s.city,
                "priority": s.priority,
                "suggested_technician_id": s.suggested_technician_id,
                "suggested_technician_name": s.suggested_technician_name,
                "confidence_score": s.confidence_score,
            }
            for s in result.suggestions
        ],
    }
