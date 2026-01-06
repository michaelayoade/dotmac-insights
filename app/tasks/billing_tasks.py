"""
Celery tasks for subscription billing automation.

These tasks handle scheduled billing operations:
- Daily billing runs
- Weekly/monthly billing cycles
- Payment processing via gateways
- Invoice generation
- Failed charge retries

All tasks read configuration from BillingConfigService for:
- Enabled/disabled flags
- Currency settings
- Retry parameters
- Schedule timing
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from celery import shared_task
from celery.schedules import crontab

from app.worker import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_billing_config():
    """Get billing configuration from database.

    Returns a BillingConfig instance with all settings.
    Must be called within a task with an active db session.
    """
    from app.services.subscriptions.billing_config import get_billing_config
    db = SessionLocal()
    try:
        return get_billing_config(db)
    finally:
        db.close()


# =============================================================================
# Daily Billing Tasks
# =============================================================================

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_daily_billing(
    self,
    billing_date: Optional[str] = None,
    dry_run: bool = False,
):
    """
    Run daily billing for all subscriptions with daily billing cycle.

    Reads schedule and settings from BillingConfigService.
    Skips execution if daily billing is disabled in config.

    Args:
        billing_date: Date to bill for (YYYY-MM-DD). Defaults to yesterday.
        dry_run: If True, calculate but don't create invoices/charges.

    Returns:
        Dict with billing run summary.
    """
    from app.services.subscriptions import BillingService
    from app.services.subscriptions.billing_config import BillingConfigService

    db = SessionLocal()
    try:
        # Load configuration
        config_service = BillingConfigService(db)
        config = config_service.get_config()

        # Check if daily billing is enabled
        if not config.enabled:
            logger.info("Billing is disabled globally, skipping daily billing run")
            return {"skipped": True, "reason": "billing_disabled"}

        if not config.daily_billing_enabled:
            logger.info("Daily billing is disabled, skipping")
            return {"skipped": True, "reason": "daily_billing_disabled"}

        target_date = (
            date.fromisoformat(billing_date)
            if billing_date
            else date.today() - timedelta(days=1)
        )

        logger.info(
            f"Starting daily billing run for {target_date}",
            extra={
                "billing_date": target_date.isoformat(),
                "dry_run": dry_run,
                "currency": config.default_currency,
                "billing_type": config.daily_billing_type,
            },
        )

        service = BillingService(db)
        summary = service.run_daily_billing(
            billing_date=target_date,
            dry_run=dry_run,
        )

        db.commit()

        logger.info(
            f"Daily billing completed: {summary.successful}/{summary.total_subscriptions} successful",
            extra={
                "run_id": summary.run_id,
                "total": summary.total_subscriptions,
                "successful": summary.successful,
                "failed": summary.failed,
                "total_amount": float(summary.total_amount),
            },
        )

        return {
            "run_id": summary.run_id,
            "run_date": summary.run_date.isoformat(),
            "total_subscriptions": summary.total_subscriptions,
            "successful": summary.successful,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "total_amount": float(summary.total_amount),
            "currency": summary.currency,
            "error_count": len(summary.error_details),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Daily billing failed: {e}", exc_info=True)
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def bill_single_subscription_daily(
    self,
    subscription_id: int,
    billing_date: Optional[str] = None,
):
    """
    Bill a single subscription for a specific day.

    Used for manual billing or retry of failed daily bills.

    Args:
        subscription_id: The subscription to bill.
        billing_date: Date to bill for (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        Dict with billing result.
    """
    from app.services.subscriptions import BillingService

    db = SessionLocal()
    try:
        target_date = (
            date.fromisoformat(billing_date)
            if billing_date
            else date.today() - timedelta(days=1)
        )

        service = BillingService(db)
        result = service.bill_subscription_daily(
            subscription_id=subscription_id,
            billing_date=target_date,
        )

        db.commit()

        return {
            "subscription_id": result.subscription_id,
            "billing_date": result.billing_date.isoformat(),
            "success": result.success,
            "billing_type": result.billing_type,
            "total_amount": float(result.total_amount),
            "currency": result.currency,
            "invoice_id": result.invoice_id,
            "error_message": result.error_message,
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"Single subscription billing failed: {e}",
            extra={"subscription_id": subscription_id},
            exc_info=True,
        )
        raise self.retry(exc=e)

    finally:
        db.close()


# =============================================================================
# Monthly Billing Tasks
# =============================================================================

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_monthly_billing(
    self,
    billing_month: Optional[str] = None,
    dry_run: bool = False,
):
    """
    Run monthly billing for subscriptions due this month.

    Reads schedule and settings from BillingConfigService.
    Skips execution if monthly billing is disabled in config.

    Args:
        billing_month: Month to bill (YYYY-MM). Defaults to current month.
        dry_run: If True, calculate but don't create invoices/charges.

    Returns:
        Dict with billing run summary.
    """
    from app.services.subscriptions import BillingService
    from app.services.subscriptions.billing_config import BillingConfigService

    db = SessionLocal()
    try:
        # Load configuration
        config_service = BillingConfigService(db)
        config = config_service.get_config()

        # Check if monthly billing is enabled
        if not config.enabled:
            logger.info("Billing is disabled globally, skipping monthly billing run")
            return {"skipped": True, "reason": "billing_disabled"}

        if not config.monthly_billing_enabled:
            logger.info("Monthly billing is disabled, skipping")
            return {"skipped": True, "reason": "monthly_billing_disabled"}

        if billing_month:
            year, month = map(int, billing_month.split("-"))
            target_date = date(year, month, 1)
        else:
            target_date = date.today()

        logger.info(
            f"Starting monthly billing run for {target_date.strftime('%Y-%m')}",
            extra={
                "billing_month": target_date.strftime("%Y-%m"),
                "dry_run": dry_run,
                "currency": config.default_currency,
            },
        )

        service = BillingService(db)
        billable = service.get_billable_subscriptions("monthly", target_date)

        results = {
            "total": len(billable),
            "successful": 0,
            "failed": 0,
            "total_amount": Decimal("0"),
            "errors": [],
        }

        for sub in billable:
            try:
                # Generate invoice for monthly subscription
                if not dry_run:
                    # Calculate billing period
                    period_start = target_date.replace(day=1)
                    if target_date.month == 12:
                        period_end = target_date.replace(
                            year=target_date.year + 1, month=1, day=1
                        ) - timedelta(days=1)
                    else:
                        period_end = target_date.replace(
                            month=target_date.month + 1, day=1
                        ) - timedelta(days=1)

                    invoice = service.generate_subscription_invoice(
                        subscription_id=sub.subscription_id,
                        billing_period_start=period_start,
                        billing_period_end=period_end,
                    )

                    # Auto-charge if enabled and payment subscription linked
                    if (
                        config.auto_charge_enabled
                        and sub.has_auto_charge
                        and sub.payment_subscription_id
                    ):
                        # Use configured currency if subscription currency not set
                        charge_currency = sub.currency or config.default_currency
                        process_subscription_charge.delay(
                            payment_subscription_id=sub.payment_subscription_id,
                            amount=float(sub.price),
                            currency=charge_currency,
                            description=f"Monthly billing: {sub.plan_name}",
                            invoice_id=invoice.id,
                        )

                results["successful"] += 1
                results["total_amount"] += sub.price

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "subscription_id": sub.subscription_id,
                    "error": str(e),
                })
                logger.error(
                    f"Monthly billing failed for subscription {sub.subscription_id}: {e}"
                )

        db.commit()

        logger.info(
            f"Monthly billing completed: {results['successful']}/{results['total']} successful",
            extra=results,
        )

        return {
            "billing_month": target_date.strftime("%Y-%m"),
            "total_subscriptions": results["total"],
            "successful": results["successful"],
            "failed": results["failed"],
            "total_amount": float(results["total_amount"]),
            "currency": config.default_currency,
            "error_count": len(results["errors"]),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Monthly billing failed: {e}", exc_info=True)
        raise self.retry(exc=e)

    finally:
        db.close()


# =============================================================================
# Payment Processing Tasks
# =============================================================================

@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def process_subscription_charge(
    self,
    payment_subscription_id: int,
    amount: float,
    currency: str,
    description: str,
    invoice_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
):
    """
    Process a charge for a payment subscription.

    Charges the saved payment method via the payment gateway.
    Uses configurable retry settings from BillingConfigService.

    Args:
        payment_subscription_id: The payment subscription ID.
        amount: Amount to charge.
        currency: Currency code.
        description: Charge description.
        invoice_id: Optional linked invoice ID.
        idempotency_key: Optional idempotency key for deduplication.

    Returns:
        Dict with charge result.
    """
    from app.models.payment_subscription import PaymentSubscription
    from app.integrations.payments.providers import get_payment_provider
    from app.services.subscriptions.billing_config import BillingConfigService

    db = SessionLocal()
    try:
        # Load configuration for retry settings
        config_service = BillingConfigService(db)
        config = config_service.get_config()

        # Check if billing is enabled
        if not config.enabled:
            return {
                "success": False,
                "error": "Billing is disabled",
                "skipped": True,
            }

        payment_sub = (
            db.query(PaymentSubscription)
            .filter(PaymentSubscription.id == payment_subscription_id)
            .first()
        )

        if not payment_sub:
            return {
                "success": False,
                "error": "Payment subscription not found",
            }

        if not payment_sub.is_active:
            return {
                "success": False,
                "error": "Payment subscription is not active",
            }

        # Validate currency
        if not config_service.is_currency_supported(currency):
            logger.warning(
                f"Currency {currency} not in supported list: {config.supported_currencies}"
            )

        # Get payment provider
        provider = get_payment_provider(payment_sub.provider)

        # Charge the authorization
        result = provider.charge_authorization(
            authorization_code=payment_sub.authorization_code,
            email=payment_sub.customer_email,
            amount=int(amount * 100),  # Convert to kobo/cents
            currency=currency,
            reference=idempotency_key,
            metadata={
                "payment_subscription_id": payment_subscription_id,
                "invoice_id": invoice_id,
                "description": description,
            },
        )

        # Update payment subscription stats
        payment_sub.total_charges += 1
        payment_sub.last_charge_date = datetime.now(timezone.utc)

        if result.get("status") == "success":
            payment_sub.successful_charges += 1
            payment_sub.total_collected += Decimal(str(amount))
            payment_sub.last_charge_status = "success"
            payment_sub.last_charge_reference = result.get("reference")
            payment_sub.retry_count = 0

            # Update invoice if linked
            if invoice_id:
                _update_invoice_paid(db, invoice_id, amount)

            db.commit()

            return {
                "success": True,
                "reference": result.get("reference"),
                "amount": amount,
                "currency": currency,
            }

        else:
            payment_sub.failed_charges += 1
            payment_sub.last_charge_status = "failed"
            payment_sub.retry_count += 1

            db.commit()

            # Check if we should retry using config
            if config_service.should_retry_charge(payment_sub.retry_count):
                # Get retry delay from config (with optional backoff)
                retry_delay = config_service.get_retry_interval_seconds(
                    payment_sub.retry_count
                )
                logger.info(
                    f"Scheduling charge retry in {retry_delay}s "
                    f"(attempt {payment_sub.retry_count}/{config.charge_max_retries})"
                )
                raise self.retry(countdown=retry_delay)

            # Max retries exceeded
            logger.warning(
                f"Max retries ({config.charge_max_retries}) exceeded for "
                f"payment subscription {payment_subscription_id}"
            )

            return {
                "success": False,
                "error": result.get("message", "Charge failed"),
                "gateway_response": result,
                "max_retries_exceeded": True,
            }

    except Exception as e:
        db.rollback()
        logger.error(
            f"Charge processing failed: {e}",
            extra={"payment_subscription_id": payment_subscription_id},
            exc_info=True,
        )
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=3600)
def retry_failed_charges(self, limit: int = 50):
    """
    Retry failed payment subscription charges.

    Finds payment subscriptions with failed charges that haven't
    exceeded max retries and attempts to charge again.
    Uses configurable retry settings from BillingConfigService.

    Args:
        limit: Maximum charges to retry.

    Returns:
        Dict with retry summary.
    """
    from app.models.payment_subscription import (
        PaymentSubscription,
        PaymentSubscriptionStatus,
    )
    from app.services.subscriptions.billing_config import BillingConfigService

    db = SessionLocal()
    try:
        # Load configuration
        config_service = BillingConfigService(db)
        config = config_service.get_config()

        # Check if retries are enabled
        if not config.enabled:
            logger.info("Billing is disabled globally, skipping retry task")
            return {"skipped": True, "reason": "billing_disabled"}

        if not config.charge_retry_enabled:
            logger.info("Charge retry is disabled, skipping")
            return {"skipped": True, "reason": "retry_disabled"}

        # Find retryable payment subscriptions using configured max retries
        retryable = (
            db.query(PaymentSubscription)
            .filter(
                PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE,
                PaymentSubscription.last_charge_status == "failed",
                PaymentSubscription.retry_count < config.charge_max_retries,
            )
            .limit(limit)
            .all()
        )

        results = {
            "total": len(retryable),
            "queued": 0,
            "skipped": 0,
            "max_retries_config": config.charge_max_retries,
        }

        for ps in retryable:
            try:
                # Use configured currency if subscription currency not set
                charge_currency = ps.currency or config.default_currency

                # Queue charge task
                process_subscription_charge.delay(
                    payment_subscription_id=ps.id,
                    amount=float(ps.amount),
                    currency=charge_currency,
                    description=f"Retry: {ps.plan_name}",
                    idempotency_key=f"retry-{ps.id}-{datetime.now().strftime('%Y%m%d%H')}",
                )
                results["queued"] += 1

            except Exception as e:
                logger.error(f"Failed to queue retry for {ps.id}: {e}")
                results["skipped"] += 1

        logger.info(
            f"Queued {results['queued']}/{results['total']} charge retries",
            extra=results,
        )

        return results

    except Exception as e:
        logger.error(f"Retry failed charges task failed: {e}", exc_info=True)
        raise self.retry(exc=e)

    finally:
        db.close()


# =============================================================================
# Invoice Tasks
# =============================================================================

@celery_app.task(bind=True)
def generate_subscription_invoice(
    self,
    subscription_id: int,
    period_start: str,
    period_end: str,
    amount: Optional[float] = None,
):
    """
    Generate an invoice for a subscription.

    Args:
        subscription_id: The subscription ID.
        period_start: Billing period start (YYYY-MM-DD).
        period_end: Billing period end (YYYY-MM-DD).
        amount: Optional override amount.

    Returns:
        Dict with invoice details.
    """
    from app.services.subscriptions import BillingService

    db = SessionLocal()
    try:
        service = BillingService(db)
        invoice = service.generate_subscription_invoice(
            subscription_id=subscription_id,
            billing_period_start=date.fromisoformat(period_start),
            billing_period_end=date.fromisoformat(period_end),
            amount=Decimal(str(amount)) if amount else None,
        )

        db.commit()

        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "status": invoice.status.value,
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"Invoice generation failed: {e}",
            extra={"subscription_id": subscription_id},
            exc_info=True,
        )
        raise

    finally:
        db.close()


@celery_app.task
def mark_overdue_invoices():
    """
    Mark invoices past due date as overdue.

    Uses configurable settings from BillingConfigService.
    Skips execution if overdue checking is disabled.

    Returns:
        Dict with update summary.
    """
    from app.models.invoice import Invoice, InvoiceStatus
    from app.services.subscriptions.billing_config import BillingConfigService

    db = SessionLocal()
    try:
        # Load configuration
        config_service = BillingConfigService(db)
        config = config_service.get_config()

        # Check if overdue checking is enabled
        if not config.enabled:
            logger.info("Billing is disabled globally, skipping overdue check")
            return {"skipped": True, "reason": "billing_disabled"}

        if not config.overdue_check_enabled:
            logger.info("Overdue invoice checking is disabled, skipping")
            return {"skipped": True, "reason": "overdue_check_disabled"}

        now = datetime.now(timezone.utc)

        updated = (
            db.query(Invoice)
            .filter(
                Invoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.PARTIALLY_PAID,
                ]),
                Invoice.due_date < now,
            )
            .update(
                {Invoice.status: InvoiceStatus.OVERDUE},
                synchronize_session=False,
            )
        )

        db.commit()

        logger.info(f"Marked {updated} invoices as overdue")

        return {"updated_count": updated}

    except Exception as e:
        db.rollback()
        logger.error(f"Mark overdue invoices failed: {e}", exc_info=True)
        raise

    finally:
        db.close()


# =============================================================================
# Scheduled Task Registration
# =============================================================================

# Note: Celery Beat schedules are registered at startup and cannot be changed
# dynamically without celery-redbeat or similar extension. We use a "fallback"
# schedule approach:
#
# 1. Tasks are registered with reasonable default schedules
# 2. Each task checks BillingConfigService on execution
# 3. Tasks skip execution if disabled in config
# 4. For fully dynamic schedules (change without restart), consider:
#    - celery-redbeat: Store schedules in Redis
#    - celery-beat-database: Store schedules in database
#    - django-celery-beat: If using Django
#
# The current approach means:
# - Schedules define "check times" (when task runs and checks config)
# - Config defines "enabled" flags (whether task executes or skips)
# - This provides flexibility without additional dependencies


def _load_billing_schedules():
    """Load billing schedules from configuration.

    Returns default schedules if database is not available.
    Used during Celery Beat initialization.
    """
    try:
        from app.services.subscriptions.billing_config import BillingConfigService
        db = SessionLocal()
        try:
            config_service = BillingConfigService(db)
            config = config_service.get_config()
            return {
                "daily_billing": {
                    "hour": config.daily_billing_hour,
                    "minute": config.daily_billing_minute,
                },
                "monthly_billing": {
                    "day_of_month": config.monthly_billing_day,
                    "hour": config.monthly_billing_hour,
                    "minute": 0,
                },
                "overdue_check": {
                    "hour": config.overdue_check_hour,
                    "minute": 0,
                },
                "retry_interval_hours": config.charge_retry_interval_hours,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not load billing schedules from DB: {e}, using defaults")
        return {
            "daily_billing": {"hour": 1, "minute": 0},
            "monthly_billing": {"day_of_month": 1, "hour": 2, "minute": 0},
            "overdue_check": {"hour": 6, "minute": 0},
            "retry_interval_hours": 4,
        }


@celery_app.on_after_configure.connect
def setup_periodic_billing_tasks(sender, **kwargs):
    """Register periodic billing tasks with Celery Beat.

    Schedules are loaded from BillingConfigService at startup.
    Each task checks config on execution and skips if disabled.
    """
    schedules = _load_billing_schedules()

    # Daily billing - default 1:00 AM, configurable
    sender.add_periodic_task(
        crontab(
            hour=schedules["daily_billing"]["hour"],
            minute=schedules["daily_billing"]["minute"],
        ),
        run_daily_billing.s(),
        name="daily-billing-run",
    )

    # Monthly billing - default 1st of month at 2:00 AM, configurable
    sender.add_periodic_task(
        crontab(
            day_of_month=schedules["monthly_billing"]["day_of_month"],
            hour=schedules["monthly_billing"]["hour"],
            minute=schedules["monthly_billing"]["minute"],
        ),
        run_monthly_billing.s(),
        name="monthly-billing-run",
    )

    # Mark overdue invoices - default 6:00 AM, configurable
    sender.add_periodic_task(
        crontab(
            hour=schedules["overdue_check"]["hour"],
            minute=schedules["overdue_check"]["minute"],
        ),
        mark_overdue_invoices.s(),
        name="mark-overdue-invoices",
    )

    # Retry failed charges - based on configured interval
    retry_hours = schedules["retry_interval_hours"]
    sender.add_periodic_task(
        crontab(hour=f"*/{retry_hours}", minute=30),
        retry_failed_charges.s(),
        name="retry-failed-charges",
    )

    logger.info(
        "Registered billing periodic tasks",
        extra={
            "daily_billing": schedules["daily_billing"],
            "monthly_billing": schedules["monthly_billing"],
            "overdue_check": schedules["overdue_check"],
            "retry_interval_hours": retry_hours,
        },
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _update_invoice_paid(db, invoice_id: int, amount: float) -> None:
    """Update invoice as paid after successful charge."""
    from app.models.invoice import Invoice, InvoiceStatus

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice:
        prior_balance = (
            invoice.balance
            if invoice.balance is not None
            else (invoice.total_amount - (invoice.amount_paid or Decimal("0")))
        )
        invoice.amount_paid += Decimal(str(amount))
        invoice.balance = prior_balance - Decimal(str(amount))

        if invoice.amount_paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_date = datetime.now(timezone.utc)
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
