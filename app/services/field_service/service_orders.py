"""Service Order service - business logic for field service orders.

This service encapsulates all service order business logic:
- CRUD operations
- Workflow transitions (schedule, dispatch, complete, cancel)
- Assignment to technicians/teams
- Time tracking and costing
- Status lifecycle management

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderType,
    ServiceOrderPriority,
    ServiceOrderStatusHistory,
    ServiceOrderItem,
    ServiceTimeEntry,
    ServiceChecklist,
    TimeEntryType,
    FieldTeam,
    ServiceZone,
)
from app.models.party import CustomerAccount
from app.models.employee import Employee
from app.services.base import paginate, safe_filter, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .service_types import (
    ServiceOrderFilters,
    ServiceOrderCreateData,
    ServiceOrderUpdateData,
    ServiceOrderItemData,
    TimeEntryData,
    ChecklistItemData,
    DispatchData,
    CompletionData,
    RescheduleData,
    ServiceOrderStats,
    TechnicianWorkload,
    ServiceCostBreakdown,
)
from .billing_config import (
    FieldServiceBillingConfig,
    FieldServiceBillingConfigService,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ServiceOrderService"]


# Valid status transitions
STATUS_TRANSITIONS = {
    ServiceOrderStatus.DRAFT: [
        ServiceOrderStatus.SCHEDULED,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.SCHEDULED: [
        ServiceOrderStatus.DISPATCHED,
        ServiceOrderStatus.RESCHEDULED,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.DISPATCHED: [
        ServiceOrderStatus.EN_ROUTE,
        ServiceOrderStatus.RESCHEDULED,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.EN_ROUTE: [
        ServiceOrderStatus.ON_SITE,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.ON_SITE: [
        ServiceOrderStatus.IN_PROGRESS,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.IN_PROGRESS: [
        ServiceOrderStatus.PENDING_PARTS,
        ServiceOrderStatus.COMPLETED,
        ServiceOrderStatus.FAILED,
    ],
    ServiceOrderStatus.PENDING_PARTS: [
        ServiceOrderStatus.IN_PROGRESS,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.RESCHEDULED: [
        ServiceOrderStatus.SCHEDULED,
        ServiceOrderStatus.CANCELLED,
    ],
    ServiceOrderStatus.COMPLETED: [],  # Terminal state
    ServiceOrderStatus.CANCELLED: [],  # Terminal state
    ServiceOrderStatus.FAILED: [
        ServiceOrderStatus.RESCHEDULED,
    ],
}


class ServiceOrderService:
    """Service for service order business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_orders(
        self,
        filters: Optional[ServiceOrderFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ServiceOrder]:
        """List service orders with filters and pagination."""
        if filters is None:
            filters = ServiceOrderFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ServiceOrder)
        query = scoped_query(query, self.principal)

        # Search
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    ServiceOrder.order_number.ilike(search_term),
                    ServiceOrder.title.ilike(search_term),
                    ServiceOrder.service_address.ilike(search_term),
                )
            )

        # Status filter
        if filters.statuses:
            valid_statuses = []
            for status_value in filters.statuses:
                try:
                    valid_statuses.append(ServiceOrderStatus(status_value))
                except ValueError:
                    continue
            if valid_statuses:
                query = query.filter(ServiceOrder.status.in_(valid_statuses))
        elif filters.status:
            try:
                status_enum = ServiceOrderStatus(filters.status)
                query = query.filter(ServiceOrder.status == status_enum)
            except ValueError:
                pass

        # Type filter
        if filters.order_type:
            try:
                type_enum = ServiceOrderType(filters.order_type)
                query = query.filter(ServiceOrder.order_type == type_enum)
            except ValueError:
                pass

        # Priority filter
        if filters.priority:
            try:
                priority_enum = ServiceOrderPriority(filters.priority)
                query = query.filter(ServiceOrder.priority == priority_enum)
            except ValueError:
                pass

        # Entity filters
        if filters.customer_account_id:
            query = query.filter(ServiceOrder.customer_account_id == filters.customer_account_id)
        if filters.technician_id:
            query = query.filter(
                ServiceOrder.assigned_technician_id == filters.technician_id
            )
        if filters.team_id:
            query = query.filter(ServiceOrder.assigned_team_id == filters.team_id)
        if filters.zone_id:
            query = query.filter(ServiceOrder.zone_id == filters.zone_id)
        if filters.city:
            query = query.filter(ServiceOrder.city == filters.city)

        # Date filters
        if filters.scheduled_date_from:
            query = query.filter(
                ServiceOrder.scheduled_date >= filters.scheduled_date_from
            )
        if filters.scheduled_date_to:
            query = query.filter(
                ServiceOrder.scheduled_date <= filters.scheduled_date_to
            )

        # Billing filters
        if filters.is_billable is not None:
            query = query.filter(ServiceOrder.is_billable == filters.is_billable)

        # Sorting
        sort_column = getattr(ServiceOrder, filters.sort_by, ServiceOrder.scheduled_date)
        ascending = str(filters.sort_dir).lower() == "asc"
        if filters.sort_by == "scheduled_date":
            query = query.order_by(
                sort_column.asc() if ascending else sort_column.desc(),
                ServiceOrder.scheduled_start_time.asc(),
            )
        else:
            query = query.order_by(sort_column.asc() if ascending else sort_column.desc())

        return paginate(query, pagination)

    def get_order(self, order_id: int) -> ServiceOrder:
        """Get a service order by ID with related entities."""
        order = (
            self.db.query(ServiceOrder)
            .options(
                joinedload(ServiceOrder.customer),
                joinedload(ServiceOrder.technician),
                joinedload(ServiceOrder.team),
                joinedload(ServiceOrder.items_used),
                joinedload(ServiceOrder.time_entries),
                joinedload(ServiceOrder.checklist_items),
            )
            .filter(ServiceOrder.id == order_id)
            .first()
        )
        if not order:
            raise NotFoundError(f"Service order {order_id} not found")
        return order

    def get_by_order_number(self, order_number: str) -> ServiceOrder:
        """Get a service order by order number."""
        order = (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.order_number == order_number)
            .first()
        )
        if not order:
            raise NotFoundError(f"Service order {order_number} not found")
        return order

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_order(self, data: ServiceOrderCreateData) -> ServiceOrder:
        """Create a new service order."""
        # Validate customer exists
        customer = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.id == data.customer_account_id)
            .first()
        )
        if not customer:
            raise ValidationError(f"Customer account {data.customer_account_id} not found")

        # Validate order type
        try:
            order_type = ServiceOrderType(data.order_type)
        except ValueError:
            raise ValidationError(f"Invalid order type: {data.order_type}")

        # Validate priority
        try:
            priority = ServiceOrderPriority(data.priority)
        except ValueError:
            priority = ServiceOrderPriority.MEDIUM

        # Generate order number
        order_number = self._generate_order_number()

        # Create order
        order = ServiceOrder(
            order_number=order_number,
            customer_account_id=data.customer_account_id,
            order_type=order_type,
            priority=priority,
            status=ServiceOrderStatus.DRAFT,
            title=data.title,
            description=data.description,
            service_address=data.service_address,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            latitude=data.latitude,
            longitude=data.longitude,
            scheduled_date=data.scheduled_date,
            scheduled_start_time=data.scheduled_start_time,
            scheduled_end_time=data.scheduled_end_time,
            estimated_duration_hours=data.estimated_duration_hours,
            project_id=data.project_id,
            task_id=data.task_id,
            ticket_id=data.ticket_id,
            asset_id=data.asset_id,
            assigned_technician_id=data.assigned_technician_id,
            assigned_team_id=data.assigned_team_id,
            zone_id=data.zone_id,
            customer_contact_name=data.customer_contact_name,
            customer_contact_phone=data.customer_contact_phone,
            customer_contact_email=data.customer_contact_email,
            is_billable=data.is_billable,
            billable_amount=data.billable_amount,
            created_by=self.principal.email if self.principal else None,
        )

        self.db.add(order)
        self.db.flush()

        # Add items
        for item_data in data.items:
            self._add_item(order.id, item_data)

        # Add checklist items
        for idx, checklist_data in enumerate(data.checklist):
            checklist_data.idx = idx
            self._add_checklist_item(order.id, checklist_data)

        # Record status history
        self._record_status_change(order.id, None, ServiceOrderStatus.DRAFT)

        return order

    def update_order(
        self, order_id: int, data: ServiceOrderUpdateData
    ) -> ServiceOrder:
        """Update a service order."""
        order = self.get_order(order_id)

        # Can only update draft/scheduled orders
        if order.status not in [
            ServiceOrderStatus.DRAFT,
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.RESCHEDULED,
        ]:
            raise ValidationError(
                f"Cannot update order in status: {order.status.value}"
            )

        # Update fields
        if data.title is not None:
            order.title = data.title
        if data.description is not None:
            order.description = data.description
        if data.order_type is not None:
            try:
                order.order_type = ServiceOrderType(data.order_type)
            except ValueError:
                raise ValidationError(f"Invalid order type: {data.order_type}")
        if data.priority is not None:
            try:
                order.priority = ServiceOrderPriority(data.priority)
            except ValueError:
                pass
        if data.service_address is not None:
            order.service_address = data.service_address
        if data.city is not None:
            order.city = data.city
        if data.state is not None:
            order.state = data.state
        if data.postal_code is not None:
            order.postal_code = data.postal_code
        if data.latitude is not None:
            order.latitude = data.latitude
        if data.longitude is not None:
            order.longitude = data.longitude
        if data.scheduled_date is not None:
            order.scheduled_date = data.scheduled_date
        if data.scheduled_start_time is not None:
            order.scheduled_start_time = data.scheduled_start_time
        if data.scheduled_end_time is not None:
            order.scheduled_end_time = data.scheduled_end_time
        if data.estimated_duration_hours is not None:
            order.estimated_duration_hours = data.estimated_duration_hours
        if data.assigned_technician_id is not None:
            order.assigned_technician_id = data.assigned_technician_id
        if data.assigned_team_id is not None:
            order.assigned_team_id = data.assigned_team_id
        if data.zone_id is not None:
            order.zone_id = data.zone_id
        if data.customer_contact_name is not None:
            order.customer_contact_name = data.customer_contact_name
        if data.customer_contact_phone is not None:
            order.customer_contact_phone = data.customer_contact_phone
        if data.customer_contact_email is not None:
            order.customer_contact_email = data.customer_contact_email
        if data.is_billable is not None:
            order.is_billable = data.is_billable
        if data.billable_amount is not None:
            order.billable_amount = data.billable_amount

        order.updated_at = datetime.now(timezone.utc)

        return order

    def delete_order(self, order_id: int) -> None:
        """Delete (soft delete) a draft service order."""
        order = self.get_order(order_id)

        if order.status != ServiceOrderStatus.DRAFT:
            raise ValidationError("Can only delete draft orders")

        # Hard delete for drafts
        self.db.delete(order)

    # -------------------------------------------------------------------------
    # Workflow Operations
    # -------------------------------------------------------------------------

    def schedule(self, order_id: int) -> ServiceOrder:
        """Schedule a draft order."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.SCHEDULED)

        if not order.scheduled_date:
            raise ValidationError("Scheduled date is required")

        order.status = ServiceOrderStatus.SCHEDULED
        self._record_status_change(
            order_id,
            ServiceOrderStatus.DRAFT,
            ServiceOrderStatus.SCHEDULED,
        )

        return order

    def dispatch(self, order_id: int, data: DispatchData) -> ServiceOrder:
        """Dispatch an order to a technician."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.DISPATCHED)

        # Validate technician
        technician = (
            self.db.query(Employee).filter(Employee.id == data.technician_id).first()
        )
        if not technician:
            raise ValidationError(f"Technician {data.technician_id} not found")

        order.assigned_technician_id = data.technician_id
        if data.team_id:
            order.assigned_team_id = data.team_id
        if data.scheduled_date:
            order.scheduled_date = data.scheduled_date
        if data.scheduled_start_time:
            order.scheduled_start_time = data.scheduled_start_time

        order.status = ServiceOrderStatus.DISPATCHED
        self._record_status_change(
            order_id,
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            notes=data.notes,
        )

        return order

    def start_travel(
        self,
        order_id: int,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ServiceOrder:
        """Mark technician as en route."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.EN_ROUTE)

        order.status = ServiceOrderStatus.EN_ROUTE
        order.travel_start_time = datetime.now(timezone.utc)

        self._record_status_change(
            order_id,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.EN_ROUTE,
            latitude=latitude,
            longitude=longitude,
        )

        # Create travel time entry
        if order.assigned_technician_id:
            self._add_time_entry(
                order.id,
                TimeEntryData(
                    entry_type="travel",
                    start_time=datetime.now(timezone.utc),
                    employee_id=order.assigned_technician_id,
                    is_billable=True,
                    start_latitude=latitude,
                    start_longitude=longitude,
                ),
            )

        return order

    def arrive_on_site(
        self,
        order_id: int,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ServiceOrder:
        """Mark technician arrived on site."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.ON_SITE)

        order.status = ServiceOrderStatus.ON_SITE
        order.arrival_time = datetime.now(timezone.utc)

        self._record_status_change(
            order_id,
            ServiceOrderStatus.EN_ROUTE,
            ServiceOrderStatus.ON_SITE,
            latitude=latitude,
            longitude=longitude,
        )

        # Close travel time entry
        self._close_active_time_entry(order_id, "travel", latitude, longitude)

        return order

    def start_work(
        self,
        order_id: int,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ServiceOrder:
        """Start work on site."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.IN_PROGRESS)

        order.status = ServiceOrderStatus.IN_PROGRESS
        order.actual_start_time = datetime.now(timezone.utc)

        self._record_status_change(
            order_id,
            ServiceOrderStatus.ON_SITE,
            ServiceOrderStatus.IN_PROGRESS,
            latitude=latitude,
            longitude=longitude,
        )

        # Create work time entry
        if order.assigned_technician_id:
            self._add_time_entry(
                order.id,
                TimeEntryData(
                    entry_type="work",
                    start_time=datetime.now(timezone.utc),
                    employee_id=order.assigned_technician_id,
                    is_billable=True,
                    start_latitude=latitude,
                    start_longitude=longitude,
                ),
            )

        return order

    def complete(
        self,
        order_id: int,
        data: CompletionData,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ServiceOrder:
        """Complete a service order."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.COMPLETED)

        # Update completion data
        order.work_performed = data.work_performed
        order.resolution_notes = data.resolution_notes
        order.actual_end_time = data.actual_end_time or datetime.now(timezone.utc)

        # Customer signature
        if data.customer_signature:
            order.customer_signature = data.customer_signature
            order.customer_signature_name = data.customer_signature_name
            order.customer_signed_at = datetime.now(timezone.utc)

        if data.customer_rating:
            order.customer_rating = data.customer_rating
        if data.customer_feedback:
            order.customer_feedback = data.customer_feedback

        # Add final items used
        for item_data in data.items_used:
            self._add_item(order_id, item_data)

        # Close active work time entry
        self._close_active_time_entry(order_id, "work", latitude, longitude)

        # Calculate costs
        self._calculate_costs(order)

        order.status = ServiceOrderStatus.COMPLETED
        self._record_status_change(
            order_id,
            ServiceOrderStatus.IN_PROGRESS,
            ServiceOrderStatus.COMPLETED,
            notes=data.resolution_notes,
            latitude=latitude,
            longitude=longitude,
        )

        return order

    def cancel(
        self, order_id: int, reason: str, by_customer: bool = False
    ) -> ServiceOrder:
        """Cancel a service order."""
        order = self.get_order(order_id)

        if order.status in [
            ServiceOrderStatus.COMPLETED,
            ServiceOrderStatus.CANCELLED,
        ]:
            raise ValidationError(
                f"Cannot cancel order in status: {order.status.value}"
            )

        old_status = order.status
        order.status = ServiceOrderStatus.CANCELLED

        self._record_status_change(
            order_id,
            old_status,
            ServiceOrderStatus.CANCELLED,
            notes=f"Cancelled{' by customer' if by_customer else ''}: {reason}",
        )

        # Close any active time entries
        self._close_all_time_entries(order_id)

        return order

    def reschedule(self, order_id: int, data: RescheduleData) -> ServiceOrder:
        """Reschedule a service order."""
        order = self.get_order(order_id)

        if order.status not in [
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.FAILED,
        ]:
            raise ValidationError(
                f"Cannot reschedule order in status: {order.status.value}"
            )

        old_status = order.status
        order.scheduled_date = data.new_date
        if data.new_start_time:
            order.scheduled_start_time = data.new_start_time
        if data.new_end_time:
            order.scheduled_end_time = data.new_end_time

        order.status = ServiceOrderStatus.RESCHEDULED

        self._record_status_change(
            order_id,
            old_status,
            ServiceOrderStatus.RESCHEDULED,
            notes=f"Rescheduled to {data.new_date}: {data.reason}",
        )

        return order

    def mark_pending_parts(
        self, order_id: int, notes: str
    ) -> ServiceOrder:
        """Mark order as pending parts."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.PENDING_PARTS)

        old_status = order.status
        order.status = ServiceOrderStatus.PENDING_PARTS

        self._record_status_change(
            order_id,
            old_status,
            ServiceOrderStatus.PENDING_PARTS,
            notes=notes,
        )

        return order

    def resume_from_pending(self, order_id: int) -> ServiceOrder:
        """Resume work after parts received."""
        order = self.get_order(order_id)
        self._validate_transition(order.status, ServiceOrderStatus.IN_PROGRESS)

        order.status = ServiceOrderStatus.IN_PROGRESS

        self._record_status_change(
            order_id,
            ServiceOrderStatus.PENDING_PARTS,
            ServiceOrderStatus.IN_PROGRESS,
            notes="Parts received, resuming work",
        )

        return order

    # -------------------------------------------------------------------------
    # Items & Time Entries
    # -------------------------------------------------------------------------

    def add_item(
        self, order_id: int, data: ServiceOrderItemData
    ) -> ServiceOrderItem:
        """Add an item to a service order."""
        order = self.get_order(order_id)
        return self._add_item(order_id, data)

    def add_time_entry(
        self, order_id: int, data: TimeEntryData
    ) -> ServiceTimeEntry:
        """Add a time entry to a service order."""
        order = self.get_order(order_id)
        return self._add_time_entry(order_id, data)

    def complete_checklist_item(
        self,
        order_id: int,
        checklist_id: int,
        notes: Optional[str] = None,
        measurement_value: Optional[str] = None,
        photo_id: Optional[int] = None,
    ) -> ServiceChecklist:
        """Complete a checklist item."""
        checklist = (
            self.db.query(ServiceChecklist)
            .filter(
                ServiceChecklist.id == checklist_id,
                ServiceChecklist.service_order_id == order_id,
            )
            .first()
        )
        if not checklist:
            raise NotFoundError(f"Checklist item {checklist_id} not found")

        checklist.is_completed = True
        checklist.completed_at = datetime.now(timezone.utc)
        checklist.completed_by = self.principal.email if self.principal else None
        checklist.notes = notes
        checklist.measurement_value = measurement_value
        if photo_id:
            checklist.photo_id = photo_id

        return checklist

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(
        self, filters: Optional[ServiceOrderFilters] = None
    ) -> ServiceOrderStats:
        """Get service order statistics."""
        if filters is None:
            filters = ServiceOrderFilters()

        base_query = self.db.query(ServiceOrder)

        # Apply entity filters
        if filters.customer_account_id:
            base_query = base_query.filter(
                ServiceOrder.customer_account_id == filters.customer_account_id
            )
        if filters.technician_id:
            base_query = base_query.filter(
                ServiceOrder.assigned_technician_id == filters.technician_id
            )
        if filters.team_id:
            base_query = base_query.filter(
                ServiceOrder.assigned_team_id == filters.team_id
            )

        # Count by status
        by_status = {}
        for status in ServiceOrderStatus:
            count = base_query.filter(ServiceOrder.status == status).count()
            by_status[status.value] = count

        # Count by type
        by_type = {}
        for order_type in ServiceOrderType:
            count = base_query.filter(ServiceOrder.order_type == order_type).count()
            by_type[order_type.value] = count

        # Count by priority
        by_priority = {}
        for priority in ServiceOrderPriority:
            count = base_query.filter(ServiceOrder.priority == priority).count()
            by_priority[priority.value] = count

        # Completion counts
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        completed_today = (
            base_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                func.date(ServiceOrder.actual_end_time) == today,
            ).count()
        )

        completed_this_week = (
            base_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                func.date(ServiceOrder.actual_end_time) >= week_start,
            ).count()
        )

        completed_this_month = (
            base_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                func.date(ServiceOrder.actual_end_time) >= month_start,
            ).count()
        )

        # Overdue count
        overdue_count = (
            base_query.filter(
                ServiceOrder.status.notin_([
                    ServiceOrderStatus.COMPLETED,
                    ServiceOrderStatus.CANCELLED,
                ]),
                ServiceOrder.scheduled_date < today,
            ).count()
        )

        # Financial totals
        billable_orders = base_query.filter(ServiceOrder.is_billable == True).all()
        total_billable = sum(o.billable_amount or Decimal("0") for o in billable_orders)

        billed_orders = (
            base_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.is_billable == True,
            ).all()
        )
        total_billed = sum(o.total_cost or Decimal("0") for o in billed_orders)

        # Time totals
        time_entries = self.db.query(ServiceTimeEntry).all()
        total_labor = sum(
            t.duration_hours or Decimal("0")
            for t in time_entries
            if t.entry_type == TimeEntryType.WORK
        )
        total_travel = sum(
            t.duration_hours or Decimal("0")
            for t in time_entries
            if t.entry_type == TimeEntryType.TRAVEL
        )

        return ServiceOrderStats(
            total=base_query.count(),
            by_status=by_status,
            by_type=by_type,
            by_priority=by_priority,
            completed_today=completed_today,
            completed_this_week=completed_this_week,
            completed_this_month=completed_this_month,
            overdue_count=overdue_count,
            total_billable=total_billable,
            total_billed=total_billed,
            unbilled_amount=total_billable - total_billed,
            total_labor_hours=total_labor,
            total_travel_hours=total_travel,
        )

    def get_technician_workload(
        self, technician_id: int
    ) -> TechnicianWorkload:
        """Get workload summary for a technician."""
        technician = (
            self.db.query(Employee).filter(Employee.id == technician_id).first()
        )
        if not technician:
            raise NotFoundError(f"Technician {technician_id} not found")

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        base_query = self.db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == technician_id
        )

        # Counts
        total_assigned = base_query.count()
        scheduled_today = (
            base_query.filter(
                ServiceOrder.scheduled_date == today,
                ServiceOrder.status.notin_([
                    ServiceOrderStatus.COMPLETED,
                    ServiceOrderStatus.CANCELLED,
                ]),
            ).count()
        )
        scheduled_this_week = (
            base_query.filter(
                ServiceOrder.scheduled_date >= week_start,
                ServiceOrder.scheduled_date <= week_end,
                ServiceOrder.status.notin_([
                    ServiceOrderStatus.COMPLETED,
                    ServiceOrderStatus.CANCELLED,
                ]),
            ).count()
        )
        in_progress = (
            base_query.filter(
                ServiceOrder.status.in_([
                    ServiceOrderStatus.EN_ROUTE,
                    ServiceOrderStatus.ON_SITE,
                    ServiceOrderStatus.IN_PROGRESS,
                ])
            ).count()
        )
        completed_this_week = (
            base_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                func.date(ServiceOrder.actual_end_time) >= week_start,
            ).count()
        )

        # Time entries this week
        time_entries = (
            self.db.query(ServiceTimeEntry)
            .filter(
                ServiceTimeEntry.employee_id == technician_id,
                func.date(ServiceTimeEntry.start_time) >= week_start,
            )
            .all()
        )

        total_hours = sum(t.duration_hours or Decimal("0") for t in time_entries)
        billable_hours = sum(
            t.duration_hours or Decimal("0") for t in time_entries if t.is_billable
        )

        # Assume 40 hour work week
        utilization = (total_hours / 40 * 100) if total_hours > 0 else Decimal("0")

        # Average customer rating
        rated_orders = (
            base_query.filter(
                ServiceOrder.customer_rating.isnot(None)
            ).all()
        )
        avg_rating = None
        if rated_orders:
            avg_rating = Decimal(
                sum(o.customer_rating for o in rated_orders) / len(rated_orders)
            )

        return TechnicianWorkload(
            technician_id=technician_id,
            technician_name=technician.full_name or f"Tech-{technician_id}",
            total_assigned=total_assigned,
            scheduled_today=scheduled_today,
            scheduled_this_week=scheduled_this_week,
            in_progress=in_progress,
            completed_this_week=completed_this_week,
            total_hours_this_week=total_hours,
            billable_hours_this_week=billable_hours,
            utilization_percent=utilization,
            avg_customer_rating=avg_rating,
        )

    def count_active_orders_for_technician(self, technician_id: int) -> int:
        """Count active orders assigned to a technician."""
        return (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.assigned_technician_id == technician_id,
                ServiceOrder.status.in_([
                    ServiceOrderStatus.SCHEDULED,
                    ServiceOrderStatus.DISPATCHED,
                    ServiceOrderStatus.EN_ROUTE,
                    ServiceOrderStatus.ON_SITE,
                    ServiceOrderStatus.IN_PROGRESS,
                ]),
            )
            .count()
        )

    def count_completed_orders_for_technician(self, technician_id: int) -> int:
        """Count completed orders assigned to a technician."""
        return (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.assigned_technician_id == technician_id,
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
            )
            .count()
        )

    def list_active_orders_for_team(
        self,
        team_id: int,
        limit: int = 10,
    ) -> List[ServiceOrder]:
        """List active orders assigned to a team."""
        return (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.assigned_team_id == team_id,
                ServiceOrder.status.in_([
                    ServiceOrderStatus.SCHEDULED,
                    ServiceOrderStatus.DISPATCHED,
                    ServiceOrderStatus.EN_ROUTE,
                    ServiceOrderStatus.ON_SITE,
                    ServiceOrderStatus.IN_PROGRESS,
                ]),
            )
            .order_by(ServiceOrder.scheduled_date)
            .limit(limit)
            .all()
        )

    def list_recent_orders_for_technician(
        self,
        technician_id: int,
        limit: int = 10,
    ) -> List[ServiceOrder]:
        """List recent orders for a technician."""
        return (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.assigned_technician_id == technician_id)
            .order_by(ServiceOrder.scheduled_date.desc())
            .limit(limit)
            .all()
        )

    def list_active_orders_for_technician(
        self,
        technician_id: int,
        limit: int = 10,
    ) -> List[ServiceOrder]:
        """List active orders for a technician."""
        return (
            self.db.query(ServiceOrder)
            .filter(
                ServiceOrder.assigned_technician_id == technician_id,
                ServiceOrder.status.in_([
                    ServiceOrderStatus.SCHEDULED,
                    ServiceOrderStatus.DISPATCHED,
                    ServiceOrderStatus.EN_ROUTE,
                    ServiceOrderStatus.ON_SITE,
                    ServiceOrderStatus.IN_PROGRESS,
                    ServiceOrderStatus.PENDING_PARTS,
                ]),
            )
            .order_by(ServiceOrder.scheduled_date)
            .limit(limit)
            .all()
        )

    def calculate_costs(self, order_id: int) -> ServiceCostBreakdown:
        """Calculate cost breakdown for a service order."""
        order = self.get_order(order_id)
        return self._calculate_costs(order)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _generate_order_number(self) -> str:
        """Generate a unique order number."""
        today = date.today()
        prefix = f"SO-{today.strftime('%Y%m%d')}"

        count = (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.order_number.like(f"{prefix}%"))
            .count()
        )

        return f"{prefix}-{count + 1:04d}"

    def _validate_transition(
        self, current: ServiceOrderStatus, target: ServiceOrderStatus
    ) -> None:
        """Validate status transition is allowed."""
        allowed = STATUS_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ValidationError(
                f"Cannot transition from {current.value} to {target.value}"
            )

    def _record_status_change(
        self,
        order_id: int,
        from_status: Optional[ServiceOrderStatus],
        to_status: ServiceOrderStatus,
        notes: Optional[str] = None,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ServiceOrderStatusHistory:
        """Record a status change in history."""
        history = ServiceOrderStatusHistory(
            service_order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            notes=notes,
            latitude=latitude,
            longitude=longitude,
            changed_by=self.principal.email if self.principal else None,
        )
        self.db.add(history)
        return history

    def _add_item(
        self, order_id: int, data: ServiceOrderItemData
    ) -> ServiceOrderItem:
        """Add an item to a service order."""
        total_cost = data.quantity * data.unit_cost

        item = ServiceOrderItem(
            service_order_id=order_id,
            stock_item_id=data.stock_item_id,
            item_code=data.item_code,
            item_name=data.item_name,
            quantity=data.quantity,
            unit=data.unit,
            unit_cost=data.unit_cost,
            total_cost=total_cost,
            serial_numbers=data.serial_numbers,
            added_by=self.principal.email if self.principal else None,
        )
        self.db.add(item)
        return item

    def _add_checklist_item(
        self, order_id: int, data: ChecklistItemData
    ) -> ServiceChecklist:
        """Add a checklist item."""
        item = ServiceChecklist(
            service_order_id=order_id,
            template_item_id=data.template_item_id,
            item_text=data.item_text,
            is_required=data.is_required,
            idx=data.idx,
            measurement_unit=data.measurement_unit,
        )
        self.db.add(item)
        return item

    def _add_time_entry(
        self, order_id: int, data: TimeEntryData
    ) -> ServiceTimeEntry:
        """Add a time entry."""
        try:
            entry_type = TimeEntryType(data.entry_type)
        except ValueError:
            entry_type = TimeEntryType.WORK

        entry = ServiceTimeEntry(
            service_order_id=order_id,
            employee_id=data.employee_id,
            entry_type=entry_type,
            start_time=data.start_time,
            end_time=data.end_time,
            notes=data.notes,
            is_billable=data.is_billable,
            start_latitude=data.start_latitude,
            start_longitude=data.start_longitude,
            end_latitude=data.end_latitude,
            end_longitude=data.end_longitude,
        )

        if data.end_time and data.start_time:
            delta = data.end_time - data.start_time
            entry.duration_hours = Decimal(str(delta.total_seconds() / 3600))

        self.db.add(entry)
        return entry

    def _close_active_time_entry(
        self,
        order_id: int,
        entry_type: str,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> Optional[ServiceTimeEntry]:
        """Close the most recent active time entry of given type."""
        try:
            type_enum = TimeEntryType(entry_type)
        except ValueError:
            return None

        entry = (
            self.db.query(ServiceTimeEntry)
            .filter(
                ServiceTimeEntry.service_order_id == order_id,
                ServiceTimeEntry.entry_type == type_enum,
                ServiceTimeEntry.end_time.is_(None),
            )
            .order_by(ServiceTimeEntry.start_time.desc())
            .first()
        )

        if entry:
            entry.end_time = datetime.now(timezone.utc)
            entry.end_latitude = latitude
            entry.end_longitude = longitude
            delta = entry.end_time - entry.start_time
            entry.duration_hours = Decimal(str(delta.total_seconds() / 3600))

        return entry

    def _close_all_time_entries(self, order_id: int) -> None:
        """Close all open time entries for an order."""
        open_entries = (
            self.db.query(ServiceTimeEntry)
            .filter(
                ServiceTimeEntry.service_order_id == order_id,
                ServiceTimeEntry.end_time.is_(None),
            )
            .all()
        )

        now = datetime.now(timezone.utc)
        for entry in open_entries:
            entry.end_time = now
            delta = entry.end_time - entry.start_time
            entry.duration_hours = Decimal(str(delta.total_seconds() / 3600))

    def _calculate_costs(self, order: ServiceOrder) -> ServiceCostBreakdown:
        """Calculate cost breakdown for an order using configurable rates."""
        # Get billing configuration
        config_service = FieldServiceBillingConfigService(self.db, self.principal)
        config = config_service.get_config()

        # Check for fixed rate by service type
        fixed_rate = config_service.get_service_type_rate(order.order_type.value)

        # Get time entries
        time_entries = (
            self.db.query(ServiceTimeEntry)
            .filter(ServiceTimeEntry.service_order_id == order.id)
            .all()
        )

        # Calculate hours by type
        labor_hours = Decimal("0")
        travel_hours = Decimal("0")
        for entry in time_entries:
            hours = entry.duration_hours or Decimal("0")
            if entry.entry_type == TimeEntryType.WORK:
                labor_hours += hours
            elif entry.entry_type == TimeEntryType.TRAVEL:
                travel_hours += hours

        # Round and apply minimum hours
        labor_hours = config_service.round_labor_hours(labor_hours)
        labor_hours = config_service.apply_minimum_hours(labor_hours)

        # Determine labor rate with multipliers
        is_emergency = order.priority.value == "emergency" if order.priority else False
        is_weekend = False
        is_overtime = False

        if order.actual_start_time:
            is_weekend = order.actual_start_time.weekday() >= 5
            is_overtime = config_service.is_overtime_hour(
                order.actual_start_time.hour
            )

        labor_rate = config_service.get_labor_rate(
            technician_level="standard",  # Could be enhanced to check technician skills
            is_overtime=is_overtime,
            is_weekend=is_weekend,
            is_emergency=is_emergency,
        )

        # Calculate labor cost (use fixed rate if available)
        if fixed_rate:
            labor_cost = fixed_rate
        else:
            labor_cost = labor_hours * labor_rate

        # Calculate travel cost
        travel_cost = config_service.get_travel_charge(hours=travel_hours)
        travel_rate = config.travel_rate_hourly

        # Get items and apply markup
        items = (
            self.db.query(ServiceOrderItem)
            .filter(ServiceOrderItem.service_order_id == order.id)
            .all()
        )
        base_parts_cost = sum(i.total_cost or Decimal("0") for i in items)
        parts_cost = config_service.apply_parts_markup(base_parts_cost)

        # Add callout fee if applicable
        callout_fee = Decimal("0")
        subtotal_before_callout = labor_cost + travel_cost + parts_cost

        if not config_service.should_waive_callout_fee(subtotal_before_callout):
            callout_fee = config.callout_fee

        # Calculate subtotal
        subtotal = subtotal_before_callout + callout_fee

        # Apply minimum service charge
        if subtotal < config.minimum_service_charge:
            subtotal = config.minimum_service_charge

        # Calculate tax
        tax_rate = config.tax_rate
        if config.tax_inclusive:
            # Extract tax from inclusive price
            tax_amount = subtotal - (subtotal / (1 + tax_rate / 100))
            subtotal = subtotal - tax_amount
        else:
            tax_amount = subtotal * (tax_rate / 100)

        total = subtotal + tax_amount

        # Update order
        order.labor_cost = labor_cost
        order.travel_cost = travel_cost
        order.parts_cost = parts_cost
        order.total_cost = total

        # Build line items
        line_items = []

        if callout_fee > 0:
            line_items.append({
                "description": "Callout Fee",
                "quantity": 1,
                "rate": float(callout_fee),
                "amount": float(callout_fee),
            })

        if fixed_rate:
            line_items.append({
                "description": f"{order.order_type.value.title()} Service",
                "quantity": 1,
                "rate": float(fixed_rate),
                "amount": float(labor_cost),
            })
        elif labor_hours > 0:
            rate_desc = f"{labor_rate}/hr"
            if is_overtime or is_weekend or is_emergency:
                modifiers = []
                if is_emergency:
                    modifiers.append("emergency")
                if is_weekend:
                    modifiers.append("weekend")
                if is_overtime:
                    modifiers.append("overtime")
                rate_desc = f"{labor_rate}/hr ({', '.join(modifiers)})"

            line_items.append({
                "description": f"Labor ({labor_hours}h @ {rate_desc})",
                "quantity": float(labor_hours),
                "rate": float(labor_rate),
                "amount": float(labor_cost),
            })

        if travel_cost > 0:
            line_items.append({
                "description": f"Travel ({travel_hours}h @ {travel_rate}/hr)",
                "quantity": float(travel_hours),
                "rate": float(travel_rate),
                "amount": float(travel_cost),
            })

        for item in items:
            line_items.append({
                "description": f"{item.item_name} x{item.quantity}",
                "quantity": float(item.quantity),
                "rate": float(item.unit_cost),
                "amount": float(item.total_cost or 0),
            })

        if config.parts_markup_enabled and base_parts_cost > 0:
            markup_amount = parts_cost - base_parts_cost
            if markup_amount > 0:
                line_items.append({
                    "description": f"Parts handling ({config.parts_markup_percent}%)",
                    "quantity": 1,
                    "rate": float(markup_amount),
                    "amount": float(markup_amount),
                })

        return ServiceCostBreakdown(
            labor_cost=labor_cost,
            labor_hours=labor_hours,
            labor_rate=labor_rate,
            parts_cost=parts_cost,
            parts_count=len(items),
            travel_cost=travel_cost,
            travel_hours=travel_hours,
            travel_rate=travel_rate,
            other_costs=callout_fee,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            line_items=line_items,
        )
