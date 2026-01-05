"""Schedule service for field service scheduling.

This service handles:
- Calendar views
- Technician schedules
- Availability checking
- Schedule overlap validation
"""
from __future__ import annotations

from datetime import date, time, timedelta, datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    FieldTeam,
    FieldTeamMember,
    TechnicianSkill,
    ServiceZone,
)
from app.models.employee import Employee

from .schedule_types import (
    CalendarFilters,
    CalendarDay,
    CalendarView,
    TechnicianSchedule,
    TechnicianAvailability,
    AvailabilitySlot,
    AvailableTechnician,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ScheduleService"]


class ScheduleService:
    """Service for managing field service schedules.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for scoping if needed).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Calendar Views
    # -------------------------------------------------------------------------

    def get_calendar(self, filters: CalendarFilters) -> CalendarView:
        """Get calendar view of scheduled orders.

        Args:
            filters: Calendar filters

        Returns:
            CalendarView with orders grouped by date
        """
        if (filters.end_date - filters.start_date).days > 90:
            from app.services.errors import ValidationError
            raise ValidationError("Date range cannot exceed 90 days")

        query = self.db.query(ServiceOrder).filter(
            ServiceOrder.scheduled_date >= filters.start_date,
            ServiceOrder.scheduled_date <= filters.end_date,
        )

        if filters.technician_id:
            query = query.filter(
                ServiceOrder.assigned_technician_id == filters.technician_id
            )
        if filters.team_id:
            query = query.filter(ServiceOrder.assigned_team_id == filters.team_id)
        if filters.zone_id:
            query = query.filter(ServiceOrder.zone_id == filters.zone_id)
        if filters.company:
            query = query.filter(ServiceOrder.company == filters.company)

        orders = query.order_by(
            ServiceOrder.scheduled_date,
            ServiceOrder.scheduled_start_time,
        ).all()

        # Group by date
        calendar: Dict[str, List[Dict[str, Any]]] = {}
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
                "scheduled_start_time": (
                    order.scheduled_start_time.isoformat()
                    if order.scheduled_start_time
                    else None
                ),
                "scheduled_end_time": (
                    order.scheduled_end_time.isoformat()
                    if order.scheduled_end_time
                    else None
                ),
                "estimated_duration_hours": float(order.estimated_duration_hours),
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "technician_id": order.assigned_technician_id,
                "technician_name": order.technician.name if order.technician else None,
                "team_id": order.assigned_team_id,
            })

        # Calculate daily summaries
        daily_summary: Dict[str, CalendarDay] = {}
        current = filters.start_date
        while current <= filters.end_date:
            date_key = current.isoformat()
            day_orders = calendar.get(date_key, [])
            daily_summary[date_key] = CalendarDay(
                total=len(day_orders),
                completed=sum(1 for o in day_orders if o["status"] == "completed"),
                in_progress=sum(1 for o in day_orders if o["status"] == "in_progress"),
                scheduled=sum(
                    1
                    for o in day_orders
                    if o["status"] in ["scheduled", "dispatched"]
                ),
                urgent=sum(
                    1
                    for o in day_orders
                    if o["priority"] in ["urgent", "emergency"]
                ),
            )
            current += timedelta(days=1)

        return CalendarView(
            start_date=filters.start_date.isoformat(),
            end_date=filters.end_date.isoformat(),
            calendar=calendar,
            daily_summary=daily_summary,
        )

    def get_technician_schedule(
        self,
        technician_id: int,
        start_date: Optional[date] = None,
        days: int = 7,
    ) -> TechnicianSchedule:
        """Get a technician's schedule.

        Args:
            technician_id: ID of the technician
            start_date: Start date (defaults to today)
            days: Number of days (max 30)

        Returns:
            TechnicianSchedule with orders grouped by date

        Raises:
            NotFoundError: If technician not found
        """
        from app.services.errors import NotFoundError

        employee = self.db.query(Employee).filter(Employee.id == technician_id).first()
        if not employee:
            raise NotFoundError(f"Technician with ID {technician_id} not found")

        days = min(days, 30)
        start = start_date or date.today()
        end = start + timedelta(days=days - 1)

        orders = (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.assigned_technician_id == technician_id,
                ServiceOrder.scheduled_date >= start,
                ServiceOrder.scheduled_date <= end,
            )
            .order_by(
                ServiceOrder.scheduled_date,
                ServiceOrder.scheduled_start_time,
            )
            .all()
        )

        # Group by date
        schedule: Dict[str, List[Dict[str, Any]]] = {}
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
                "scheduled_start_time": (
                    order.scheduled_start_time.isoformat()
                    if order.scheduled_start_time
                    else None
                ),
                "scheduled_end_time": (
                    order.scheduled_end_time.isoformat()
                    if order.scheduled_end_time
                    else None
                ),
                "estimated_duration_hours": float(order.estimated_duration_hours),
                "customer_name": order.customer.name if order.customer else None,
                "service_address": order.service_address,
                "city": order.city,
                "latitude": float(order.latitude) if order.latitude else None,
                "longitude": float(order.longitude) if order.longitude else None,
            })

        # Calculate totals
        total_hours_scheduled = sum(
            float(o.estimated_duration_hours)
            for o in orders
            if o.status not in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]
        )

        return TechnicianSchedule(
            technician_id=employee.id,
            technician_name=employee.name,
            technician_email=employee.email,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            schedule=schedule,
            total_orders=len(orders),
            total_hours_scheduled=round(total_hours_scheduled, 1),
            completed=sum(
                1 for o in orders if o.status == ServiceOrderStatus.COMPLETED
            ),
        )

    # -------------------------------------------------------------------------
    # Availability
    # -------------------------------------------------------------------------

    def check_availability(
        self,
        check_date: date,
        technician_id: Optional[int] = None,
        team_id: Optional[int] = None,
    ) -> List[TechnicianAvailability]:
        """Check technician availability for a given date.

        Args:
            check_date: Date to check
            technician_id: Optional specific technician
            team_id: Optional specific team

        Returns:
            List of availability for each technician
        """
        # Get technicians to check
        technicians_query = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True,
            ),
        )

        if technician_id:
            technicians_query = technicians_query.filter(Employee.id == technician_id)
        if team_id:
            technicians_query = technicians_query.filter(
                FieldTeamMember.team_id == team_id
            )

        technicians = technicians_query.distinct().all()

        availability = []
        for tech in technicians:
            # Get scheduled orders for this date
            orders = (
                self.db.query(ServiceOrder)
                .filter(
                    ServiceOrder.assigned_technician_id == tech.id,
                    ServiceOrder.scheduled_date == check_date,
                    ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED]),
                )
                .all()
            )

            total_scheduled_hours = sum(float(o.estimated_duration_hours) for o in orders)

            # Get team membership for max orders
            membership = (
                self.db.query(FieldTeamMember)
                .filter(
                    FieldTeamMember.party_id == tech.party_id,
                    FieldTeamMember.is_active == True,
                )
                .first()
            )

            max_hours = 8.0  # Default 8 hour workday
            max_orders = (
                membership.team.max_daily_orders if membership and membership.team else 10
            )

            available_hours = max(0.0, max_hours - total_scheduled_hours)
            available_slots = max(0, max_orders - len(orders))

            # Build time slots
            scheduled_slots = []
            for order in orders:
                if order.scheduled_start_time and order.scheduled_end_time:
                    scheduled_slots.append(
                        AvailabilitySlot(
                            start=order.scheduled_start_time.isoformat(),
                            end=order.scheduled_end_time.isoformat(),
                            order_id=order.id,
                            title=order.title,
                        )
                    )

            availability.append(
                TechnicianAvailability(
                    technician_id=tech.id,
                    technician_name=tech.name,
                    date=check_date.isoformat(),
                    scheduled_orders=len(orders),
                    scheduled_hours=round(total_scheduled_hours, 1),
                    available_hours=round(available_hours, 1),
                    available_slots=available_slots,
                    is_available=available_slots > 0,
                    scheduled_slots=scheduled_slots,
                )
            )

        return availability

    def get_available_technicians(
        self,
        check_date: date,
        duration_hours: float = 1.0,
        zone_id: Optional[int] = None,
        skill_type: Optional[str] = None,
    ) -> List[AvailableTechnician]:
        """Get list of available technicians for a given date/time.

        Args:
            check_date: Date to check
            duration_hours: Required duration
            zone_id: Optional zone filter
            skill_type: Optional skill filter

        Returns:
            List of available technicians sorted by availability
        """
        # Get all active technicians
        query = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True,
            ),
        )

        if zone_id:
            # Filter by technicians in teams that cover this zone
            query = query.join(
                FieldTeam,
                FieldTeam.id == FieldTeamMember.team_id,
            ).filter(FieldTeam.coverage_zone_ids.contains([zone_id]))

        if skill_type:
            query = query.join(
                TechnicianSkill,
                TechnicianSkill.employee_id == Employee.id,
            ).filter(
                TechnicianSkill.skill_type == skill_type,
                TechnicianSkill.is_active == True,
            )

        technicians = query.distinct().all()

        available = []
        for tech in technicians:
            # Count scheduled orders
            orders = (
                self.db.query(ServiceOrder)
                .filter(
                    ServiceOrder.assigned_technician_id == tech.id,
                    ServiceOrder.scheduled_date == check_date,
                    ServiceOrder.status.notin_(
                        [ServiceOrderStatus.CANCELLED, ServiceOrderStatus.COMPLETED]
                    ),
                )
                .all()
            )

            total_hours = sum(float(o.estimated_duration_hours) for o in orders)

            # Check if available
            if total_hours + duration_hours <= 8.0:  # 8 hour max
                available.append(
                    AvailableTechnician(
                        technician_id=tech.id,
                        technician_name=tech.name,
                        email=tech.email,
                        phone=tech.phone,
                        scheduled_orders=len(orders),
                        scheduled_hours=round(total_hours, 1),
                        available_hours=round(8.0 - total_hours, 1),
                    )
                )

        # Sort by available hours (most available first)
        available.sort(key=lambda x: x.available_hours, reverse=True)
        return available

    # -------------------------------------------------------------------------
    # Schedule Validation
    # -------------------------------------------------------------------------

    def check_schedule_overlap(
        self,
        technician_id: int,
        check_date: date,
        start_time: Optional[time],
        end_time: Optional[time],
        duration_hours: float,
        exclude_order_id: Optional[int] = None,
    ) -> bool:
        """Check if a schedule slot overlaps with existing orders.

        Args:
            technician_id: Technician to check
            check_date: Date to check
            start_time: Start time (optional)
            end_time: End time (optional)
            duration_hours: Duration in hours
            exclude_order_id: Order ID to exclude (for updates)

        Returns:
            True if there is an overlap, False if slot is available
        """
        query = self.db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == technician_id,
            ServiceOrder.scheduled_date == check_date,
            ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED]),
        )

        if exclude_order_id:
            query = query.filter(ServiceOrder.id != exclude_order_id)

        existing_orders = query.all()

        # If no time specified, check capacity only
        if not start_time:
            total_hours = sum(float(o.estimated_duration_hours) for o in existing_orders)
            return total_hours + duration_hours > 8.0  # 8 hour max

        # Check time overlap
        for order in existing_orders:
            if not order.scheduled_start_time or not order.scheduled_end_time:
                continue

            # Check if times overlap
            if start_time and end_time:
                if not (end_time <= order.scheduled_start_time or start_time >= order.scheduled_end_time):
                    return True

        return False
