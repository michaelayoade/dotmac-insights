"""
Scheduling and Dispatch API

Calendar views, availability checking, and bulk operations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Dict, Any, Optional, List, cast
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderPriority,
    FieldTeam,
    FieldTeamMember,
    ServiceZone,
)
from app.models.employee import Employee
from app.services.customer_notifications import get_notification_service

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
) -> Dict[str, Any]:
    """Get calendar view of scheduled orders."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    if (end - start).days > 90:
        raise HTTPException(400, "Date range cannot exceed 90 days")

    query = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    )

    if technician_id:
        query = query.filter(ServiceOrder.assigned_technician_id == technician_id)

    if team_id:
        query = query.filter(ServiceOrder.assigned_team_id == team_id)

    if zone_id:
        query = query.filter(ServiceOrder.zone_id == zone_id)

    orders = query.order_by(
        ServiceOrder.scheduled_date,
        ServiceOrder.scheduled_start_time
    ).all()

    # Group by date
    calendar: Dict[str, List[Dict]] = {}
    for order in orders:
        date_key = order.scheduled_date.isoformat()
        if date_key not in calendar:
            calendar[date_key] = []

        calendar[date_key].append({
            "id": order.id,
            "order_number": order.order_number,
            "title": order.title,
            "status": order.status.value,
            "priority": order.priority.value,
            "order_type": order.order_type.value,
            "scheduled_start_time": order.scheduled_start_time.isoformat() if order.scheduled_start_time else None,
            "scheduled_end_time": order.scheduled_end_time.isoformat() if order.scheduled_end_time else None,
            "estimated_duration_hours": float(order.estimated_duration_hours),
            "customer_name": order.customer.name if order.customer else None,
            "service_address": order.service_address,
            "city": order.city,
            "technician_id": order.assigned_technician_id,
            "technician_name": order.technician.name if order.technician else None,
            "team_id": order.assigned_team_id,
        })

    # Calculate daily summaries
    daily_summary: Dict[str, Dict] = {}
    current = start
    while current <= end:
        date_key = current.isoformat()
        day_orders = calendar.get(date_key, [])
        daily_summary[date_key] = {
            "total": len(day_orders),
            "completed": sum(1 for o in day_orders if o["status"] == "completed"),
            "in_progress": sum(1 for o in day_orders if o["status"] == "in_progress"),
            "scheduled": sum(1 for o in day_orders if o["status"] in ["scheduled", "dispatched"]),
            "urgent": sum(1 for o in day_orders if o["priority"] in ["urgent", "emergency"]),
        }
        current += timedelta(days=1)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "calendar": calendar,
        "daily_summary": daily_summary,
    }


@router.get("/schedule/technician/{technician_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_technician_schedule(
    technician_id: int,
    date_param: Optional[str] = Query(None, alias="date", description="Date (YYYY-MM-DD)"),
    days: int = Query(default=7, le=30),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a technician's schedule."""
    employee = db.query(Employee).filter(Employee.id == technician_id).first()
    if not employee:
        raise HTTPException(404, "Technician not found")

    start = date.fromisoformat(date_param) if date_param else date.today()
    end = start + timedelta(days=days - 1)

    orders = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_technician_id == technician_id,
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).order_by(
        ServiceOrder.scheduled_date,
        ServiceOrder.scheduled_start_time
    ).all()

    # Group by date
    schedule: Dict[str, List[Dict]] = {}
    for order in orders:
        date_key = order.scheduled_date.isoformat()
        if date_key not in schedule:
            schedule[date_key] = []

        schedule[date_key].append({
            "id": order.id,
            "order_number": order.order_number,
            "title": order.title,
            "status": order.status.value,
            "priority": order.priority.value,
            "order_type": order.order_type.value,
            "scheduled_start_time": order.scheduled_start_time.isoformat() if order.scheduled_start_time else None,
            "scheduled_end_time": order.scheduled_end_time.isoformat() if order.scheduled_end_time else None,
            "estimated_duration_hours": float(order.estimated_duration_hours),
            "customer_name": order.customer.name if order.customer else None,
            "service_address": order.service_address,
            "city": order.city,
            "latitude": float(order.latitude) if order.latitude else None,
            "longitude": float(order.longitude) if order.longitude else None,
        })

    # Calculate utilization
    total_hours_scheduled = sum(
        float(o.estimated_duration_hours) for o in orders
        if o.status not in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]
    )

    return {
        "technician": {
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
        },
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "schedule": schedule,
        "summary": {
            "total_orders": len(orders),
            "total_hours_scheduled": round(total_hours_scheduled, 1),
            "completed": sum(1 for o in orders if o.status == ServiceOrderStatus.COMPLETED),
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
) -> Dict[str, Any]:
    """Check technician availability for a given date."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    # Get technicians to check
    technicians_query = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    )

    if technician_id:
        technicians_query = technicians_query.filter(Employee.id == technician_id)

    if team_id:
        technicians_query = technicians_query.filter(FieldTeamMember.team_id == team_id)

    technicians = technicians_query.distinct().all()

    availability = []
    for tech in technicians:
        # Get scheduled orders for this date
        orders = db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.scheduled_date == check_date,
            ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED])
        ).all()

        total_scheduled_hours = sum(float(o.estimated_duration_hours) for o in orders)

        # Get team membership for max orders
        membership = db.query(FieldTeamMember).filter(
            FieldTeamMember.employee_id == tech.id,
            FieldTeamMember.is_active == True
        ).first()

        max_hours = 8  # Default 8 hour workday
        if membership and membership.team:
            max_orders = membership.team.max_daily_orders
        else:
            max_orders = 10

        available_hours = max(0, max_hours - total_scheduled_hours)
        available_slots = max(0, max_orders - len(orders))

        # Build time slots
        scheduled_slots = []
        for order in orders:
            if order.scheduled_start_time and order.scheduled_end_time:
                scheduled_slots.append({
                    "start": order.scheduled_start_time.isoformat(),
                    "end": order.scheduled_end_time.isoformat(),
                    "order_id": order.id,
                    "title": order.title,
                })

        availability.append({
            "technician_id": tech.id,
            "technician_name": tech.name,
            "date": check_date.isoformat(),
            "scheduled_orders": len(orders),
            "scheduled_hours": round(total_scheduled_hours, 1),
            "available_hours": round(available_hours, 1),
            "available_slots": available_slots,
            "is_available": available_slots > 0,
            "scheduled_slots": scheduled_slots,
        })

    return {
        "date": date_param,
        "availability": availability,
    }


@router.get("/schedule/available-technicians", dependencies=[Depends(Require("explorer:read"))])
async def get_available_technicians(
    date_param: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    start_time: Optional[str] = None,
    duration_hours: float = 1.0,
    zone_id: Optional[int] = None,
    skill_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get list of available technicians for a given date/time."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    # Get all active technicians
    query = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    )

    if zone_id:
        # Filter by technicians in teams that cover this zone
        query = query.join(
            FieldTeam,
            FieldTeam.id == FieldTeamMember.team_id
        ).filter(
            FieldTeam.coverage_zone_ids.contains([zone_id])
        )

    if skill_type:
        from app.models.field_service import TechnicianSkill
        query = query.join(
            TechnicianSkill,
            TechnicianSkill.employee_id == Employee.id
        ).filter(
            TechnicianSkill.skill_type == skill_type,
            TechnicianSkill.is_active == True
        )

    technicians = query.distinct().all()

    available = []
    for tech in technicians:
        # Count scheduled orders
        orders = db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.scheduled_date == check_date,
            ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED, ServiceOrderStatus.COMPLETED])
        ).all()

        total_hours = sum(float(o.estimated_duration_hours) for o in orders)

        # Check if available
        if total_hours + duration_hours <= 8:  # 8 hour max
            available.append({
                "technician_id": tech.id,
                "technician_name": tech.name,
                "email": tech.email,
                "phone": tech.phone,
                "scheduled_orders": len(orders),
                "scheduled_hours": round(total_hours, 1),
                "available_hours": round(8 - total_hours, 1),
            })

    # Sort by available hours (most available first)
    available.sort(key=lambda x: float(cast(float | int, x.get("available_hours", 0.0))), reverse=True)

    return {
        "date": date_param,
        "duration_hours": duration_hours,
        "available_technicians": available,
        "total_available": len(available),
    }


# =============================================================================
# DISPATCH OPERATIONS
# =============================================================================

@router.get("/schedule/dispatch-board", dependencies=[Depends(Require("field-service:dispatch"))])
async def get_dispatch_board(
    date_param: Optional[str] = Query(None, alias="date", description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get dispatch board view for a given date."""
    check_date = date.fromisoformat(date_param) if date_param else date.today()

    # Get all orders for this date
    orders = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date == check_date
    ).order_by(
        ServiceOrder.priority.desc(),
        ServiceOrder.scheduled_start_time
    ).all()

    # Group by status
    by_status: Dict[str, List[Dict]] = {
        "unassigned": [],
        "assigned": [],
        "en_route": [],
        "on_site": [],
        "in_progress": [],
        "completed": [],
    }

    for order in orders:
        order_data = {
            "id": order.id,
            "order_number": order.order_number,
            "title": order.title,
            "order_type": order.order_type.value,
            "status": order.status.value,
            "priority": order.priority.value,
            "scheduled_start_time": order.scheduled_start_time.isoformat() if order.scheduled_start_time else None,
            "estimated_duration_hours": float(order.estimated_duration_hours),
            "customer_name": order.customer.name if order.customer else None,
            "service_address": order.service_address,
            "city": order.city,
            "technician_id": order.assigned_technician_id,
            "technician_name": order.technician.name if order.technician else None,
            "team_id": order.assigned_team_id,
            "is_overdue": order.is_overdue,
        }

        if order.status in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED] and not order.assigned_technician_id:
            by_status["unassigned"].append(order_data)
        elif order.status in [ServiceOrderStatus.DISPATCHED]:
            by_status["assigned"].append(order_data)
        elif order.status == ServiceOrderStatus.EN_ROUTE:
            by_status["en_route"].append(order_data)
        elif order.status == ServiceOrderStatus.ON_SITE:
            by_status["on_site"].append(order_data)
        elif order.status == ServiceOrderStatus.IN_PROGRESS:
            by_status["in_progress"].append(order_data)
        elif order.status == ServiceOrderStatus.COMPLETED:
            by_status["completed"].append(order_data)

    # Get technicians with their workload
    technicians = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    ).distinct().all()

    tech_workload = []
    for tech in technicians:
        tech_orders = [o for o in orders if o.assigned_technician_id == tech.id]
        tech_workload.append({
            "technician_id": tech.id,
            "technician_name": tech.name,
            "total_orders": len(tech_orders),
            "completed": sum(1 for o in tech_orders if o.status == ServiceOrderStatus.COMPLETED),
            "in_progress": sum(1 for o in tech_orders if o.status == ServiceOrderStatus.IN_PROGRESS),
            "pending": sum(1 for o in tech_orders if o.status in [
                ServiceOrderStatus.DISPATCHED, ServiceOrderStatus.EN_ROUTE, ServiceOrderStatus.ON_SITE
            ]),
        })

    return {
        "date": check_date.isoformat(),
        "orders": by_status,
        "summary": {
            "total": len(orders),
            "unassigned": len(by_status["unassigned"]),
            "assigned": len(by_status["assigned"]),
            "in_field": len(by_status["en_route"]) + len(by_status["on_site"]) + len(by_status["in_progress"]),
            "completed": len(by_status["completed"]),
        },
        "technician_workload": tech_workload,
    }


@router.post("/schedule/bulk-assign", dependencies=[Depends(Require("field-service:dispatch"))])
async def bulk_assign_orders(
    request: BulkAssignRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk assign orders to a technician."""
    # Validate technician
    technician = db.query(Employee).filter(Employee.id == request.technician_id).first()
    if not technician:
        raise HTTPException(400, "Technician not found")

    # Get orders
    orders = db.query(ServiceOrder).filter(
        ServiceOrder.id.in_(request.order_ids)
    ).all()

    if not orders:
        raise HTTPException(400, "No valid orders found")

    notification_service = get_notification_service(db)
    assigned = []
    errors = []

    for order in orders:
        if order.status not in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED]:
            errors.append({
                "order_id": order.id,
                "error": f"Cannot assign order in {order.status.value} status"
            })
            continue

        order.assigned_technician_id = request.technician_id
        if request.team_id:
            order.assigned_team_id = request.team_id

        order.status = ServiceOrderStatus.DISPATCHED

        # Notify customer if requested
        if request.notify_customers:
            try:
                notification_service.notify_technician_assigned(order)
                order.customer_notified = True
                order.last_notification_at = datetime.utcnow()
            except Exception as e:
                errors.append({
                    "order_id": order.id,
                    "error": f"Notification failed: {str(e)}"
                })

        assigned.append(order.id)

    db.commit()

    return {
        "assigned": assigned,
        "assigned_count": len(assigned),
        "technician_name": technician.name,
        "errors": errors,
    }


# =============================================================================
# ROUTE OPTIMIZATION
# =============================================================================

@router.get("/schedule/optimize", dependencies=[Depends(Require("field-service:dispatch"))])
async def get_route_suggestions(
    date_param: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    technician_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get route optimization suggestions for a given date."""
    try:
        check_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    # Get unassigned orders
    unassigned_query = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date == check_date,
        ServiceOrder.assigned_technician_id.is_(None),
        ServiceOrder.status.in_([ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED])
    )

    unassigned = unassigned_query.all()

    # Get technicians with availability
    technicians = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    ).distinct().all()

    suggestions = []

    for order in unassigned:
        # Find best technician based on:
        # 1. Zone coverage
        # 2. Current workload
        # 3. Skills (if applicable)

        best_match = None
        best_score = -1

        for tech in technicians:
            score = 0

            # Check workload
            tech_orders = db.query(func.count(ServiceOrder.id)).filter(
                ServiceOrder.assigned_technician_id == tech.id,
                ServiceOrder.scheduled_date == check_date,
                ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED])
            ).scalar() or 0

            if tech_orders >= 10:  # Max orders reached
                continue

            # Lower workload = higher score
            score += (10 - tech_orders) * 10

            # Zone matching
            membership = db.query(FieldTeamMember).filter(
                FieldTeamMember.employee_id == tech.id,
                FieldTeamMember.is_active == True
            ).first()

            if membership and membership.team and order.zone_id:
                if membership.team.coverage_zone_ids and order.zone_id in membership.team.coverage_zone_ids:
                    score += 50  # Zone match bonus

            if score > best_score:
                best_score = score
                best_match = tech

        if best_match:
            suggestions.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "title": order.title,
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "priority": order.priority.value,
                "suggested_technician_id": best_match.id,
                "suggested_technician_name": best_match.name,
                "confidence_score": min(100, best_score),
            })

    return {
        "date": date_param,
        "unassigned_count": len(unassigned),
        "suggestions": suggestions,
    }
