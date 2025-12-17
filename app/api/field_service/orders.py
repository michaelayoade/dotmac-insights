"""
Service Orders API

CRUD operations and lifecycle management for field service orders.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid
import os
import shutil
from pathlib import Path

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.field_service import (
    ServiceOrder,
    ServiceOrderType,
    ServiceOrderStatus,
    ServiceOrderPriority,
    ServiceOrderStatusHistory,
    ServiceChecklist,
    ServicePhoto,
    ServiceTimeEntry,
    ServiceOrderItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
    FieldTeam,
    TimeEntryType,
    PhotoType,
)
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.project import Project
from app.models.task import Task
from app.models.ticket import Ticket
from app.services.customer_notifications import get_notification_service

router = APIRouter()


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class ServiceOrderCreate(BaseModel):
    """Schema for creating a service order."""
    order_type: ServiceOrderType
    priority: Optional[ServiceOrderPriority] = ServiceOrderPriority.MEDIUM
    customer_id: int
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    ticket_id: Optional[int] = None
    assigned_technician_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    zone_id: Optional[int] = None

    # Location
    service_address: str
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    # Scheduling
    scheduled_date: date
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    estimated_duration_hours: Optional[Decimal] = Decimal("1")

    # Details
    title: str
    description: Optional[str] = None

    # Customer contact
    customer_contact_name: Optional[str] = None
    customer_contact_phone: Optional[str] = None
    customer_contact_email: Optional[str] = None

    # Costing
    is_billable: bool = True

    # Apply checklist template
    checklist_template_id: Optional[int] = None


class ServiceOrderUpdate(BaseModel):
    """Schema for updating a service order."""
    order_type: Optional[ServiceOrderType] = None
    priority: Optional[ServiceOrderPriority] = None
    status: Optional[ServiceOrderStatus] = None
    assigned_technician_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    zone_id: Optional[int] = None

    # Location
    service_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    # Scheduling
    scheduled_date: Optional[date] = None
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    estimated_duration_hours: Optional[Decimal] = None

    # Details
    title: Optional[str] = None
    description: Optional[str] = None
    work_performed: Optional[str] = None
    resolution_notes: Optional[str] = None

    # Customer contact
    customer_contact_name: Optional[str] = None
    customer_contact_phone: Optional[str] = None
    customer_contact_email: Optional[str] = None

    # Costing
    labor_cost: Optional[Decimal] = None
    parts_cost: Optional[Decimal] = None
    travel_cost: Optional[Decimal] = None
    billable_amount: Optional[Decimal] = None
    is_billable: Optional[bool] = None


class StatusChangeRequest(BaseModel):
    """Schema for status change operations."""
    notes: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None


class DispatchRequest(BaseModel):
    """Schema for dispatching a service order."""
    technician_id: int
    team_id: Optional[int] = None
    notes: Optional[str] = None
    notify_customer: bool = True


class RescheduleRequest(BaseModel):
    """Schema for rescheduling a service order."""
    scheduled_date: date
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    reason: str
    notify_customer: bool = True


class ChecklistItemUpdate(BaseModel):
    """Schema for updating a checklist item."""
    is_completed: bool
    notes: Optional[str] = None
    measurement_value: Optional[str] = None


class TimeEntryCreate(BaseModel):
    """Schema for creating a time entry."""
    entry_type: TimeEntryType = TimeEntryType.WORK
    start_time: datetime
    end_time: Optional[datetime] = None
    notes: Optional[str] = None
    is_billable: bool = True
    start_latitude: Optional[Decimal] = None
    start_longitude: Optional[Decimal] = None
    end_latitude: Optional[Decimal] = None
    end_longitude: Optional[Decimal] = None


class ItemUsedCreate(BaseModel):
    """Schema for adding an inventory item."""
    stock_item_id: Optional[int] = None
    item_code: Optional[str] = None
    item_name: str
    quantity: Decimal
    unit: str = "pcs"
    unit_cost: Decimal = Decimal("0")
    serial_numbers: Optional[List[str]] = None


class SignatureCapture(BaseModel):
    """Schema for capturing customer signature."""
    signature_data: str  # Base64 encoded
    signer_name: str
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: Optional[str] = None


class BulkRescheduleRequest(BaseModel):
    """Schema for bulk rescheduling orders."""
    order_ids: List[int]
    scheduled_date: date
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    reason: str
    notify_customers: bool = True


class BulkCancelRequest(BaseModel):
    """Schema for bulk cancelling orders."""
    order_ids: List[int]
    reason: str
    notify_customers: bool = True


class BulkDeleteRequest(BaseModel):
    """Schema for bulk deleting (cancelling) orders."""
    order_ids: List[int]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_order_number() -> str:
    """Generate unique order number."""
    now = datetime.utcnow()
    return f"SO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def record_status_change(
    db: Session,
    order: ServiceOrder,
    new_status: ServiceOrderStatus,
    changed_by: Optional[str] = None,
    notes: Optional[str] = None,
    latitude: Optional[Decimal] = None,
    longitude: Optional[Decimal] = None,
):
    """Record a status change in history."""
    history = ServiceOrderStatusHistory(
        service_order_id=order.id,
        from_status=order.status,
        to_status=new_status,
        changed_by=changed_by,
        notes=notes,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(history)
    order.status = new_status


def serialize_order(order: ServiceOrder, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a service order to dict."""
    result = {
        "id": order.id,
        "order_number": order.order_number,
        "order_type": order.order_type.value,
        "status": order.status.value,
        "priority": order.priority.value,
        "customer_id": order.customer_id,
        "customer_name": order.customer.name if order.customer else None,
        "project_id": order.project_id,
        "task_id": order.task_id,
        "ticket_id": order.ticket_id,
        "assigned_technician_id": order.assigned_technician_id,
        "technician_name": order.technician.employee_name if order.technician else None,
        "assigned_team_id": order.assigned_team_id,
        "team_name": order.team.name if order.team else None,
        "zone_id": order.zone_id,
        "service_address": order.service_address,
        "city": order.city,
        "state": order.state,
        "latitude": float(order.latitude) if order.latitude else None,
        "longitude": float(order.longitude) if order.longitude else None,
        "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
        "scheduled_start_time": order.scheduled_start_time.isoformat() if order.scheduled_start_time else None,
        "scheduled_end_time": order.scheduled_end_time.isoformat() if order.scheduled_end_time else None,
        "estimated_duration_hours": float(order.estimated_duration_hours),
        "title": order.title,
        "description": order.description,
        "is_overdue": order.is_overdue,
        "is_billable": order.is_billable,
        "total_cost": float(order.total_cost),
        "billable_amount": float(order.billable_amount),
        "customer_rating": order.customer_rating,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }

    if include_details:
        result.update({
            "work_performed": order.work_performed,
            "resolution_notes": order.resolution_notes,
            "customer_contact_name": order.customer_contact_name,
            "customer_contact_phone": order.customer_contact_phone,
            "customer_contact_email": order.customer_contact_email,
            "actual_start_time": order.actual_start_time.isoformat() if order.actual_start_time else None,
            "actual_end_time": order.actual_end_time.isoformat() if order.actual_end_time else None,
            "travel_start_time": order.travel_start_time.isoformat() if order.travel_start_time else None,
            "arrival_time": order.arrival_time.isoformat() if order.arrival_time else None,
            "actual_duration_hours": float(order.actual_duration_hours) if order.actual_duration_hours else None,
            "labor_cost": float(order.labor_cost),
            "parts_cost": float(order.parts_cost),
            "travel_cost": float(order.travel_cost),
            "has_signature": bool(order.customer_signature),
            "customer_signed_at": order.customer_signed_at.isoformat() if order.customer_signed_at else None,
            "customer_signature_name": order.customer_signature_name,
            "customer_feedback": order.customer_feedback,
            "checklist_items": [
                {
                    "id": item.id,
                    "idx": item.idx,
                    "item_text": item.item_text,
                    "is_required": item.is_required,
                    "is_completed": item.is_completed,
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                    "notes": item.notes,
                    "measurement_value": item.measurement_value,
                }
                for item in sorted(order.checklist_items, key=lambda x: x.idx)
            ],
            "photos": [
                {
                    "id": photo.id,
                    "photo_type": photo.photo_type.value,
                    "file_path": photo.file_path,
                    "caption": photo.caption,
                    "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
                }
                for photo in order.photos
            ],
            "time_entries": [
                {
                    "id": entry.id,
                    "entry_type": entry.entry_type.value,
                    "start_time": entry.start_time.isoformat() if entry.start_time else None,
                    "end_time": entry.end_time.isoformat() if entry.end_time else None,
                    "duration_hours": float(entry.duration_hours) if entry.duration_hours else None,
                    "is_billable": entry.is_billable,
                    "notes": entry.notes,
                }
                for entry in order.time_entries
            ],
            "items_used": [
                {
                    "id": item.id,
                    "item_name": item.item_name,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                    "unit_cost": float(item.unit_cost),
                    "total_cost": float(item.total_cost),
                    "serial_numbers": item.serial_numbers,
                }
                for item in order.items_used
            ],
            "status_history": [
                {
                    "from_status": h.from_status.value if h.from_status else None,
                    "to_status": h.to_status.value,
                    "changed_by": h.changed_by,
                    "notes": h.notes,
                    "changed_at": h.changed_at.isoformat() if h.changed_at else None,
                }
                for h in sorted(order.status_history, key=lambda x: x.changed_at, reverse=True)
            ],
        })

    return result


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("field-service-dashboard", ttl=CACHE_TTL["short"])
async def get_dashboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get field service dashboard metrics."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Orders by status
    by_status = db.query(
        ServiceOrder.status,
        func.count(ServiceOrder.id).label("count")
    ).group_by(ServiceOrder.status).all()

    status_counts = {s.status.value: s.count for s in by_status}
    total_orders = sum(status_counts.values())

    # Today's orders
    today_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date == today
    ).scalar() or 0

    today_completed = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date == today,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED
    ).scalar() or 0

    # Overdue orders
    overdue = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date < today,
        ServiceOrder.status.notin_([
            ServiceOrderStatus.COMPLETED,
            ServiceOrderStatus.CANCELLED
        ])
    ).scalar() or 0

    # Orders by type
    by_type = db.query(
        ServiceOrder.order_type,
        func.count(ServiceOrder.id).label("count")
    ).group_by(ServiceOrder.order_type).all()

    # This week completion rate
    week_total = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= week_start,
        ServiceOrder.scheduled_date <= today
    ).scalar() or 0

    week_completed = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= week_start,
        ServiceOrder.scheduled_date <= today,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED
    ).scalar() or 0

    completion_rate = round(week_completed / week_total * 100, 1) if week_total > 0 else 0

    # Average customer rating (this month)
    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.created_at >= month_start,
        ServiceOrder.customer_rating.isnot(None)
    ).scalar() or 0

    # Unassigned orders
    unassigned = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED]),
        ServiceOrder.assigned_technician_id.is_(None)
    ).scalar() or 0

    return {
        "summary": {
            "total_orders": total_orders,
            "today_orders": today_orders,
            "today_completed": today_completed,
            "overdue": overdue,
            "unassigned": unassigned,
            "week_completion_rate": completion_rate,
            "avg_customer_rating": round(float(avg_rating), 1),
        },
        "by_status": status_counts,
        "by_type": {t.order_type.value: t.count for t in by_type},
        "today": {
            "scheduled": today_orders,
            "completed": today_completed,
            "pending": today_orders - today_completed,
        },
    }


# =============================================================================
# SERVICE ORDERS CRUD
# =============================================================================

@router.get("/orders", dependencies=[Depends(Require("explorer:read"))])
async def list_orders(
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    priority: Optional[str] = None,
    customer_id: Optional[int] = None,
    technician_id: Optional[int] = None,
    team_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    scheduled_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    overdue_only: bool = False,
    unassigned_only: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List service orders with filtering."""
    query = db.query(ServiceOrder)

    if status:
        try:
            query = query.filter(ServiceOrder.status == ServiceOrderStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    if order_type:
        try:
            query = query.filter(ServiceOrder.order_type == ServiceOrderType(order_type))
        except ValueError:
            raise HTTPException(400, f"Invalid order type: {order_type}")

    if priority:
        try:
            query = query.filter(ServiceOrder.priority == ServiceOrderPriority(priority))
        except ValueError:
            raise HTTPException(400, f"Invalid priority: {priority}")

    if customer_id:
        query = query.filter(ServiceOrder.customer_id == customer_id)

    if technician_id:
        query = query.filter(ServiceOrder.assigned_technician_id == technician_id)

    if team_id:
        query = query.filter(ServiceOrder.assigned_team_id == team_id)

    if zone_id:
        query = query.filter(ServiceOrder.zone_id == zone_id)

    if scheduled_date:
        query = query.filter(ServiceOrder.scheduled_date == date.fromisoformat(scheduled_date))

    if date_from:
        query = query.filter(ServiceOrder.scheduled_date >= date.fromisoformat(date_from))

    if date_to:
        query = query.filter(ServiceOrder.scheduled_date <= date.fromisoformat(date_to))

    if overdue_only:
        query = query.filter(
            ServiceOrder.scheduled_date < date.today(),
            ServiceOrder.status.notin_([ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED])
        )

    if unassigned_only:
        query = query.filter(ServiceOrder.assigned_technician_id.is_(None))

    if search:
        # Use PostgreSQL full-text search when available
        # Falls back to ILIKE for simple queries or when search_vector is not populated
        search_clean = search.strip()
        if len(search_clean) >= 2:
            # Try full-text search first (faster for large datasets)
            try:
                from sqlalchemy import text
                # Use plainto_tsquery for safe handling of user input
                # (automatically escapes special characters, no injection risk)
                query = query.filter(
                    text("search_vector @@ plainto_tsquery('english', :search)")
                ).params(search=search_clean)
            except Exception:
                # Fallback to ILIKE if full-text search fails
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        ServiceOrder.order_number.ilike(search_term),
                        ServiceOrder.title.ilike(search_term),
                        ServiceOrder.service_address.ilike(search_term),
                        ServiceOrder.customer_contact_name.ilike(search_term),
                    )
                )
        else:
            # For very short queries, use simple ILIKE
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    ServiceOrder.order_number.ilike(search_term),
                    ServiceOrder.title.ilike(search_term),
                )
            )

    total = query.count()
    orders = query.order_by(
        ServiceOrder.scheduled_date.desc(),
        ServiceOrder.created_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_order(o) for o in orders],
    }


@router.get("/orders/{order_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_order(order_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get detailed service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    return serialize_order(order, include_details=True)


@router.post("/orders", dependencies=[Depends(Require("field-service:write"))])
async def create_order(
    payload: ServiceOrderCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new service order with transaction safety."""
    # Validate customer
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(400, "Customer not found")

    # Validate linked entities
    if payload.project_id:
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project:
            raise HTTPException(400, "Project not found")

    if payload.task_id:
        task = db.query(Task).filter(Task.id == payload.task_id).first()
        if not task:
            raise HTTPException(400, "Task not found")

    if payload.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
        if not ticket:
            raise HTTPException(400, "Ticket not found")

    try:
        # Create order
        order = ServiceOrder(
            order_number=generate_order_number(),
            order_type=payload.order_type,
            status=ServiceOrderStatus.DRAFT,
            priority=payload.priority or ServiceOrderPriority.MEDIUM,
            customer_id=payload.customer_id,
            project_id=payload.project_id,
            task_id=payload.task_id,
            ticket_id=payload.ticket_id,
            assigned_technician_id=payload.assigned_technician_id,
            assigned_team_id=payload.assigned_team_id,
            zone_id=payload.zone_id,
            service_address=payload.service_address,
            city=payload.city,
            state=payload.state,
            postal_code=payload.postal_code,
            latitude=payload.latitude,
            longitude=payload.longitude,
            scheduled_date=payload.scheduled_date,
            scheduled_start_time=payload.scheduled_start_time,
            scheduled_end_time=payload.scheduled_end_time,
            estimated_duration_hours=payload.estimated_duration_hours or Decimal("1"),
            title=payload.title,
            description=payload.description,
            customer_contact_name=payload.customer_contact_name or customer.name,
            customer_contact_phone=payload.customer_contact_phone or customer.phone,
            customer_contact_email=payload.customer_contact_email or customer.email,
            is_billable=payload.is_billable,
        )

        db.add(order)
        db.flush()

        # Record initial status
        record_status_change(db, order, ServiceOrderStatus.DRAFT, notes="Order created")

        # Apply checklist template if specified
        if payload.checklist_template_id:
            template = db.query(ChecklistTemplate).filter(
                ChecklistTemplate.id == payload.checklist_template_id
            ).first()
            if template:
                for item in sorted(template.items, key=lambda x: x.idx):
                    checklist_item = ServiceChecklist(
                        service_order_id=order.id,
                        template_item_id=item.id,
                        idx=item.idx,
                        item_text=item.item_text,
                        is_required=item.is_required,
                        measurement_unit=item.measurement_unit,
                    )
                    db.add(checklist_item)
        else:
            # Apply default template for order type
            default_template = db.query(ChecklistTemplate).filter(
                ChecklistTemplate.order_type == payload.order_type,
                ChecklistTemplate.is_default == True,
                ChecklistTemplate.is_active == True,
            ).first()
            if default_template:
                for item in sorted(default_template.items, key=lambda x: x.idx):
                    checklist_item = ServiceChecklist(
                        service_order_id=order.id,
                        template_item_id=item.id,
                        idx=item.idx,
                        item_text=item.item_text,
                        is_required=item.is_required,
                        measurement_unit=item.measurement_unit,
                    )
                    db.add(checklist_item)

        db.commit()
        db.refresh(order)

        return serialize_order(order, include_details=True)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create order: {str(e)}")


@router.patch("/orders/{order_id}", dependencies=[Depends(Require("field-service:write"))])
async def update_order(
    order_id: int,
    payload: ServiceOrderUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    # Track status change
    old_status = order.status

    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(order, key, value)

    # Record status change if changed
    if payload.status and payload.status != old_status:
        record_status_change(db, order, payload.status, notes="Status updated manually")

    # Recalculate total cost
    order.total_cost = order.labor_cost + order.parts_cost + order.travel_cost

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


@router.delete("/orders/{order_id}", dependencies=[Depends(Require("field-service:write"))])
async def delete_order(order_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete (cancel) a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status == ServiceOrderStatus.COMPLETED:
        raise HTTPException(400, "Cannot delete completed orders")

    record_status_change(db, order, ServiceOrderStatus.CANCELLED, notes="Order deleted")
    db.commit()

    return {"message": "Order cancelled", "id": order_id}


# =============================================================================
# LIFECYCLE OPERATIONS
# =============================================================================

@router.post("/orders/{order_id}/schedule", dependencies=[Depends(Require("field-service:dispatch"))])
async def schedule_order(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Schedule a draft order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status != ServiceOrderStatus.DRAFT:
        raise HTTPException(400, f"Cannot schedule order in {order.status.value} status")

    record_status_change(
        db, order, ServiceOrderStatus.SCHEDULED,
        notes=request.notes,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # Notify customer
    notification_service = get_notification_service(db)
    notification_service.notify_service_scheduled(order)

    order.customer_notified = True
    order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


def check_schedule_overlap(
    db: Session,
    technician_id: int,
    scheduled_date: date,
    start_time: Optional[time],
    end_time: Optional[time],
    duration_hours: Decimal,
    exclude_order_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if there's a schedule overlap for a technician.
    Returns conflicting order info if overlap exists, None otherwise.
    """
    # Get all orders for this technician on the same date
    query = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_technician_id == technician_id,
        ServiceOrder.scheduled_date == scheduled_date,
        ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED, ServiceOrderStatus.COMPLETED])
    )

    if exclude_order_id:
        query = query.filter(ServiceOrder.id != exclude_order_id)

    existing_orders = query.all()

    if not existing_orders:
        return None

    # If no specific times, check total hours for the day
    if not start_time:
        total_hours = sum(float(o.estimated_duration_hours) for o in existing_orders)
        if total_hours + float(duration_hours) > 8:  # 8 hour max workday
            return {
                "type": "workload_exceeded",
                "message": f"Technician already has {total_hours:.1f} hours scheduled. Adding {float(duration_hours):.1f} hours would exceed 8-hour workday.",
                "scheduled_hours": total_hours,
            }
        return None

    # Calculate end time if not provided
    if not end_time:
        from datetime import datetime as dt
        start_dt = dt.combine(scheduled_date, start_time)
        end_dt = start_dt + timedelta(hours=float(duration_hours))
        end_time = end_dt.time()

    # Check for time slot overlaps
    for existing in existing_orders:
        if not existing.scheduled_start_time:
            continue

        existing_start = existing.scheduled_start_time
        existing_end = existing.scheduled_end_time

        if not existing_end:
            from datetime import datetime as dt
            existing_start_dt = dt.combine(scheduled_date, existing_start)
            existing_end_dt = existing_start_dt + timedelta(hours=float(existing.estimated_duration_hours))
            existing_end = existing_end_dt.time()

        # Check for overlap: new_start < existing_end AND new_end > existing_start
        if start_time < existing_end and end_time > existing_start:
            return {
                "type": "time_overlap",
                "message": f"Schedule conflict with order {existing.order_number} ({existing_start.strftime('%H:%M')}-{existing_end.strftime('%H:%M')})",
                "conflicting_order": {
                    "id": existing.id,
                    "order_number": existing.order_number,
                    "title": existing.title,
                    "start_time": existing_start.isoformat(),
                    "end_time": existing_end.isoformat(),
                },
            }

    return None


@router.post("/orders/{order_id}/dispatch", dependencies=[Depends(Require("field-service:dispatch"))])
async def dispatch_order(
    order_id: int,
    request: DispatchRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Dispatch order to a technician."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status not in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED]:
        raise HTTPException(400, f"Cannot dispatch order in {order.status.value} status")

    # Validate technician
    technician = db.query(Employee).filter(Employee.id == request.technician_id).first()
    if not technician:
        raise HTTPException(400, "Technician not found")

    # Check for schedule overlap
    overlap = check_schedule_overlap(
        db=db,
        technician_id=request.technician_id,
        scheduled_date=order.scheduled_date,
        start_time=order.scheduled_start_time,
        end_time=order.scheduled_end_time,
        duration_hours=order.estimated_duration_hours,
        exclude_order_id=order_id,
    )

    if overlap:
        raise HTTPException(
            409,
            {
                "error": "schedule_conflict",
                "detail": overlap["message"],
                "conflict": overlap,
            }
        )

    order.assigned_technician_id = request.technician_id
    if request.team_id:
        order.assigned_team_id = request.team_id

    record_status_change(
        db, order, ServiceOrderStatus.DISPATCHED,
        notes=request.notes or f"Dispatched to {technician.employee_name}",
    )

    # Notify customer
    if request.notify_customer:
        notification_service = get_notification_service(db)
        notification_service.notify_technician_assigned(order)
        order.customer_notified = True
        order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    # Broadcast WebSocket event
    try:
        from app.api.field_service.websocket import broadcast_order_event, FieldServiceEvent
        import asyncio

        order_data = serialize_order(order, include_details=False)
        order_data["technician_name"] = technician.employee_name

        asyncio.create_task(
            broadcast_order_event(
                event_type=FieldServiceEvent.ORDER_DISPATCHED,
                order_data=order_data,
                team_id=order.assigned_team_id,
                technician_id=order.assigned_technician_id,
            )
        )
    except Exception:
        pass  # Don't fail dispatch if WebSocket broadcast fails

    return serialize_order(order, include_details=True)


@router.post("/orders/{order_id}/en-route", dependencies=[Depends(Require("field-service:mobile"))])
async def mark_en_route(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark technician as en route."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status != ServiceOrderStatus.DISPATCHED:
        raise HTTPException(400, f"Cannot start travel from {order.status.value} status")

    order.travel_start_time = datetime.utcnow()
    record_status_change(
        db, order, ServiceOrderStatus.EN_ROUTE,
        notes=request.notes,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # Notify customer
    notification_service = get_notification_service(db)
    notification_service.notify_technician_en_route(order, eta="30 minutes")
    order.customer_notified = True
    order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


@router.post("/orders/{order_id}/arrive", dependencies=[Depends(Require("field-service:mobile"))])
async def mark_arrived(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark technician as arrived on site."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status != ServiceOrderStatus.EN_ROUTE:
        raise HTTPException(400, f"Cannot arrive from {order.status.value} status")

    order.arrival_time = datetime.utcnow()
    record_status_change(
        db, order, ServiceOrderStatus.ON_SITE,
        notes=request.notes,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # Notify customer
    notification_service = get_notification_service(db)
    notification_service.notify_technician_arrived(order)
    order.customer_notified = True
    order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


@router.post("/orders/{order_id}/start", dependencies=[Depends(Require("field-service:mobile"))])
async def start_work(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Start work on the service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status not in [ServiceOrderStatus.ON_SITE, ServiceOrderStatus.DISPATCHED]:
        raise HTTPException(400, f"Cannot start work from {order.status.value} status")

    order.actual_start_time = datetime.utcnow()
    record_status_change(
        db, order, ServiceOrderStatus.IN_PROGRESS,
        notes=request.notes,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # Create initial time entry if technician assigned
    if order.assigned_technician_id:
        time_entry = ServiceTimeEntry(
            service_order_id=order.id,
            employee_id=order.assigned_technician_id,
            entry_type=TimeEntryType.WORK,
            start_time=datetime.utcnow(),
            is_billable=order.is_billable,
            start_latitude=request.latitude,
            start_longitude=request.longitude,
        )
        db.add(time_entry)

    # Notify customer
    notification_service = get_notification_service(db)
    notification_service.notify_service_started(order)
    order.customer_notified = True
    order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


@router.post("/orders/{order_id}/complete", dependencies=[Depends(Require("field-service:mobile"))])
async def complete_order(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Complete the service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status != ServiceOrderStatus.IN_PROGRESS:
        raise HTTPException(400, f"Cannot complete from {order.status.value} status")

    # Check required checklist items
    incomplete_required = [
        item for item in order.checklist_items
        if item.is_required and not item.is_completed
    ]
    if incomplete_required:
        raise HTTPException(
            400,
            f"Cannot complete: {len(incomplete_required)} required checklist items incomplete"
        )

    order.actual_end_time = datetime.utcnow()
    if request.notes:
        order.resolution_notes = request.notes

    record_status_change(
        db, order, ServiceOrderStatus.COMPLETED,
        notes=request.notes or "Service completed",
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # Close any open time entries
    for entry in order.time_entries:
        if entry.end_time is None:
            entry.end_time = datetime.utcnow()
            delta = entry.end_time - entry.start_time
            entry.duration_hours = Decimal(str(delta.total_seconds() / 3600))
            entry.end_latitude = request.latitude
            entry.end_longitude = request.longitude

    # Notify customer
    notification_service = get_notification_service(db)
    notification_service.notify_service_completed(order)
    order.customer_notified = True
    order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


@router.post("/orders/{order_id}/reschedule", dependencies=[Depends(Require("field-service:dispatch"))])
async def reschedule_order(
    order_id: int,
    request: RescheduleRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reschedule a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if order.status == ServiceOrderStatus.COMPLETED:
        raise HTTPException(400, "Cannot reschedule completed orders")

    order.scheduled_date = request.scheduled_date
    order.scheduled_start_time = request.scheduled_start_time
    order.scheduled_end_time = request.scheduled_end_time

    record_status_change(
        db, order, ServiceOrderStatus.RESCHEDULED,
        notes=request.reason,
    )

    # Set back to scheduled
    order.status = ServiceOrderStatus.SCHEDULED

    # Notify customer
    if request.notify_customer:
        notification_service = get_notification_service(db)
        notification_service.notify_service_rescheduled(order, request.reason)
        order.customer_notified = True
        order.last_notification_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return serialize_order(order, include_details=True)


# =============================================================================
# CHECKLIST OPERATIONS
# =============================================================================

@router.patch("/orders/{order_id}/checklist/{item_id}", dependencies=[Depends(Require("field-service:mobile"))])
async def update_checklist_item(
    order_id: int,
    item_id: int,
    update: ChecklistItemUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a checklist item."""
    item = db.query(ServiceChecklist).filter(
        ServiceChecklist.id == item_id,
        ServiceChecklist.service_order_id == order_id
    ).first()

    if not item:
        raise HTTPException(404, "Checklist item not found")

    item.is_completed = update.is_completed
    if update.is_completed:
        item.completed_at = datetime.utcnow()
    else:
        item.completed_at = None

    if update.notes is not None:
        item.notes = update.notes
    if update.measurement_value is not None:
        item.measurement_value = update.measurement_value

    db.commit()

    return {
        "id": item.id,
        "item_text": item.item_text,
        "is_completed": item.is_completed,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "notes": item.notes,
        "measurement_value": item.measurement_value,
    }


# =============================================================================
# TIME ENTRIES
# =============================================================================

@router.post("/orders/{order_id}/time-entries", dependencies=[Depends(Require("field-service:mobile"))])
async def add_time_entry(
    order_id: int,
    entry: TimeEntryCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a time entry to a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    if not order.assigned_technician_id:
        raise HTTPException(400, "No technician assigned to this order")

    # Calculate duration if end time provided
    duration_hours = None
    if entry.end_time:
        delta = entry.end_time - entry.start_time
        duration_hours = Decimal(str(delta.total_seconds() / 3600))

    time_entry = ServiceTimeEntry(
        service_order_id=order_id,
        employee_id=order.assigned_technician_id,
        entry_type=entry.entry_type,
        start_time=entry.start_time,
        end_time=entry.end_time,
        duration_hours=duration_hours,
        notes=entry.notes,
        is_billable=entry.is_billable,
        start_latitude=entry.start_latitude,
        start_longitude=entry.start_longitude,
        end_latitude=entry.end_latitude,
        end_longitude=entry.end_longitude,
    )

    db.add(time_entry)
    db.commit()

    return {
        "id": time_entry.id,
        "entry_type": time_entry.entry_type.value,
        "start_time": time_entry.start_time.isoformat(),
        "end_time": time_entry.end_time.isoformat() if time_entry.end_time else None,
        "duration_hours": float(time_entry.duration_hours) if time_entry.duration_hours else None,
    }


# =============================================================================
# INVENTORY ITEMS
# =============================================================================

@router.post("/orders/{order_id}/items", dependencies=[Depends(Require("field-service:mobile"))])
async def add_item_used(
    order_id: int,
    item: ItemUsedCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add an inventory item to a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    total_cost = item.quantity * item.unit_cost

    service_item = ServiceOrderItem(
        service_order_id=order_id,
        stock_item_id=item.stock_item_id,
        item_code=item.item_code,
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        unit_cost=item.unit_cost,
        total_cost=total_cost,
        serial_numbers=item.serial_numbers,
    )

    db.add(service_item)

    # Update order parts cost
    order.parts_cost += total_cost
    order.total_cost = order.labor_cost + order.parts_cost + order.travel_cost

    db.commit()

    return {
        "id": service_item.id,
        "item_name": service_item.item_name,
        "quantity": float(service_item.quantity),
        "total_cost": float(service_item.total_cost),
    }


# =============================================================================
# SIGNATURE CAPTURE
# =============================================================================

@router.post("/orders/{order_id}/signature", dependencies=[Depends(Require("field-service:mobile"))])
async def capture_signature(
    order_id: int,
    signature: SignatureCapture,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Capture customer signature."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    order.customer_signature = signature.signature_data
    order.customer_signature_name = signature.signer_name
    order.customer_signed_at = datetime.utcnow()

    if signature.rating:
        order.customer_rating = signature.rating
    if signature.feedback:
        order.customer_feedback = signature.feedback

    db.commit()

    return {
        "signed": True,
        "signer_name": order.customer_signature_name,
        "signed_at": order.customer_signed_at.isoformat(),
        "rating": order.customer_rating,
    }


# =============================================================================
# PHOTO UPLOADS
# =============================================================================

UPLOAD_DIR = Path("uploads/field-service/photos")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/orders/{order_id}/photos", dependencies=[Depends(Require("field-service:mobile"))])
async def upload_photo(
    order_id: int,
    file: UploadFile = File(...),
    photo_type: str = Form(default="issue"),
    caption: Optional[str] = Form(default=None),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload a photo for a service order."""
    order = db.query(ServiceOrder).filter(ServiceOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "Service order not found")

    # Validate file extension
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Validate photo type
    try:
        photo_type_enum = PhotoType(photo_type)
    except ValueError:
        valid_types = [t.value for t in PhotoType]
        raise HTTPException(400, f"Invalid photo type. Valid types: {', '.join(valid_types)}")

    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB")

    # Create upload directory
    order_dir = UPLOAD_DIR / str(order_id)
    order_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{photo_type}_{timestamp}_{unique_id}{ext}"
    file_path = order_dir / new_filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Create database record
    photo = ServicePhoto(
        service_order_id=order_id,
        photo_type=photo_type_enum,
        file_path=str(file_path),
        file_name=new_filename,
        file_size=len(contents),
        mime_type=file.content_type,
        caption=caption,
        latitude=Decimal(str(latitude)) if latitude else None,
        longitude=Decimal(str(longitude)) if longitude else None,
        captured_at=datetime.utcnow(),
        uploaded_at=datetime.utcnow(),
    )

    db.add(photo)
    db.commit()
    db.refresh(photo)

    return {
        "id": photo.id,
        "file_name": photo.file_name,
        "file_path": f"/api/field-service/photos/{photo.id}",
        "photo_type": photo.photo_type.value,
        "caption": photo.caption,
        "file_size": photo.file_size,
        "uploaded_at": photo.uploaded_at.isoformat(),
    }


@router.get("/photos/{photo_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_photo(photo_id: int, db: Session = Depends(get_db)):
    """Get photo file."""
    from fastapi.responses import FileResponse

    photo = db.query(ServicePhoto).filter(ServicePhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(404, "Photo not found")

    if not os.path.exists(photo.file_path):
        raise HTTPException(404, "Photo file not found")

    return FileResponse(
        photo.file_path,
        media_type=photo.mime_type or "image/jpeg",
        filename=photo.file_name,
    )


@router.delete("/orders/{order_id}/photos/{photo_id}", dependencies=[Depends(Require("field-service:mobile"))])
async def delete_photo(
    order_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a photo from a service order."""
    photo = db.query(ServicePhoto).filter(
        ServicePhoto.id == photo_id,
        ServicePhoto.service_order_id == order_id
    ).first()

    if not photo:
        raise HTTPException(404, "Photo not found")

    # Delete file
    if os.path.exists(photo.file_path):
        os.remove(photo.file_path)

    # Delete record
    db.delete(photo)
    db.commit()

    return {"deleted": True, "id": photo_id}


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.post("/orders/bulk/reschedule", dependencies=[Depends(Require("field-service:dispatch"))])
async def bulk_reschedule_orders(
    request: BulkRescheduleRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk reschedule multiple service orders."""
    orders = db.query(ServiceOrder).filter(ServiceOrder.id.in_(request.order_ids)).all()

    if not orders:
        raise HTTPException(400, "No valid orders found")

    notification_service = get_notification_service(db)
    rescheduled = []
    errors = []

    for order in orders:
        try:
            # Check if order can be rescheduled
            if order.status == ServiceOrderStatus.COMPLETED:
                errors.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "error": "Cannot reschedule completed orders"
                })
                continue

            # Update schedule
            order.scheduled_date = request.scheduled_date
            order.scheduled_start_time = request.scheduled_start_time
            order.scheduled_end_time = request.scheduled_end_time

            # Record status change
            record_status_change(
                db, order, ServiceOrderStatus.RESCHEDULED,
                notes=request.reason,
            )

            # Set back to scheduled
            order.status = ServiceOrderStatus.SCHEDULED

            # Notify customer if requested
            if request.notify_customers:
                try:
                    notification_service.notify_service_rescheduled(order, request.reason)
                    order.customer_notified = True
                    order.last_notification_at = datetime.utcnow()
                except Exception as e:
                    errors.append({
                        "order_id": order.id,
                        "order_number": order.order_number,
                        "error": f"Rescheduled but notification failed: {str(e)}"
                    })

            rescheduled.append({
                "order_id": order.id,
                "order_number": order.order_number,
            })

        except Exception as e:
            errors.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "error": str(e)
            })

    db.commit()

    return {
        "rescheduled": rescheduled,
        "rescheduled_count": len(rescheduled),
        "new_date": request.scheduled_date.isoformat(),
        "errors": errors,
    }


@router.post("/orders/bulk/cancel", dependencies=[Depends(Require("field-service:dispatch"))])
async def bulk_cancel_orders(
    request: BulkCancelRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk cancel multiple service orders."""
    orders = db.query(ServiceOrder).filter(ServiceOrder.id.in_(request.order_ids)).all()

    if not orders:
        raise HTTPException(400, "No valid orders found")

    notification_service = get_notification_service(db)
    cancelled = []
    errors = []

    for order in orders:
        try:
            # Check if order can be cancelled
            if order.status in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]:
                errors.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "error": f"Cannot cancel order in {order.status.value} status"
                })
                continue

            # Record status change
            record_status_change(
                db, order, ServiceOrderStatus.CANCELLED,
                notes=request.reason,
            )

            # Notify customer if requested
            if request.notify_customers:
                try:
                    notification_service.notify_service_cancelled(order, request.reason)
                    order.customer_notified = True
                    order.last_notification_at = datetime.utcnow()
                except Exception as e:
                    errors.append({
                        "order_id": order.id,
                        "order_number": order.order_number,
                        "error": f"Cancelled but notification failed: {str(e)}"
                    })

            cancelled.append({
                "order_id": order.id,
                "order_number": order.order_number,
            })

        except Exception as e:
            errors.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "error": str(e)
            })

    db.commit()

    return {
        "cancelled": cancelled,
        "cancelled_count": len(cancelled),
        "reason": request.reason,
        "errors": errors,
    }


@router.post("/orders/bulk/delete", dependencies=[Depends(Require("field-service:admin"))])
async def bulk_delete_orders(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk delete (permanently) multiple service orders. Admin only."""
    orders = db.query(ServiceOrder).filter(ServiceOrder.id.in_(request.order_ids)).all()

    if not orders:
        raise HTTPException(400, "No valid orders found")

    deleted = []
    errors = []

    for order in orders:
        try:
            # Only allow deleting draft or cancelled orders
            if order.status not in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.CANCELLED]:
                errors.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "error": f"Can only delete draft or cancelled orders. Current status: {order.status.value}"
                })
                continue

            order_info = {
                "order_id": order.id,
                "order_number": order.order_number,
            }

            # Delete associated photos files
            for photo in order.photos:
                if os.path.exists(photo.file_path):
                    os.remove(photo.file_path)

            # Delete order (cascade will handle related records)
            db.delete(order)
            deleted.append(order_info)

        except Exception as e:
            errors.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "error": str(e)
            })

    db.commit()

    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "errors": errors,
    }
