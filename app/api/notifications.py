"""Notification and webhook API endpoints."""
from __future__ import annotations

import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.models.notification import (
    WebhookConfig,
    WebhookDelivery,
    Notification,
    NotificationPreference,
    NotificationEventType,
    NotificationStatus,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============= PYDANTIC SCHEMAS =============

class WebhookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    url: str = Field(..., min_length=1)
    method: str = Field(default="POST", pattern="^(POST|PUT)$")
    auth_type: Optional[str] = Field(None, pattern="^(none|basic|bearer|api_key)$")
    auth_header: Optional[str] = None
    auth_value: Optional[str] = None  # Will be stored encrypted
    custom_headers: Optional[Dict[str, str]] = None
    event_types: List[str] = Field(default_factory=list)
    filters: Optional[Dict[str, Any]] = None
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=10, le=3600)
    company: Optional[str] = None


class WebhookUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = Field(None, pattern="^(POST|PUT)$")
    auth_type: Optional[str] = Field(None, pattern="^(none|basic|bearer|api_key)$")
    auth_header: Optional[str] = None
    auth_value: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None
    event_types: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=10, le=3600)


class NotificationPreferenceRequest(BaseModel):
    event_type: str
    email_enabled: bool = True
    in_app_enabled: bool = True
    sms_enabled: bool = False
    slack_enabled: bool = False
    threshold_amount: Optional[float] = None
    threshold_days: Optional[int] = None


class TestWebhookRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None


# ============= WEBHOOK ENDPOINTS =============

@router.get("/webhooks", dependencies=[Depends(Require("books:admin"))])
async def list_webhooks(
    include_inactive: bool = Query(False),
    company: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List webhook configurations."""
    query = db.query(WebhookConfig).filter(WebhookConfig.is_deleted == False)

    if not include_inactive:
        query = query.filter(WebhookConfig.is_active == True)

    if company:
        query = query.filter(WebhookConfig.company == company)

    total = query.count()
    webhooks = query.order_by(WebhookConfig.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "webhooks": [
            {
                "id": wh.id,
                "name": wh.name,
                "description": wh.description,
                "url": wh.url,
                "method": wh.method,
                "auth_type": wh.auth_type,
                "event_types": wh.event_types,
                "is_active": wh.is_active,
                "last_triggered_at": wh.last_triggered_at.isoformat() if wh.last_triggered_at else None,
                "success_count": wh.success_count,
                "failure_count": wh.failure_count,
                "company": wh.company,
            }
            for wh in webhooks
        ],
    }


@router.post("/webhooks", dependencies=[Depends(Require("books:admin"))])
async def create_webhook(
    request: WebhookCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new webhook configuration."""
    # Validate event types
    valid_events = {e.value for e in NotificationEventType}
    for event in request.event_types:
        if event not in valid_events:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")

    # Generate signing secret
    signing_secret = secrets.token_urlsafe(32)

    webhook = WebhookConfig(
        name=request.name,
        description=request.description,
        url=request.url,
        method=request.method,
        auth_type=request.auth_type,
        auth_header=request.auth_header,
        auth_value_encrypted=request.auth_value,  # TODO: Actually encrypt this
        custom_headers=request.custom_headers,
        event_types=request.event_types,
        filters=request.filters,
        max_retries=request.max_retries,
        retry_delay_seconds=request.retry_delay_seconds,
        signing_secret=signing_secret,
        company=request.company,
        created_by_id=principal.id,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return {
        "id": webhook.id,
        "name": webhook.name,
        "url": webhook.url,
        "signing_secret": signing_secret,  # Only returned on creation
        "event_types": webhook.event_types,
        "is_active": webhook.is_active,
    }


@router.get("/webhooks/{webhook_id}", dependencies=[Depends(Require("books:admin"))])
async def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get webhook configuration details."""
    webhook = db.query(WebhookConfig).filter(
        and_(WebhookConfig.id == webhook_id, WebhookConfig.is_deleted == False)
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {
        "id": webhook.id,
        "name": webhook.name,
        "description": webhook.description,
        "url": webhook.url,
        "method": webhook.method,
        "auth_type": webhook.auth_type,
        "auth_header": webhook.auth_header,
        "custom_headers": webhook.custom_headers,
        "event_types": webhook.event_types,
        "filters": webhook.filters,
        "is_active": webhook.is_active,
        "max_retries": webhook.max_retries,
        "retry_delay_seconds": webhook.retry_delay_seconds,
        "last_triggered_at": webhook.last_triggered_at.isoformat() if webhook.last_triggered_at else None,
        "success_count": webhook.success_count,
        "failure_count": webhook.failure_count,
        "company": webhook.company,
        "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
    }


@router.patch("/webhooks/{webhook_id}", dependencies=[Depends(Require("books:admin"))])
async def update_webhook(
    webhook_id: int,
    request: WebhookUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update webhook configuration."""
    webhook = db.query(WebhookConfig).filter(
        and_(WebhookConfig.id == webhook_id, WebhookConfig.is_deleted == False)
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if request.name is not None:
        webhook.name = request.name
    if request.description is not None:
        webhook.description = request.description
    if request.url is not None:
        webhook.url = request.url
    if request.method is not None:
        webhook.method = request.method
    if request.auth_type is not None:
        webhook.auth_type = request.auth_type
    if request.auth_header is not None:
        webhook.auth_header = request.auth_header
    if request.auth_value is not None:
        webhook.auth_value_encrypted = request.auth_value
    if request.custom_headers is not None:
        webhook.custom_headers = request.custom_headers
    if request.event_types is not None:
        valid_events = {e.value for e in NotificationEventType}
        for event in request.event_types:
            if event not in valid_events:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")
        webhook.event_types = request.event_types
    if request.filters is not None:
        webhook.filters = request.filters
    if request.is_active is not None:
        webhook.is_active = request.is_active
    if request.max_retries is not None:
        webhook.max_retries = request.max_retries
    if request.retry_delay_seconds is not None:
        webhook.retry_delay_seconds = request.retry_delay_seconds

    webhook.updated_at = datetime.utcnow()
    db.commit()

    return {
        "id": webhook.id,
        "name": webhook.name,
        "url": webhook.url,
        "is_active": webhook.is_active,
        "event_types": webhook.event_types,
    }


@router.delete("/webhooks/{webhook_id}", dependencies=[Depends(Require("books:admin"))])
async def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete (soft) a webhook configuration."""
    webhook = db.query(WebhookConfig).filter(
        and_(WebhookConfig.id == webhook_id, WebhookConfig.is_deleted == False)
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.is_deleted = True
    webhook.is_active = False
    db.commit()

    return {"status": "deleted", "webhook_id": webhook_id}


@router.post("/webhooks/{webhook_id}/test", dependencies=[Depends(Require("books:admin"))])
async def test_webhook(
    webhook_id: int,
    request: TestWebhookRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a test event to a webhook."""
    webhook = db.query(WebhookConfig).filter(
        and_(WebhookConfig.id == webhook_id, WebhookConfig.is_deleted == False)
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Create test payload
    test_payload = request.payload or {
        "test": True,
        "message": "This is a test webhook delivery",
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Queue delivery
    service = NotificationService(db)
    result = service.emit_event(
        event_type=NotificationEventType.CUSTOM,
        payload=test_payload,
        company=webhook.company,
    )

    return {
        "status": "queued",
        "event_id": result["event_id"],
        "webhooks_queued": result["webhooks_queued"],
    }


@router.get("/webhooks/{webhook_id}/deliveries", dependencies=[Depends(Require("books:admin"))])
async def list_webhook_deliveries(
    webhook_id: int,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List delivery attempts for a webhook."""
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    query = db.query(WebhookDelivery).filter(WebhookDelivery.webhook_id == webhook_id)

    if status:
        query = query.filter(WebhookDelivery.status == status)

    total = query.count()
    deliveries = query.order_by(desc(WebhookDelivery.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "deliveries": [
            {
                "id": d.id,
                "event_type": d.event_type,
                "event_id": d.event_id,
                "status": d.status.value if hasattr(d.status, 'value') else d.status,
                "attempt_count": d.attempt_count,
                "response_status_code": d.response_status_code,
                "response_time_ms": d.response_time_ms,
                "error_message": d.error_message[:200] if d.error_message else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in deliveries
        ],
    }


@router.post("/webhooks/{webhook_id}/deliveries/{delivery_id}/retry", dependencies=[Depends(Require("books:admin"))])
async def retry_webhook_delivery(
    webhook_id: int,
    delivery_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually retry a failed webhook delivery."""
    delivery = db.query(WebhookDelivery).filter(
        and_(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.webhook_id == webhook_id,
        )
    ).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    service = NotificationService(db)
    success = service.deliver_webhook(delivery_id)

    return {
        "delivery_id": delivery_id,
        "success": success,
        "status": delivery.status.value if hasattr(delivery.status, 'value') else delivery.status,
        "attempt_count": delivery.attempt_count,
    }


# ============= EVENT TYPES =============

@router.get("/event-types", dependencies=[Depends(Require("accounting:read"))])
async def list_event_types() -> Dict[str, Any]:
    """List all available notification event types."""
    return {
        "event_types": [
            {
                "value": e.value,
                "name": e.name,
                "category": _get_event_category(e),
            }
            for e in NotificationEventType
        ],
    }


def _get_event_category(event_type: NotificationEventType) -> str:
    """Get category for an event type."""
    categories = {
        "approval": ["APPROVAL_REQUESTED", "APPROVAL_APPROVED", "APPROVAL_REJECTED", "APPROVAL_ESCALATED"],
        "invoice": ["INVOICE_CREATED", "INVOICE_OVERDUE", "INVOICE_PAID", "INVOICE_WRITTEN_OFF"],
        "dunning": ["DUNNING_SENT", "DUNNING_ESCALATED"],
        "payment": ["PAYMENT_RECEIVED", "PAYMENT_FAILED"],
        "period": ["PERIOD_CLOSING", "PERIOD_CLOSED"],
        "tax": ["TAX_DUE_REMINDER", "TAX_OVERDUE"],
        "credit": ["CREDIT_LIMIT_WARNING", "CREDIT_HOLD_APPLIED"],
        "inventory": ["STOCK_LOW", "STOCK_REORDER"],
        "reconciliation": ["RECONCILIATION_COMPLETE", "RECONCILIATION_DISCREPANCY"],
    }
    for category, events in categories.items():
        if event_type.name in events:
            return category
    return "other"


# ============= USER NOTIFICATIONS =============

@router.get("/me", dependencies=[Depends(Require("accounting:read"))])
async def get_my_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get current user's notifications."""
    service = NotificationService(db)
    notifications = service.get_user_notifications(
        user_id=principal.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    unread_count = service.get_unread_count(principal.id)

    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.id,
                "event_type": n.event_type.value if hasattr(n.event_type, 'value') else n.event_type,
                "title": n.title,
                "message": n.message,
                "icon": n.icon,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "priority": n.priority,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
    }


@router.get("/me/unread-count", dependencies=[Depends(Require("accounting:read"))])
async def get_unread_count(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get count of unread notifications."""
    service = NotificationService(db)
    return {"unread_count": service.get_unread_count(principal.id)}


@router.post("/me/{notification_id}/read", dependencies=[Depends(Require("accounting:read"))])
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a notification as read."""
    service = NotificationService(db)
    success = service.mark_notification_read(notification_id, principal.id)

    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"status": "read", "notification_id": notification_id}


@router.post("/me/read-all", dependencies=[Depends(Require("accounting:read"))])
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark all notifications as read."""
    now = datetime.utcnow()
    result = db.query(Notification).filter(
        and_(
            Notification.user_id == principal.id,
            Notification.is_read == False,
        )
    ).update({"is_read": True, "read_at": now})
    db.commit()

    return {"status": "success", "marked_read": result}


# ============= USER PREFERENCES =============

@router.get("/me/preferences", dependencies=[Depends(Require("accounting:read"))])
async def get_my_preferences(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get current user's notification preferences."""
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == principal.id
    ).all()

    return {
        "preferences": [
            {
                "id": p.id,
                "event_type": p.event_type.value if hasattr(p.event_type, 'value') else p.event_type,
                "email_enabled": p.email_enabled,
                "in_app_enabled": p.in_app_enabled,
                "sms_enabled": p.sms_enabled,
                "slack_enabled": p.slack_enabled,
                "threshold_amount": float(p.threshold_amount) if p.threshold_amount else None,
                "threshold_days": p.threshold_days,
            }
            for p in prefs
        ],
    }


@router.put("/me/preferences", dependencies=[Depends(Require("accounting:read"))])
async def update_my_preferences(
    request: NotificationPreferenceRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update notification preference for an event type."""
    # Validate event type
    try:
        event_type = NotificationEventType(request.event_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {request.event_type}")

    # Find or create preference
    pref = db.query(NotificationPreference).filter(
        and_(
            NotificationPreference.user_id == principal.id,
            NotificationPreference.event_type == event_type,
        )
    ).first()

    if pref:
        pref.email_enabled = request.email_enabled
        pref.in_app_enabled = request.in_app_enabled
        pref.sms_enabled = request.sms_enabled
        pref.slack_enabled = request.slack_enabled
        pref.threshold_amount = Decimal(str(request.threshold_amount)) if request.threshold_amount else None
        pref.threshold_days = request.threshold_days
        pref.updated_at = datetime.utcnow()
    else:
        pref = NotificationPreference(
            user_id=principal.id,
            event_type=event_type,
            email_enabled=request.email_enabled,
            in_app_enabled=request.in_app_enabled,
            sms_enabled=request.sms_enabled,
            slack_enabled=request.slack_enabled,
            threshold_amount=Decimal(str(request.threshold_amount)) if request.threshold_amount else None,
            threshold_days=request.threshold_days,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)

    return {
        "id": pref.id,
        "event_type": pref.event_type.value if hasattr(pref.event_type, 'value') else pref.event_type,
        "email_enabled": pref.email_enabled,
        "in_app_enabled": pref.in_app_enabled,
    }


# ============= EMIT EVENT (INTERNAL/ADMIN) =============

@router.post("/emit", dependencies=[Depends(Require("books:admin"))])
async def emit_event(
    event_type: str = Query(..., description="Event type to emit"),
    payload: Dict[str, Any] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_ids: Optional[List[int]] = Query(None),
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually emit a notification event (admin only)."""
    try:
        event = NotificationEventType(event_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")

    service = NotificationService(db)
    result = service.emit_event(
        event_type=event,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        user_ids=user_ids,
        company=company,
    )

    return result
