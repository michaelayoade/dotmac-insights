"""Celery tasks for upselling opportunity analysis and management."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import structlog

from app.worker import celery_app
from app.config import settings
from app.database import AsyncSessionLocal
from app.services.subscriptions.upselling import UpsellingService
from app.services.subscriptions.upselling_types import BatchAnalysisInput, TriggerType
from app.services.event_bus import EventBus
from app.services.notification_service import NotificationService

logger = structlog.get_logger()


def run_async(coro):
    """Run async coroutine in sync context for Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Scheduled Analysis Tasks
# =============================================================================

@celery_app.task(
    name="upselling.run_daily_analysis",
    bind=True,
    max_retries=3,
    default_retry_delay=60 * 5,
)
def run_daily_analysis(self, company_id: int = 1):
    """Run daily upselling opportunity analysis.

    Scheduled to run daily (recommended: overnight during low traffic).
    Analyzes all active subscriptions for upselling opportunities.
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            logger.info("upselling_daily_analysis_started", company_id=company_id)

            input_data = BatchAnalysisInput(
                subscription_ids=None,  # All active subscriptions
                min_months_active=3,
                exclude_recently_analyzed=True,
                recently_analyzed_days=7,
            )

            result = await service.run_batch_analysis(input_data)
            await session.commit()

            logger.info(
                "upselling_daily_analysis_completed",
                company_id=company_id,
                subscriptions_analyzed=result.subscriptions_analyzed,
                opportunities_found=result.opportunities_found,
                total_potential_mrr=float(result.total_potential_mrr),
                duration_seconds=result.duration_seconds,
            )

            # Notify if high-value opportunities found
            if result.opportunities_found > 0:
                await _notify_new_opportunities(session, company_id, result)

            return {
                "success": True,
                "run_id": result.run_id,
                "subscriptions_analyzed": result.subscriptions_analyzed,
                "opportunities_found": result.opportunities_found,
            }

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(
            "upselling_daily_analysis_failed",
            company_id=company_id,
            error=str(e),
        )
        raise self.retry(exc=e)


@celery_app.task(
    name="upselling.run_contract_renewal_check",
    bind=True,
    max_retries=3,
    default_retry_delay=60 * 5,
)
def run_contract_renewal_check(self, company_id: int = 1, days_ahead: int = 60):
    """Check for contracts expiring soon and create opportunities.

    Specifically looks for subscriptions with contract end dates
    within the specified number of days.
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            logger.info(
                "contract_renewal_check_started",
                company_id=company_id,
                days_ahead=days_ahead,
            )

            input_data = BatchAnalysisInput(
                subscription_ids=None,
                trigger_types=[TriggerType.CONTRACT_RENEWAL],
                min_months_active=0,  # Include all active subscriptions
                exclude_recently_analyzed=True,
                recently_analyzed_days=14,  # Don't re-check recently analyzed
            )

            result = await service.run_batch_analysis(input_data)
            await session.commit()

            logger.info(
                "contract_renewal_check_completed",
                company_id=company_id,
                opportunities_found=result.opportunities_found,
            )

            return {
                "success": True,
                "opportunities_found": result.opportunities_found,
            }

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(
            "contract_renewal_check_failed",
            company_id=company_id,
            error=str(e),
        )
        raise self.retry(exc=e)


@celery_app.task(
    name="upselling.run_high_usage_check",
    bind=True,
    max_retries=3,
    default_retry_delay=60 * 5,
)
def run_high_usage_check(self, company_id: int = 1):
    """Check for high data usage patterns.

    Specifically targets subscriptions showing consistent high usage
    that might benefit from larger data caps.
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            logger.info("high_usage_check_started", company_id=company_id)

            input_data = BatchAnalysisInput(
                subscription_ids=None,
                trigger_types=[TriggerType.HIGH_USAGE, TriggerType.BUNDLE_EXHAUSTION],
                min_months_active=3,
                exclude_recently_analyzed=True,
                recently_analyzed_days=7,
            )

            result = await service.run_batch_analysis(input_data)
            await session.commit()

            logger.info(
                "high_usage_check_completed",
                company_id=company_id,
                opportunities_found=result.opportunities_found,
                by_trigger=result.opportunities_by_trigger,
            )

            return {
                "success": True,
                "opportunities_found": result.opportunities_found,
                "by_trigger": result.opportunities_by_trigger,
            }

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(
            "high_usage_check_failed",
            company_id=company_id,
            error=str(e),
        )
        raise self.retry(exc=e)


# =============================================================================
# Opportunity Lifecycle Tasks
# =============================================================================

@celery_app.task(name="upselling.expire_old_opportunities")
def expire_old_opportunities(company_id: int = 1):
    """Expire opportunities that have passed their expiry date.

    Should be scheduled to run daily.
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            logger.info("expiring_old_opportunities", company_id=company_id)

            try:
                count = await service.expire_old_opportunities()
                await session.commit()

                logger.info(
                    "opportunities_expired",
                    company_id=company_id,
                    count=count,
                )

                return {"success": True, "expired_count": count}

            except Exception as e:
                logger.error(
                    "expire_opportunities_failed",
                    company_id=company_id,
                    error=str(e),
                )
                raise

    return run_async(_run())


@celery_app.task(name="upselling.send_follow_up_reminders")
def send_follow_up_reminders(company_id: int = 1):
    """Send reminders for opportunities needing follow-up.

    Notifies sales reps about:
    - Opportunities assigned but not contacted
    - Opportunities contacted but not progressed
    - High-priority opportunities
    """
    async def _run():
        from sqlalchemy import select, and_
        from app.models.upselling import UpsellOpportunity, UpsellStatus
        from app.utils.datetime_utils import utc_now

        async with AsyncSessionLocal() as session:
            logger.info("sending_follow_up_reminders", company_id=company_id)

            now = utc_now()
            stale_threshold = now - timedelta(days=3)  # Not contacted in 3 days

            # Find stale opportunities
            q = select(UpsellOpportunity).where(
                and_(
                    UpsellOpportunity.status.in_([
                        UpsellStatus.NEW.value,
                        UpsellStatus.CONTACTED.value,
                    ]),
                    UpsellOpportunity.assigned_to_id.isnot(None),
                    UpsellOpportunity.created_at <= stale_threshold,
                )
            )

            result = await session.execute(q)
            stale_opportunities = list(result.scalars().all())

            reminders_sent = 0
            for opp in stale_opportunities:
                try:
                    await _send_follow_up_reminder(session, opp)
                    reminders_sent += 1
                except Exception as e:
                    logger.warning(
                        "follow_up_reminder_failed",
                        opportunity_id=opp.id,
                        error=str(e),
                    )

            logger.info(
                "follow_up_reminders_sent",
                company_id=company_id,
                reminders_sent=reminders_sent,
            )

            return {"success": True, "reminders_sent": reminders_sent}

    return run_async(_run())


# =============================================================================
# Notification Tasks
# =============================================================================

@celery_app.task(name="upselling.notify_high_score_opportunity")
def notify_high_score_opportunity(opportunity_id: int, company_id: int = 1):
    """Send notification for a high-scoring opportunity.

    Called when a new opportunity with a high trigger score is created.
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            opportunity = await service.get_opportunity(opportunity_id)
            if not opportunity:
                logger.warning(
                    "opportunity_not_found_for_notification",
                    opportunity_id=opportunity_id,
                )
                return

            logger.info(
                "notifying_high_score_opportunity",
                opportunity_id=opportunity_id,
                trigger_score=opportunity.trigger_score,
                potential_mrr=float(opportunity.monthly_revenue_increase),
            )

            # Build notification
            notification_service = NotificationService(session)

            await notification_service.send_notification(
                notification_type="upsell_high_score",
                subject=f"High-value upselling opportunity detected",
                message=(
                    f"A high-scoring upselling opportunity has been detected:\n\n"
                    f"Customer: Party #{opportunity.party_id}\n"
                    f"Current Plan: {opportunity.current_plan_name}\n"
                    f"Trigger: {opportunity.trigger_type.replace('_', ' ').title()}\n"
                    f"Score: {opportunity.trigger_score}/100\n"
                    f"Potential MRR Increase: ₦{opportunity.monthly_revenue_increase:,.2f}\n"
                ),
                metadata={
                    "opportunity_id": opportunity_id,
                    "subscription_id": opportunity.subscription_id,
                    "party_id": opportunity.party_id,
                },
                # Would send to sales managers
            )

            return {"success": True, "notified": True}

    return run_async(_run())


@celery_app.task(name="upselling.send_daily_digest")
def send_daily_digest(company_id: int = 1):
    """Send daily digest of upselling activity.

    Summarizes:
    - New opportunities created
    - Opportunities converted
    - Pending high-priority opportunities
    - Revenue impact
    """
    async def _run():
        async with AsyncSessionLocal() as session:
            service = UpsellingService(session, company_id)

            logger.info("generating_daily_digest", company_id=company_id)

            # Get stats
            stats = await service.get_conversion_stats(1)  # Last 24 hours
            forecast = await service.get_revenue_forecast()

            # Build digest message
            message = f"""
Upselling Daily Digest

NEW OPPORTUNITIES TODAY
-----------------------
Total: {stats.total_opportunities}
Potential MRR: ₦{float(forecast.potential_monthly_revenue):,.2f}

CONVERSIONS TODAY
-----------------
Converted: {stats.converted_count}
MRR Gained: ₦{float(stats.total_mrr_gained):,.2f}

PENDING OPPORTUNITIES
---------------------
Active: {forecast.active_opportunities}
Expected MRR (25% conv.): ₦{float(forecast.expected_monthly_revenue):,.2f}

Conversion Rate (30d): {stats.conversion_rate:.1f}%
"""

            notification_service = NotificationService(session)

            await notification_service.send_notification(
                notification_type="upsell_daily_digest",
                subject="Upselling Daily Digest",
                message=message,
                metadata={
                    "new_opportunities": stats.total_opportunities,
                    "conversions": stats.converted_count,
                    "mrr_gained": float(stats.total_mrr_gained),
                },
            )

            logger.info("daily_digest_sent", company_id=company_id)

            return {"success": True}

    return run_async(_run())


# =============================================================================
# Helper Functions
# =============================================================================

async def _notify_new_opportunities(session, company_id: int, result):
    """Notify about new opportunities from batch analysis."""
    if result.opportunities_found == 0:
        return

    try:
        notification_service = NotificationService(session)

        await notification_service.send_notification(
            notification_type="upsell_batch_complete",
            subject=f"{result.opportunities_found} new upselling opportunities found",
            message=(
                f"Batch analysis completed:\n\n"
                f"Subscriptions analyzed: {result.subscriptions_analyzed}\n"
                f"Opportunities found: {result.opportunities_found}\n"
                f"Total potential MRR: ₦{float(result.total_potential_mrr):,.2f}\n\n"
                f"By trigger type:\n"
                + "\n".join(
                    f"  - {k}: {v}"
                    for k, v in result.opportunities_by_trigger.items()
                )
            ),
            metadata={
                "run_id": result.run_id,
                "opportunities_found": result.opportunities_found,
                "total_potential_mrr": float(result.total_potential_mrr),
            },
        )
    except Exception as e:
        logger.warning("notify_new_opportunities_failed", error=str(e))


async def _send_follow_up_reminder(session, opportunity):
    """Send follow-up reminder for a specific opportunity."""
    from app.models.employee import Employee
    from app.utils.datetime_utils import utc_now

    # Get assignee info
    assignee = await session.get(Employee, opportunity.assigned_to_id)
    if not assignee:
        return

    notification_service = NotificationService(session)

    days_old = (utc_now() - opportunity.created_at).days

    await notification_service.send_notification(
        notification_type="upsell_follow_up",
        subject=f"Follow-up needed: Upselling opportunity #{opportunity.id}",
        message=(
            f"This opportunity requires follow-up:\n\n"
            f"Customer: Party #{opportunity.party_id}\n"
            f"Plan: {opportunity.current_plan_name}\n"
            f"Trigger: {opportunity.trigger_type.replace('_', ' ').title()}\n"
            f"Status: {opportunity.status}\n"
            f"Days since created: {days_old}\n"
            f"Potential MRR: ₦{opportunity.monthly_revenue_increase:,.2f}\n"
        ),
        recipient_ids=[opportunity.assigned_to_id],
        metadata={
            "opportunity_id": opportunity.id,
            "days_old": days_old,
        },
    )


# =============================================================================
# Celery Beat Schedule
# =============================================================================

# These would be added to the Celery beat schedule configuration
UPSELLING_SCHEDULE = {
    "upselling-daily-analysis": {
        "task": "upselling.run_daily_analysis",
        "schedule": 86400,  # Daily
        "args": (1,),  # company_id
        "options": {"queue": "low_priority"},
    },
    "upselling-expire-opportunities": {
        "task": "upselling.expire_old_opportunities",
        "schedule": 86400,  # Daily
        "args": (1,),
    },
    "upselling-follow-up-reminders": {
        "task": "upselling.send_follow_up_reminders",
        "schedule": 86400,  # Daily (morning)
        "args": (1,),
    },
    "upselling-daily-digest": {
        "task": "upselling.send_daily_digest",
        "schedule": 86400,  # Daily (end of day)
        "args": (1,),
    },
    "upselling-contract-renewal-check": {
        "task": "upselling.run_contract_renewal_check",
        "schedule": 86400,  # Daily
        "args": (1, 60),  # company_id, days_ahead
    },
    "upselling-high-usage-check": {
        "task": "upselling.run_high_usage_check",
        "schedule": 86400 * 7,  # Weekly
        "args": (1,),
    },
}
