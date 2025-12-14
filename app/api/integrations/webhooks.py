"""
Webhook endpoints for payment providers.

Handles incoming webhooks from Paystack and Flutterwave with
signature verification and idempotent processing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.integrations.payments.webhooks import webhook_processor
from app.integrations.payments.exceptions import WebhookVerificationError

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

    try:
        result = await webhook_processor.process_paystack_webhook(
            payload=payload,
            signature=x_paystack_signature,
            db=db,
        )

        logger.info(f"Paystack webhook processed: {result}")
        return {"status": "ok", **result}

    except WebhookVerificationError as e:
        logger.warning(f"Paystack webhook verification failed: {e}")
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

    try:
        result = await webhook_processor.process_flutterwave_webhook(
            payload=payload,
            signature=verif_hash or "",
            db=db,
        )

        logger.info(f"Flutterwave webhook processed: {result}")
        return {"status": "ok", **result}

    except WebhookVerificationError as e:
        logger.warning(f"Flutterwave webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    except Exception as e:
        logger.error(f"Flutterwave webhook processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/events")
async def list_webhook_events(
    provider: str = None,
    event_type: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    List webhook events for debugging and monitoring.
    """
    from sqlalchemy import select
    from app.models.webhook_event import WebhookEvent

    query = select(WebhookEvent)

    if provider:
        query = query.where(WebhookEvent.provider == provider)
    if event_type:
        query = query.where(WebhookEvent.event_type == event_type)
    if status:
        query = query.where(WebhookEvent.status == status)

    query = query.order_by(WebhookEvent.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "items": [
            {
                "id": e.id,
                "provider": e.provider,
                "event_type": e.event_type,
                "idempotency_key": e.idempotency_key,
                "status": e.status,
                "error_message": e.error_message,
                "created_at": e.created_at.isoformat(),
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in events
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/events/{event_id}")
async def get_webhook_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get webhook event details including payload."""
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

    return {
        "id": event.id,
        "provider": event.provider,
        "event_type": event.event_type,
        "idempotency_key": event.idempotency_key,
        "status": event.status,
        "payload": event.payload,
        "error_message": event.error_message,
        "created_at": event.created_at.isoformat(),
        "processed_at": event.processed_at.isoformat() if event.processed_at else None,
    }
