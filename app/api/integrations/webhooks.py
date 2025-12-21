"""
Webhook endpoints for payment providers.

Handles incoming webhooks from Paystack and Flutterwave with
signature verification and idempotent processing.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_principal, Require
from app.integrations.payments.webhooks import webhook_processor
from app.integrations.payments.exceptions import WebhookVerificationError
from app.middleware.metrics import increment_webhook_auth_failure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(..., alias="x-paystack-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Paystack webhooks.

    Paystack sends webhooks for:
    - charge.success - Payment completed
    - charge.failed - Payment failed
    - transfer.success - Transfer completed
    - transfer.failed - Transfer failed
    - transfer.reversed - Transfer reversed
    - refund.processed - Refund processed
    - dedicatedaccount.assign.success - Virtual account created
    """
    payload = await request.body()
    source_ip = request.client.host if request.client else None

    try:
        result = await webhook_processor.process_paystack_webhook(
            payload=payload,
            signature=x_paystack_signature,
            db=db,
            source_ip=source_ip,
        )

        logger.info(f"Paystack webhook processed: {result}")
        return {"status": "ok", **result}

    except WebhookVerificationError as e:
        logger.warning(f"Paystack webhook verification failed: {e}")
        increment_webhook_auth_failure("paystack", "invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    except Exception as e:
        logger.error(f"Paystack webhook processing error: {e}", exc_info=True)
        # Return 200 to prevent retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    verif_hash: str = Header(None, alias="verif-hash"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Flutterwave webhooks.

    Flutterwave sends webhooks for:
    - charge.completed - Payment completed
    - charge.failed - Payment failed
    - transfer.completed - Transfer completed
    - transfer.failed - Transfer failed
    - refund.completed - Refund processed
    """
    payload = await request.body()
    source_ip = request.client.host if request.client else None

    try:
        result = await webhook_processor.process_flutterwave_webhook(
            payload=payload,
            signature=verif_hash or "",
            db=db,
            source_ip=source_ip,
        )

        logger.info(f"Flutterwave webhook processed: {result}")
        return {"status": "ok", **result}

    except WebhookVerificationError as e:
        logger.warning(f"Flutterwave webhook verification failed: {e}")
        increment_webhook_auth_failure("flutterwave", "invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    except Exception as e:
        logger.error(f"Flutterwave webhook processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/events", dependencies=[Depends(Require("admin:read"))])
async def list_webhook_events(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    processed: Optional[bool] = Query(None, description="Filter by processed status"),
    has_error: Optional[bool] = Query(None, description="Filter by error presence"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    List webhook events for debugging and monitoring.

    Requires admin:read permission.
    """
    from sqlalchemy import select
    from app.models.webhook_event import WebhookEvent

    query = select(WebhookEvent)

    if provider:
        query = query.where(WebhookEvent.provider == provider)
    if event_type:
        query = query.where(WebhookEvent.event_type == event_type)
    if processed is not None:
        query = query.where(WebhookEvent.processed == processed)
    if has_error is not None:
        if has_error:
            query = query.where(WebhookEvent.error.isnot(None))
        else:
            query = query.where(WebhookEvent.error.is_(None))

    query = query.order_by(WebhookEvent.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "items": [
            {
                "id": e.id,
                "provider": e.provider,
                "provider_event_id": e.provider_event_id,
                "event_type": e.event_type,
                "processed": e.processed,
                "error": e.error,
                "retry_count": e.retry_count,
                "source_ip": e.source_ip,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/events/{event_id}", dependencies=[Depends(Require("admin:read"))])
async def get_webhook_event(
    event_id: int,
    include_payload: bool = Query(False, description="Include full payload (sensitive)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get webhook event details.

    Requires admin:read permission. Payload is only included if explicitly requested.
    """
    from sqlalchemy import select
    from app.models.webhook_event import WebhookEvent

    result = await db.execute(
        select(WebhookEvent).where(WebhookEvent.id == event_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook event not found",
        )

    response = {
        "id": event.id,
        "provider": event.provider,
        "provider_event_id": event.provider_event_id,
        "event_type": event.event_type,
        "processed": event.processed,
        "error": event.error,
        "retry_count": event.retry_count,
        "last_retry_at": event.last_retry_at.isoformat() if event.last_retry_at else None,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "source_ip": event.source_ip,
        "received_at": event.received_at.isoformat() if event.received_at else None,
        "processed_at": event.processed_at.isoformat() if event.processed_at else None,
        "created_at": event.created_at.isoformat(),
    }

    # Only include payload if explicitly requested (contains sensitive data)
    if include_payload:
        response["payload"] = event.payload

    return response


@router.get("/providers", dependencies=[Depends(Require("admin:read"))])
async def list_webhook_providers(
    db: AsyncSession = Depends(get_db),
):
    """
    List configured webhook providers with their status.

    Shows whether each provider has webhook secrets configured
    and basic stats about received webhooks.
    """
    from sqlalchemy import select, func
    from app.models.webhook_event import WebhookEvent
    from app.integrations.payments.config import get_payment_settings

    settings = get_payment_settings()

    # Get stats per provider
    stats_query = select(
        WebhookEvent.provider,
        func.count(WebhookEvent.id).label("total_events"),
        func.count(WebhookEvent.id).filter(WebhookEvent.processed == True).label("processed_count"),
        func.count(WebhookEvent.id).filter(WebhookEvent.error.isnot(None)).label("error_count"),
        func.max(WebhookEvent.received_at).label("last_received"),
    ).group_by(WebhookEvent.provider)

    result = await db.execute(stats_query)
    stats_by_provider = {row.provider: row for row in result.all()}

    providers = [
        {
            "name": "paystack",
            "display_name": "Paystack",
            "webhook_url": "/api/integrations/webhooks/paystack",
            "secret_configured": bool(settings.paystack_webhook_secret),
            "events_supported": [
                "charge.success", "charge.failed", "transfer.success",
                "transfer.failed", "transfer.reversed", "refund.processed",
                "dedicatedaccount.assign.success"
            ],
            "stats": _format_provider_stats(stats_by_provider.get("paystack")),
        },
        {
            "name": "flutterwave",
            "display_name": "Flutterwave",
            "webhook_url": "/api/integrations/webhooks/flutterwave",
            "secret_configured": bool(settings.flutterwave_webhook_secret),
            "events_supported": [
                "charge.completed", "charge.failed", "transfer.completed",
                "transfer.failed", "refund.completed"
            ],
            "stats": _format_provider_stats(stats_by_provider.get("flutterwave")),
        },
        {
            "name": "mono",
            "display_name": "Mono (Open Banking)",
            "webhook_url": "/api/integrations/webhooks/mono",
            "secret_configured": bool(settings.mono_webhook_secret),
            "events_supported": [
                "mono.events.account_connected", "mono.events.account_updated",
                "mono.events.reauthorisation_required"
            ],
            "stats": _format_provider_stats(stats_by_provider.get("mono")),
        },
        {
            "name": "okra",
            "display_name": "Okra (Open Banking)",
            "webhook_url": "/api/integrations/webhooks/okra",
            "secret_configured": bool(settings.okra_webhook_secret),
            "events_supported": [
                "ACCOUNT_CONNECTED", "ACCOUNT_UPDATED", "TRANSACTION_UPDATED"
            ],
            "stats": _format_provider_stats(stats_by_provider.get("okra")),
        },
    ]

    return {"providers": providers}


def _format_provider_stats(row) -> dict:
    """Format provider stats row into dict."""
    if not row:
        return {
            "total_events": 0,
            "processed_count": 0,
            "error_count": 0,
            "success_rate": None,
            "last_received": None,
        }
    success_rate = None
    if row.total_events > 0:
        success_rate = round((row.processed_count / row.total_events) * 100, 1)
    return {
        "total_events": row.total_events,
        "processed_count": row.processed_count,
        "error_count": row.error_count,
        "success_rate": success_rate,
        "last_received": row.last_received.isoformat() if row.last_received else None,
    }


@router.get("/providers/{provider_name}/stats", dependencies=[Depends(Require("admin:read"))])
async def get_provider_stats(
    provider_name: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to aggregate"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed webhook statistics for a specific provider.

    Includes daily breakdown and event type distribution.
    """
    from sqlalchemy import select, func, cast, Date
    from datetime import datetime, timedelta
    from app.models.webhook_event import WebhookEvent

    valid_providers = ["paystack", "flutterwave", "mono", "okra"]
    if provider_name not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider. Valid providers: {', '.join(valid_providers)}"
        )

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Overall stats
    overall_query = select(
        func.count(WebhookEvent.id).label("total"),
        func.count(WebhookEvent.id).filter(WebhookEvent.processed == True).label("processed"),
        func.count(WebhookEvent.id).filter(WebhookEvent.error.isnot(None)).label("errors"),
    ).where(
        WebhookEvent.provider == provider_name,
        WebhookEvent.received_at >= cutoff,
    )
    overall_result = await db.execute(overall_query)
    overall = overall_result.one()

    # Daily breakdown
    daily_query = select(
        cast(WebhookEvent.received_at, Date).label("date"),
        func.count(WebhookEvent.id).label("count"),
        func.count(WebhookEvent.id).filter(WebhookEvent.error.isnot(None)).label("errors"),
    ).where(
        WebhookEvent.provider == provider_name,
        WebhookEvent.received_at >= cutoff,
    ).group_by(
        cast(WebhookEvent.received_at, Date)
    ).order_by(
        cast(WebhookEvent.received_at, Date)
    )
    daily_result = await db.execute(daily_query)
    daily_data = [
        {"date": str(row.date), "count": row.count, "errors": row.errors}
        for row in daily_result.all()
    ]

    # Event type distribution
    event_type_query = select(
        WebhookEvent.event_type,
        func.count(WebhookEvent.id).label("count"),
    ).where(
        WebhookEvent.provider == provider_name,
        WebhookEvent.received_at >= cutoff,
    ).group_by(
        WebhookEvent.event_type
    ).order_by(
        func.count(WebhookEvent.id).desc()
    )
    event_type_result = await db.execute(event_type_query)
    event_types = [
        {"event_type": row.event_type, "count": row.count}
        for row in event_type_result.all()
    ]

    # Recent errors
    errors_query = select(WebhookEvent).where(
        WebhookEvent.provider == provider_name,
        WebhookEvent.error.isnot(None),
        WebhookEvent.received_at >= cutoff,
    ).order_by(
        WebhookEvent.received_at.desc()
    ).limit(10)
    errors_result = await db.execute(errors_query)
    recent_errors = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "error": e.error[:200] if e.error else None,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in errors_result.scalars().all()
    ]

    return {
        "provider": provider_name,
        "period_days": days,
        "summary": {
            "total_events": overall.total,
            "processed": overall.processed,
            "errors": overall.errors,
            "success_rate": round((overall.processed / overall.total) * 100, 1) if overall.total > 0 else None,
        },
        "daily": daily_data,
        "event_types": event_types,
        "recent_errors": recent_errors,
    }


@router.post("/events/{event_id}/replay", dependencies=[Depends(Require("admin:write"))])
async def replay_webhook_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Replay/reprocess a webhook event.

    This will re-run the event processing logic as if the webhook was just received.
    Useful for recovering from transient failures or after fixing bugs.
    """
    from sqlalchemy import select
    from datetime import datetime
    from app.models.webhook_event import WebhookEvent
    from app.integrations.payments.enums import PaymentProvider

    result = await db.execute(
        select(WebhookEvent).where(WebhookEvent.id == event_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook event not found",
        )

    if not event.payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has no payload to replay",
        )

    # Reset event status for reprocessing
    original_processed = event.processed
    original_error = event.error

    try:
        # Get the appropriate provider enum
        provider_map = {
            "paystack": PaymentProvider.PAYSTACK,
            "flutterwave": PaymentProvider.FLUTTERWAVE,
        }
        provider = provider_map.get(event.provider)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {event.provider}",
            )

        # Re-route the event
        event_data = event.payload.get("data", {})
        await webhook_processor._route_event(
            provider=provider,
            event_type=event.event_type,
            event_data=event_data,
            db=db,
        )

        # Mark as successfully replayed
        event.processed = True
        event.error = None
        event.processed_at = datetime.utcnow()
        event.retry_count += 1
        event.last_retry_at = datetime.utcnow()
        await db.commit()

        logger.info(f"Webhook event replayed successfully: {event_id}")

        return {
            "event_id": event_id,
            "status": "replayed",
            "previous_state": {
                "processed": original_processed,
                "error": original_error,
            },
            "current_state": {
                "processed": True,
                "error": None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log the error but don't reset the event
        event.error = str(e)[:1000]
        event.retry_count += 1
        event.last_retry_at = datetime.utcnow()
        await db.commit()

        logger.error(f"Webhook event replay failed: {event_id} - {e}")

        return {
            "event_id": event_id,
            "status": "failed",
            "error": str(e),
            "previous_state": {
                "processed": original_processed,
                "error": original_error,
            },
        }
