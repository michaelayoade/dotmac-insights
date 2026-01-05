"""
Shared dependencies for field service routes.

This module contains common imports, helpers, and permission dependencies
used across all field service route modules.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_, true
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Models - Field Service
from app.models.field_service import (
    ServiceOrder, ServiceOrderType, ServiceOrderStatus, ServiceOrderPriority,
    FieldTeam, FieldTeamMember, ServiceZone, TechnicianSkill,
)

# Models - Related
from app.models.party import CustomerAccount, Party
from app.models.employee import Employee, EmploymentStatus

# Permission dependencies
RequireFieldServiceRead = Depends(require_scope("field_service:read"))
RequireFieldServiceWrite = Depends(require_scope("field_service:write"))

# Template environment
templates = get_template_env()


# =============================================================================
# COMMON HELPER FUNCTIONS
# =============================================================================

def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string value from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    """Extract integer value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _form_enum(enum_cls: type, form: Any, key: str, default: Any) -> Any:
    """Extract enum value from form data."""
    default_value = str(getattr(default, "value", default))
    value = _form_str(form, key, default_value)
    try:
        return enum_cls(value)
    except ValueError:
        return default


def _form_date(form: Any, key: str) -> Optional[date]:
    """Extract date value from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile) or not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _form_datetime(form: Any, key: str) -> Optional[datetime]:
    """Extract datetime value from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile) or not value:
        return None
    try:
        # Try datetime first, then date
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        return None
    except (TypeError, ValueError):
        return None


# =============================================================================
# SERVICE ORDER ENUM OPTIONS
# =============================================================================

def get_status_options():
    """Get service order status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ServiceOrderStatus
    ]


def get_priority_options():
    """Get service order priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in ServiceOrderPriority
    ]


def get_type_options():
    """Get service order type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in ServiceOrderType
    ]


# =============================================================================
# DYNAMIC OPTIONS FROM DATABASE (using services)
# =============================================================================

def get_customer_options(db):
    """Get customer accounts for service order dropdown."""
    from app.services.subscribers import SubscriberService
    service = SubscriberService(db)
    customers = service.list_customer_accounts(limit=100)
    return [
        {"value": str(c.id), "label": c.party.name if c.party else f"Account {c.id}"}
        for c in customers
    ]


def get_technician_options(db):
    """Get active technicians for assignment dropdown."""
    from app.services.field_service import TeamService
    service = TeamService(db)
    employees = service.list_technicians(active_only=True)
    return [
        {"value": str(e.id), "label": f"{e.first_name} {e.last_name}".strip() or e.email}
        for e in employees
    ]


def get_team_options(db):
    """Get active field teams for assignment dropdown."""
    from app.services.field_service import TeamService
    service = TeamService(db)
    teams = service.list_teams(active_only=True)
    return [
        {"value": str(t.id), "label": t.name}
        for t in teams
    ]


def get_zone_options(db):
    """Get service zones for filtering/assignment."""
    from app.services.field_service import ScheduleService
    service = ScheduleService(db)
    zones = service.list_zones(active_only=True)
    return [
        {"value": str(z.id), "label": z.name}
        for z in zones
    ]


def get_skill_options(db):
    """Get technician skills for filtering."""
    from app.services.field_service import TeamService
    service = TeamService(db)
    skills = service.list_skills()
    return [
        {"value": str(s.id), "label": s.name}
        for s in skills
    ]


# =============================================================================
# FIELD SERVICE WEB SERVICE
# =============================================================================

from typing import Dict, List, Any


class FieldServiceWebService:
    """
    Service class for Field Service UI operations.

    Provides calendar views, availability checking, and dispatch operations.
    """

    def __init__(self, db, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # CALENDAR DATA
    # =========================================================================

    def get_calendar_data(
        self,
        start_date: date,
        end_date: date,
        technician_id: Optional[int] = None,
        team_id: Optional[int] = None,
        zone_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get calendar view of scheduled orders."""
        query = self.db.query(ServiceOrder).options(
            joinedload(ServiceOrder.customer),
            joinedload(ServiceOrder.technician),
        ).filter(
            ServiceOrder.scheduled_date >= start_date,
            ServiceOrder.scheduled_date <= end_date,
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
                "estimated_duration_hours": float(order.estimated_duration_hours) if order.estimated_duration_hours else 1.0,
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "technician_id": order.assigned_technician_id,
                "technician_name": order.technician.name if order.technician else None,
                "team_id": order.assigned_team_id,
                "latitude": float(order.latitude) if order.latitude else None,
                "longitude": float(order.longitude) if order.longitude else None,
            })

        # Calculate daily summaries
        daily_summary: Dict[str, Dict] = {}
        current = start_date
        while current <= end_date:
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
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "calendar": calendar,
            "daily_summary": daily_summary,
            "total_orders": len(orders),
        }

    def get_technician_schedule(
        self,
        technician_id: int,
        start_date: date,
        days: int = 7,
    ) -> Optional[Dict[str, Any]]:
        """Get a technician's schedule."""
        employee = self.db.query(Employee).filter(Employee.id == technician_id).first()
        if not employee:
            return None

        end_date = start_date + timedelta(days=days - 1)

        orders = self.db.query(ServiceOrder).options(
            joinedload(ServiceOrder.customer),
        ).filter(
            ServiceOrder.assigned_technician_id == technician_id,
            ServiceOrder.scheduled_date >= start_date,
            ServiceOrder.scheduled_date <= end_date,
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
                "estimated_duration_hours": float(order.estimated_duration_hours) if order.estimated_duration_hours else 1.0,
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "latitude": float(order.latitude) if order.latitude else None,
                "longitude": float(order.longitude) if order.longitude else None,
            })

        # Calculate utilization
        total_hours_scheduled = sum(
            float(o.estimated_duration_hours) if o.estimated_duration_hours else 1.0
            for o in orders
            if o.status not in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]
        )

        return {
            "technician": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}".strip() or employee.email,
                "email": employee.email,
            },
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "schedule": schedule,
            "summary": {
                "total_orders": len(orders),
                "total_hours_scheduled": round(total_hours_scheduled, 1),
                "completed": sum(1 for o in orders if o.status == ServiceOrderStatus.COMPLETED),
            },
        }

    # =========================================================================
    # DISPATCH BOARD
    # =========================================================================

    def get_dispatch_board(self, check_date: date) -> Dict[str, Any]:
        """Get dispatch board view for a given date."""
        orders = self.db.query(ServiceOrder).options(
            joinedload(ServiceOrder.customer),
            joinedload(ServiceOrder.technician),
        ).filter(
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
                "estimated_duration_hours": float(order.estimated_duration_hours) if order.estimated_duration_hours else 1.0,
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "technician_id": order.assigned_technician_id,
                "technician_name": order.technician.name if order.technician else None,
                "team_id": order.assigned_team_id,
                "latitude": float(order.latitude) if order.latitude else None,
                "longitude": float(order.longitude) if order.longitude else None,
            }

            if order.status in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED] and not order.assigned_technician_id:
                by_status["unassigned"].append(order_data)
            elif order.status == ServiceOrderStatus.DISPATCHED:
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
        from app.models.field_service import FieldTeamMember
        technicians = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True
            )
        ).distinct().all()

        tech_workload = []
        for tech in technicians:
            tech_orders = [o for o in orders if o.assigned_technician_id == tech.id]
            tech_workload.append({
                "technician_id": tech.id,
                "technician_name": f"{tech.first_name} {tech.last_name}".strip() or tech.email,
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
            "all_orders": [self._order_to_dict(o) for o in orders],
            "summary": {
                "total": len(orders),
                "unassigned": len(by_status["unassigned"]),
                "assigned": len(by_status["assigned"]),
                "in_field": len(by_status["en_route"]) + len(by_status["on_site"]) + len(by_status["in_progress"]),
                "completed": len(by_status["completed"]),
            },
            "technician_workload": tech_workload,
        }

    def _order_to_dict(self, order: ServiceOrder) -> Dict[str, Any]:
        """Convert order to dict for templates."""
        return {
            "id": order.id,
            "order_number": order.order_number,
            "title": order.title,
            "status": order.status.value,
            "priority": order.priority.value,
            "order_type": order.order_type.value,
            "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
            "scheduled_start_time": order.scheduled_start_time.isoformat() if order.scheduled_start_time else None,
            "customer_name": order.customer.name if order.customer else None,
            "service_address": order.service_address,
            "city": order.city,
            "technician_id": order.assigned_technician_id,
            "technician_name": order.technician.name if order.technician else None,
            "latitude": float(order.latitude) if order.latitude else None,
            "longitude": float(order.longitude) if order.longitude else None,
        }

    # =========================================================================
    # SUMMARY STATS
    # =========================================================================

    def get_daily_summary(self, check_date: date) -> Dict[str, Any]:
        """Get summary statistics for a date."""
        orders = self.db.query(ServiceOrder).filter(
            ServiceOrder.scheduled_date == check_date
        ).all()

        return {
            "date": check_date.isoformat(),
            "total": len(orders),
            "unassigned": sum(1 for o in orders if not o.assigned_technician_id),
            "completed": sum(1 for o in orders if o.status == ServiceOrderStatus.COMPLETED),
            "in_progress": sum(1 for o in orders if o.status == ServiceOrderStatus.IN_PROGRESS),
            "urgent": sum(1 for o in orders if o.priority in [ServiceOrderPriority.URGENT, ServiceOrderPriority.EMERGENCY]),
        }
