"""Bundle Scheduled Tasks.

Celery tasks for processing data bundle operations:
- Usage sync from RADIUS
- Exhaustion checking and handling
- Expiry processing with rollover
- Alert notifications
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models.data_bundle import BundleStatus, CustomerBundle, DataBundleProduct
from app.services.subscriptions.data_bundles import DataBundleService
from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)


@shared_task(name="bundles.process_usage")
def process_bundle_usage() -> dict:
    """Sync usage from RADIUS accounting to bundle records.

    Runs every 5 minutes to aggregate RADIUS accounting data
    and update bundle usage counters.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_process_bundle_usage())


async def _process_bundle_usage() -> dict:
    """Async implementation of usage processing."""
    async with async_session_maker() as db:
        # This would integrate with RADIUS accounting
        # For now, placeholder that could poll RADIUS accounting table
        # or receive usage updates via API

        # Example: Query unprocessed RADIUS accounting records
        # and aggregate by subscription, then call DataBundleService.record_usage

        logger.info("Bundle usage sync completed")
        return {"status": "ok", "records_processed": 0}


@shared_task(name="bundles.check_exhaustion")
def check_bundle_exhaustion() -> dict:
    """Check for exhausted bundles and trigger actions.

    Runs every minute to catch bundles that have exceeded
    their data allocation.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_check_bundle_exhaustion())


async def _check_bundle_exhaustion() -> dict:
    """Async implementation of exhaustion checking."""
    async with async_session_maker() as db:
        service = DataBundleService(db, EventBus(db))

        # Find active bundles that are exhausted but not yet marked
        result = await db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(
                and_(
                    CustomerBundle.status == BundleStatus.ACTIVE.value,
                    CustomerBundle.exhausted_at.is_(None),
                )
            )
        )
        bundles = list(result.scalars().all())

        exhausted_count = 0
        for bundle in bundles:
            if bundle.is_exhausted:
                await service.handle_exhaustion(bundle.id)
                exhausted_count += 1

        await db.commit()

        if exhausted_count > 0:
            logger.info("Processed %d exhausted bundles", exhausted_count)

        return {"status": "ok", "exhausted_bundles": exhausted_count}


@shared_task(name="bundles.process_expiry")
def process_bundle_expiry() -> dict:
    """Handle expired bundles and rollover calculation.

    Runs daily at midnight to:
    - Mark expired bundles as expired
    - Calculate and apply rollover to next bundle
    - Notify customers of expiry
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_process_bundle_expiry())


async def _process_bundle_expiry() -> dict:
    """Async implementation of expiry processing."""
    async with async_session_maker() as db:
        service = DataBundleService(db, EventBus(db))

        processed = await service.process_expiring_bundles()
        await db.commit()

        logger.info("Processed %d expired bundles", len(processed))
        return {"status": "ok", "expired_bundles": len(processed)}


@shared_task(name="bundles.send_alerts")
def send_bundle_alerts() -> dict:
    """Send low-balance and expiry warning notifications.

    Runs every hour to:
    - Send threshold alerts (50%, 80%, 95%)
    - Send expiry warnings (7 days, 3 days, 1 day)
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_send_bundle_alerts())


async def _send_bundle_alerts() -> dict:
    """Async implementation of alert sending."""
    from datetime import timedelta
    from app.services.subscriptions.subscription_settings import SubscriptionSettingsService

    async with async_session_maker() as db:
        now = datetime.now(timezone.utc)
        alerts_sent = 0

        # Get configured expiry warning thresholds from settings
        settings_service = SubscriptionSettingsService(db)
        settings = await settings_service.get_settings()

        # Build expiry thresholds from settings
        expiry_thresholds = [
            (days, f"bundle.expiry_warning_{days}_days")
            for days in settings.bundle_expiry_warning_days
        ]

        for days, event_type in expiry_thresholds:
            threshold = now + timedelta(days=days)
            threshold_start = now + timedelta(days=days - 1)

            result = await db.execute(
                select(CustomerBundle)
                .options(selectinload(CustomerBundle.product))
                .where(
                    and_(
                        CustomerBundle.status == BundleStatus.ACTIVE.value,
                        CustomerBundle.expires_at <= threshold,
                        CustomerBundle.expires_at > threshold_start,
                    )
                )
            )
            expiring_bundles = list(result.scalars().all())

            event_bus = EventBus(db)
            for bundle in expiring_bundles:
                await event_bus.emit(
                    event_type,
                    {
                        "bundle_id": bundle.id,
                        "subscription_id": bundle.subscription_id,
                        "expires_at": bundle.expires_at.isoformat() if bundle.expires_at else None,
                        "days_remaining": days,
                        "data_remaining_mb": bundle.data_remaining_mb,
                    },
                )
                alerts_sent += 1

        await db.commit()

        if alerts_sent > 0:
            logger.info("Sent %d bundle alerts", alerts_sent)

        return {"status": "ok", "alerts_sent": alerts_sent}


@shared_task(name="bundles.cleanup_expired")
def cleanup_expired_bundles() -> dict:
    """Clean up old expired/cancelled bundles.

    Runs weekly to archive or delete bundles that have been
    expired/cancelled for more than the configured retention period.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_cleanup_expired_bundles())


async def _cleanup_expired_bundles() -> dict:
    """Async implementation of cleanup."""
    from datetime import timedelta
    from app.services.subscriptions.subscription_settings import SubscriptionSettingsService

    async with async_session_maker() as db:
        # Get retention period from settings
        settings_service = SubscriptionSettingsService(db)
        settings = await settings_service.get_settings()
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.bundle_cleanup_retention_days)

        # For now, just log. In production, might archive or delete.
        result = await db.execute(
            select(CustomerBundle).where(
                and_(
                    CustomerBundle.status.in_([
                        BundleStatus.EXPIRED.value,
                        BundleStatus.CANCELLED.value,
                    ]),
                    CustomerBundle.updated_at < cutoff,
                )
            )
        )
        old_bundles = list(result.scalars().all())

        logger.info("Found %d bundles eligible for cleanup", len(old_bundles))
        return {"status": "ok", "bundles_found": len(old_bundles)}


@shared_task(name="bundles.auto_activate_pending")
def auto_activate_pending_bundles() -> dict:
    """Automatically activate pending bundles when current expires.

    Runs every 5 minutes to activate the next pending bundle
    when a subscription's active bundle expires or is exhausted.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_auto_activate_pending_bundles())


async def _auto_activate_pending_bundles() -> dict:
    """Async implementation of auto-activation."""
    async with async_session_maker() as db:
        service = DataBundleService(db, EventBus(db))

        # Find subscriptions with no active bundle but have pending bundles
        from sqlalchemy import func, exists

        subq = select(CustomerBundle.subscription_id).where(
            CustomerBundle.status == BundleStatus.ACTIVE.value
        )

        result = await db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(
                and_(
                    CustomerBundle.status == BundleStatus.PENDING.value,
                    ~CustomerBundle.subscription_id.in_(subq),
                )
            )
            .distinct(CustomerBundle.subscription_id)
            .order_by(CustomerBundle.subscription_id, CustomerBundle.purchased_at)
        )

        pending_bundles = list(result.scalars().all())
        activated_count = 0

        for bundle in pending_bundles:
            try:
                await service.activate_bundle(bundle.id)
                activated_count += 1
                logger.info(
                    "Auto-activated bundle %d for subscription %d",
                    bundle.id,
                    bundle.subscription_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to auto-activate bundle %d: %s",
                    bundle.id,
                    e,
                )

        await db.commit()

        if activated_count > 0:
            logger.info("Auto-activated %d pending bundles", activated_count)

        return {"status": "ok", "bundles_activated": activated_count}
