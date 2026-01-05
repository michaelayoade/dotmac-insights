"""
Service Orders API

CRUD operations and lifecycle management for field service orders.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time, timezone
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid
import os
from pathlib import Path

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models.field_service import (
    ServiceOrder,
    ServiceOrderType,
    ServiceOrderStatus,
    ServiceOrderPriority,
    ServiceChecklist,
    ServicePhoto,
    PhotoType,
    TimeEntryType,
)
from app.services.field_service import (
    ServiceOrderService,
    ServiceOrderFilters,
    ServiceOrderCreateData,
    ServiceOrderUpdateData,
    ServiceOrderItemData,
    TimeEntryData,
    DispatchData,
    CompletionData,
    RescheduleData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError
from app.services.customer_notifications import get_notification_service

router = APIRouter()


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class ServiceOrderCreate(BaseModel):
    """Schema for creating a service order."""
    order_type: ServiceOrderType
    priority: Optional[ServiceOrderPriority] = ServiceOrderPriority.MEDIUM
    customer_account_id: int
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

def serialize_order(order: ServiceOrder, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a service order to dict."""
    result = {
        "id": order.id,
        "order_number": order.order_number,
        "order_type": order.order_type.value,
        "status": order.status.value,
        "priority": order.priority.value,
        "customer_account_id": order.customer_account_id,
        "customer_name": order.customer.name if order.customer else None,
        "project_id": order.project_id,
        "task_id": order.task_id,
        "ticket_id": order.ticket_id,
        "assigned_technician_id": order.assigned_technician_id,
        "technician_name": order.technician.name if order.technician else None,
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
async def get_dashboard(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get field service dashboard metrics."""
    service = ServiceOrderService(db, principal)
    stats = service.get_stats()

    # Calculate completion rate from stats
    total_this_week = stats.completed_this_week + stats.overdue_count
    completion_rate = (
        round(stats.completed_this_week / total_this_week * 100, 1)
        if total_this_week > 0
        else 0
    )

    return {
        "summary": {
            "total_orders": stats.total,
            "today_orders": stats.completed_today,  # Orders completed today
            "today_completed": stats.completed_today,
            "overdue": stats.overdue_count,
            "unassigned": stats.by_status.get("draft", 0) + stats.by_status.get("scheduled", 0),
            "week_completion_rate": completion_rate,
            "avg_customer_rating": 0,  # Would need separate query
        },
        "by_status": stats.by_status,
        "by_type": stats.by_type,
        "today": {
            "scheduled": stats.completed_today,
            "completed": stats.completed_today,
            "pending": 0,
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
    customer_account_id: Optional[int] = None,
    technician_id: Optional[int] = None,
    team_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    scheduled_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List service orders with filtering."""
    service = ServiceOrderService(db, principal)

    # Build filters
    filters = ServiceOrderFilters(
        search=search,
        status=status,
        order_type=order_type,
        priority=priority,
        customer_account_id=customer_account_id,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
        scheduled_date_from=date.fromisoformat(date_from) if date_from else None,
        scheduled_date_to=date.fromisoformat(date_to) if date_to else None,
    )

    # Handle single date filter
    if scheduled_date:
        d = date.fromisoformat(scheduled_date)
        filters.scheduled_date_from = d
        filters.scheduled_date_to = d

    pagination = PaginationParams(limit=limit, offset=offset)

    result = service.list_orders(filters, pagination)

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "data": [serialize_order(o) for o in result.items],
    }


@router.get("/orders/{order_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get detailed service order."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.get_order(order_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))

    return serialize_order(order, include_details=True)


@router.post("/orders", dependencies=[Depends(Require("field-service:write"))])
async def create_order(
    payload: ServiceOrderCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new service order."""
    service = ServiceOrderService(db, principal)

    # Build create data from payload
    data = ServiceOrderCreateData(
        customer_account_id=payload.customer_account_id,
        order_type=payload.order_type.value,
        title=payload.title,
        service_address=payload.service_address,
        scheduled_date=payload.scheduled_date,
        description=payload.description,
        priority=payload.priority.value if payload.priority else "medium",
        scheduled_start_time=payload.scheduled_start_time,
        scheduled_end_time=payload.scheduled_end_time,
        estimated_duration_hours=payload.estimated_duration_hours or Decimal("1"),
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        latitude=payload.latitude,
        longitude=payload.longitude,
        project_id=payload.project_id,
        task_id=payload.task_id,
        ticket_id=payload.ticket_id,
        assigned_technician_id=payload.assigned_technician_id,
        assigned_team_id=payload.assigned_team_id,
        zone_id=payload.zone_id,
        customer_contact_name=payload.customer_contact_name,
        customer_contact_phone=payload.customer_contact_phone,
        customer_contact_email=payload.customer_contact_email,
        is_billable=payload.is_billable,
    )

    try:
        order = service.create_order(data)
        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.patch("/orders/{order_id}", dependencies=[Depends(Require("field-service:write"))])
async def update_order(
    order_id: int,
    payload: ServiceOrderUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a service order."""
    service = ServiceOrderService(db, principal)

    # Build update data from payload
    update_dict = payload.model_dump(exclude_unset=True)
    data = ServiceOrderUpdateData(
        title=update_dict.get("title"),
        description=update_dict.get("description"),
        order_type=update_dict.get("order_type").value if update_dict.get("order_type") else None,
        priority=update_dict.get("priority").value if update_dict.get("priority") else None,
        service_address=update_dict.get("service_address"),
        city=update_dict.get("city"),
        state=update_dict.get("state"),
        postal_code=update_dict.get("postal_code"),
        latitude=update_dict.get("latitude"),
        longitude=update_dict.get("longitude"),
        scheduled_date=update_dict.get("scheduled_date"),
        scheduled_start_time=update_dict.get("scheduled_start_time"),
        scheduled_end_time=update_dict.get("scheduled_end_time"),
        estimated_duration_hours=update_dict.get("estimated_duration_hours"),
        assigned_technician_id=update_dict.get("assigned_technician_id"),
        assigned_team_id=update_dict.get("assigned_team_id"),
        zone_id=update_dict.get("zone_id"),
        customer_contact_name=update_dict.get("customer_contact_name"),
        customer_contact_phone=update_dict.get("customer_contact_phone"),
        customer_contact_email=update_dict.get("customer_contact_email"),
        is_billable=update_dict.get("is_billable"),
        billable_amount=update_dict.get("billable_amount"),
    )

    try:
        order = service.update_order(order_id, data)
        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.delete("/orders/{order_id}", dependencies=[Depends(Require("field-service:write"))])
async def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete (cancel) a service order."""
    service = ServiceOrderService(db, principal)

    try:
        service.cancel(order_id, "Order deleted")
        db.commit()
        return {"message": "Order cancelled", "id": order_id}
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


# =============================================================================
# LIFECYCLE OPERATIONS
# =============================================================================

@router.post("/orders/{order_id}/schedule", dependencies=[Depends(Require("field-service:dispatch"))])
async def schedule_order(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Schedule a draft order."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.schedule(order_id)

        # Notify customer
        notification_service = get_notification_service(db)
        notification_service.notify_service_scheduled(order)
        order.customer_notified = True
        order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/dispatch", dependencies=[Depends(Require("field-service:dispatch"))])
async def dispatch_order(
    order_id: int,
    request: DispatchRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Dispatch order to a technician."""
    service = ServiceOrderService(db, principal)

    # Build dispatch data
    data = DispatchData(
        technician_id=request.technician_id,
        team_id=request.team_id,
        notes=request.notes,
    )

    try:
        order = service.dispatch(order_id, data)

        # Notify customer
        if request.notify_customer:
            notification_service = get_notification_service(db)
            notification_service.notify_technician_assigned(order)
            order.customer_notified = True
            order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)

        # Broadcast WebSocket event
        try:
            from app.api.field_service.websocket import broadcast_order_event, FieldServiceEvent
            import asyncio

            order_data = serialize_order(order, include_details=False)

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
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/en-route", dependencies=[Depends(Require("field-service:mobile"))])
async def mark_en_route(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark technician as en route."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.start_travel(order_id, request.latitude, request.longitude)

        # Notify customer
        notification_service = get_notification_service(db)
        notification_service.notify_technician_en_route(order, eta="30 minutes")
        order.customer_notified = True
        order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/arrive", dependencies=[Depends(Require("field-service:mobile"))])
async def mark_arrived(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark technician as arrived on site."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.arrive_on_site(order_id, request.latitude, request.longitude)

        # Notify customer
        notification_service = get_notification_service(db)
        notification_service.notify_technician_arrived(order)
        order.customer_notified = True
        order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/start", dependencies=[Depends(Require("field-service:mobile"))])
async def start_work(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Start work on the service order."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.start_work(order_id, request.latitude, request.longitude)

        # Notify customer
        notification_service = get_notification_service(db)
        notification_service.notify_service_started(order)
        order.customer_notified = True
        order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/complete", dependencies=[Depends(Require("field-service:mobile"))])
async def complete_order(
    order_id: int,
    request: StatusChangeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Complete the service order."""
    service = ServiceOrderService(db, principal)

    # Build completion data
    data = CompletionData(
        work_performed=request.notes or "Service completed",
        resolution_notes=request.notes,
    )

    try:
        order = service.complete(order_id, data, request.latitude, request.longitude)

        # Notify customer
        notification_service = get_notification_service(db)
        notification_service.notify_service_completed(order)
        order.customer_notified = True
        order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/orders/{order_id}/reschedule", dependencies=[Depends(Require("field-service:dispatch"))])
async def reschedule_order(
    order_id: int,
    request: RescheduleRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reschedule a service order."""
    service = ServiceOrderService(db, principal)

    # Build reschedule data
    data = RescheduleData(
        new_date=request.scheduled_date,
        new_start_time=request.scheduled_start_time,
        new_end_time=request.scheduled_end_time,
        reason=request.reason,
        notify_customer=request.notify_customer,
    )

    try:
        order = service.reschedule(order_id, data)

        # Notify customer
        if request.notify_customer:
            notification_service = get_notification_service(db)
            notification_service.notify_service_rescheduled(order, request.reason)
            order.customer_notified = True
            order.last_notification_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return serialize_order(order, include_details=True)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))


# =============================================================================
# CHECKLIST OPERATIONS
# =============================================================================

@router.patch("/orders/{order_id}/checklist/{item_id}", dependencies=[Depends(Require("field-service:mobile"))])
async def update_checklist_item(
    order_id: int,
    item_id: int,
    update: ChecklistItemUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a checklist item."""
    service = ServiceOrderService(db, principal)

    try:
        if update.is_completed:
            item = service.complete_checklist_item(
                order_id,
                item_id,
                notes=update.notes,
                measurement_value=update.measurement_value,
            )
        else:
            # For uncomplete, get the item directly and update
            item = db.query(ServiceChecklist).filter(
                ServiceChecklist.id == item_id,
                ServiceChecklist.service_order_id == order_id
            ).first()
            if not item:
                raise HTTPException(404, "Checklist item not found")
            item.is_completed = False
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
    except NotFoundError as e:
        raise HTTPException(404, str(e))


# =============================================================================
# TIME ENTRIES
# =============================================================================

@router.post("/orders/{order_id}/time-entries", dependencies=[Depends(Require("field-service:mobile"))])
async def add_time_entry(
    order_id: int,
    entry: TimeEntryCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Add a time entry to a service order."""
    service = ServiceOrderService(db, principal)

    # Get order to get technician ID
    try:
        order = service.get_order(order_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))

    if not order.assigned_technician_id:
        raise HTTPException(400, "No technician assigned to this order")

    # Build time entry data
    data = TimeEntryData(
        entry_type=entry.entry_type.value,
        start_time=entry.start_time,
        end_time=entry.end_time,
        employee_id=order.assigned_technician_id,
        notes=entry.notes,
        is_billable=entry.is_billable,
        start_latitude=entry.start_latitude,
        start_longitude=entry.start_longitude,
        end_latitude=entry.end_latitude,
        end_longitude=entry.end_longitude,
    )

    time_entry = service.add_time_entry(order_id, data)
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Add an inventory item to a service order."""
    service = ServiceOrderService(db, principal)

    # Build item data
    data = ServiceOrderItemData(
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        unit_cost=item.unit_cost,
        item_code=item.item_code,
        stock_item_id=item.stock_item_id,
        serial_numbers=item.serial_numbers,
    )

    try:
        service_item = service.add_item(order_id, data)
        db.commit()

        return {
            "id": service_item.id,
            "item_name": service_item.item_name,
            "quantity": float(service_item.quantity),
            "total_cost": float(service_item.total_cost),
        }
    except NotFoundError as e:
        raise HTTPException(404, str(e))


# =============================================================================
# SIGNATURE CAPTURE
# =============================================================================

@router.post("/orders/{order_id}/signature", dependencies=[Depends(Require("field-service:mobile"))])
async def capture_signature(
    order_id: int,
    signature: SignatureCapture,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Capture customer signature."""
    service = ServiceOrderService(db, principal)

    try:
        order = service.get_order(order_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))

    order.customer_signature = signature.signature_data
    order.customer_signature_name = signature.signer_name
    order.customer_signed_at = datetime.now(timezone.utc)

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
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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
        captured_at=datetime.now(timezone.utc),
        uploaded_at=datetime.now(timezone.utc),
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reschedule multiple service orders."""
    service = ServiceOrderService(db, principal)
    notification_service = get_notification_service(db)
    rescheduled = []
    errors = []

    for order_id in request.order_ids:
        try:
            # Build reschedule data
            data = RescheduleData(
                new_date=request.scheduled_date,
                new_start_time=request.scheduled_start_time,
                new_end_time=request.scheduled_end_time,
                reason=request.reason,
                notify_customer=request.notify_customers,
            )

            order = service.reschedule(order_id, data)

            # Notify customer if requested
            if request.notify_customers:
                try:
                    notification_service.notify_service_rescheduled(order, request.reason)
                    order.customer_notified = True
                    order.last_notification_at = datetime.now(timezone.utc)
                except Exception as e:
                    errors.append({
                        "order_id": order_id,
                        "order_number": order.order_number,
                        "error": f"Rescheduled but notification failed: {str(e)}"
                    })

            rescheduled.append({
                "order_id": order.id,
                "order_number": order.order_number,
            })

        except NotFoundError:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": "Order not found"
            })
        except ValidationError as e:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": str(e)
            })
        except Exception as e:
            errors.append({
                "order_id": order_id,
                "order_number": None,
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk cancel multiple service orders."""
    service = ServiceOrderService(db, principal)
    notification_service = get_notification_service(db)
    cancelled = []
    errors = []

    for order_id in request.order_ids:
        try:
            order = service.cancel(order_id, request.reason)

            # Notify customer if requested
            if request.notify_customers:
                try:
                    notification_service.notify_service_cancelled(order, request.reason)
                    order.customer_notified = True
                    order.last_notification_at = datetime.now(timezone.utc)
                except Exception as e:
                    errors.append({
                        "order_id": order_id,
                        "order_number": order.order_number,
                        "error": f"Cancelled but notification failed: {str(e)}"
                    })

            cancelled.append({
                "order_id": order.id,
                "order_number": order.order_number,
            })

        except NotFoundError:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": "Order not found"
            })
        except ValidationError as e:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": str(e)
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk delete (permanently) multiple service orders. Admin only."""
    service = ServiceOrderService(db, principal)
    deleted = []
    errors = []

    for order_id in request.order_ids:
        try:
            order = service.get_order(order_id)

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

        except NotFoundError:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": "Order not found"
            })
        except Exception as e:
            errors.append({
                "order_id": order_id,
                "order_number": None,
                "error": str(e)
            })

    db.commit()

    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "errors": errors,
    }
