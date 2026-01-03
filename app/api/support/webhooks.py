"""Webhooks API - REST endpoints for webhook event management.

Provides endpoints for:
- Webhook event listing and details
- Failed event retry
- Public webhook ingestion endpoint
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.services.support.webhooks import WebhookService
from app.services.support.errors import (
    ChannelNotFoundError,
    WebhookProcessingError,
    WebhookValidationError,
)

router = APIRouter()

# RBAC dependencies
webhook_read_dep = Depends(Require("support:webhooks:read", "support:read"))
webhook_write_dep = Depends(Require("support:webhooks:write", "support:write"))


# ---------------------------------------------------------------------------
# Service Dependency
# ---------------------------------------------------------------------------


def get_webhook_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> WebhookService:
    """Dependency to get a WebhookService instance."""
    return WebhookService(db, principal)


def get_public_webhook_service(
    db: Session = Depends(get_db),
) -> WebhookService:
    """Dependency to get a WebhookService for public endpoints (no auth)."""
    return WebhookService(db)


# ---------------------------------------------------------------------------
# Response Serializers
# ---------------------------------------------------------------------------


def serialize_event(event) -> Dict[str, Any]:
    """Serialize a webhook event for API response."""
    return {
        "id": event.id,
        "channel_id": event.channel_id,
        "provider_event_id": event.provider_event_id,
        "payload": event.payload,
        "headers": event.headers,
        "processed": event.processed,
        "error": event.error,
        "retry_count": event.retry_count,
        "received_at": event.received_at.isoformat() if event.received_at else None,
        "last_retry_at": event.last_retry_at.isoformat() if event.last_retry_at else None,
    }


def serialize_result(result) -> Dict[str, Any]:
    """Serialize a webhook processing result."""
    return {
        "success": result.success,
        "event_id": result.event_id,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "error": result.error,
        "is_duplicate": result.is_duplicate,
        "action_taken": result.action_taken,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    dependencies=[webhook_read_dep],
)
def list_events(
    channel_id: Optional[int] = None,
    processed: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """List webhook events with optional filtering.

    Args:
        channel_id: Filter by channel.
        processed: Filter by processed status.
        limit: Maximum events to return.
        offset: Pagination offset.

    Returns:
        List of webhook events.
    """
    events, total = service.list_events(
        channel_id=channel_id,
        processed=processed,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_event(e) for e in events],
    }


@router.get(
    "/events/{event_id}",
    dependencies=[webhook_read_dep],
)
def get_event(
    event_id: int,
    service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """Get a webhook event by ID.

    Args:
        event_id: The event ID.

    Returns:
        Event details.
    """
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Webhook event not found: {event_id}")
    return serialize_event(event)


@router.post(
    "/events/{event_id}/retry",
    dependencies=[webhook_write_dep],
)
def retry_event(
    event_id: int,
    db: Session = Depends(get_db),
    service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """Retry processing a failed webhook event.

    Args:
        event_id: The event ID.

    Returns:
        Processing result.
    """
    try:
        result = service.retry_event(event_id)
        db.commit()
        return serialize_result(result)
    except WebhookProcessingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/ingest/{channel_id}",
)
async def ingest_webhook(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    service: WebhookService = Depends(get_public_webhook_service),
) -> Dict[str, Any]:
    """Ingest a webhook event (public endpoint).

    This endpoint is called by external services to deliver webhook events.
    No authentication required, but signature validation may be performed
    based on channel configuration.

    Args:
        channel_id: The channel ID.
        request: The incoming request.

    Returns:
        Processing result.
    """
    try:
        # Read raw body for signature validation
        raw_body = await request.body()

        # Parse JSON payload
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        # Get headers as dict
        headers = dict(request.headers)

        result = service.ingest(
            channel_id=channel_id,
            payload=payload,
            headers=headers,
            raw_body=raw_body,
        )
        db.commit()
        return serialize_result(result)
    except ChannelNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except WebhookValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except WebhookProcessingError as exc:
        db.rollback()
        # Still return 200 with error info for webhooks
        return {
            "success": False,
            "event_id": exc.event_id,
            "error": exc.message,
        }


@router.get(
    "/stats",
    dependencies=[webhook_read_dep],
)
def get_stats(
    channel_id: Optional[int] = None,
    service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """Get webhook processing statistics.

    Args:
        channel_id: Optional channel filter.

    Returns:
        Statistics summary.
    """
    # Get counts for different states
    processed_events, processed_total = service.list_events(
        channel_id=channel_id,
        processed=True,
        limit=0,
        offset=0,
    )
    failed_events, failed_total = service.list_events(
        channel_id=channel_id,
        processed=False,
        limit=0,
        offset=0,
    )
    all_events, all_total = service.list_events(
        channel_id=channel_id,
        processed=None,
        limit=0,
        offset=0,
    )

    return {
        "channel_id": channel_id,
        "total_events": all_total,
        "processed": processed_total,
        "pending": failed_total,
        "success_rate": (processed_total / all_total * 100) if all_total > 0 else 0,
    }
