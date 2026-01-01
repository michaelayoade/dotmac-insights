"""
Celery tasks for MikroTik subscription provisioning.

These tasks handle asynchronous provisioning operations triggered by
subscription status changes or manual user actions.
"""

import asyncio
from datetime import datetime
from typing import Optional
import structlog

from app.worker import celery_app
from app.database import SessionLocal
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.router import Router
from app.integrations.mikrotik.provisioner import SubscriptionProvisioner
from app.integrations.mikrotik.exceptions import (
    ProvisioningError,
    DeprovisioningError,
    DisconnectError,
    MikroTikError,
)

logger = structlog.get_logger()


def run_async(coro):
    """Run async coroutine in sync context for Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_subscription_status_change(
    self,
    subscription_id: int,
    old_status: str,
    new_status: str,
    triggered_by: str = "system",
):
    """
    Process a subscription status change.

    Called when a subscription's status changes. Determines and executes
    the appropriate provisioning action.

    Args:
        subscription_id: ID of the subscription
        old_status: Previous status value
        new_status: New status value
        triggered_by: Source of the trigger (user, system, etc.)

    Returns:
        Dict with result status
    """
    task_name = "process_subscription_status_change"
    logger.info(
        "task_started",
        task=task_name,
        subscription_id=subscription_id,
        old_status=old_status,
        new_status=new_status,
    )

    db = SessionLocal()
    try:
        subscription = db.get(Subscription, subscription_id)
        if not subscription:
            logger.error("subscription_not_found", subscription_id=subscription_id)
            return {"status": "error", "reason": "subscription_not_found"}

        # Skip if subscription has no router or access method
        if not subscription.router_id:
            logger.info(
                "skipping_no_router",
                subscription_id=subscription_id,
            )
            return {"status": "skipped", "reason": "no_router_assigned"}

        if not subscription.access_method:
            logger.info(
                "skipping_no_access_method",
                subscription_id=subscription_id,
            )
            return {"status": "skipped", "reason": "no_access_method"}

        # Parse status enums
        try:
            old_status_enum = SubscriptionStatus(old_status)
            new_status_enum = SubscriptionStatus(new_status)
        except ValueError as e:
            logger.error("invalid_status", error=str(e))
            return {"status": "error", "reason": "invalid_status"}

        # Create provisioner and process
        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)
        log = run_async(
            provisioner.on_status_change(subscription, old_status_enum, new_status_enum)
        )

        if log:
            logger.info(
                "task_completed",
                task=task_name,
                subscription_id=subscription_id,
                action=log.action.value,
                status=log.status.value,
            )
            return {
                "status": "success",
                "subscription_id": subscription_id,
                "action": log.action.value,
                "provisioning_status": log.status.value,
                "log_id": log.id,
            }
        else:
            logger.info(
                "task_completed_no_action",
                task=task_name,
                subscription_id=subscription_id,
            )
            return {
                "status": "success",
                "subscription_id": subscription_id,
                "action": "none",
            }

    except MikroTikError as e:
        logger.error(
            "provisioning_error",
            task=task_name,
            subscription_id=subscription_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Retry with exponential backoff
        countdown = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=e, countdown=countdown)

    except Exception as e:
        logger.error(
            "task_failed",
            task=task_name,
            subscription_id=subscription_id,
            error=str(e),
        )
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def provision_subscription(
    self,
    subscription_id: int,
    triggered_by: str = "system",
    force: bool = False,
):
    """
    Provision a subscription on its assigned router.

    Args:
        subscription_id: ID of the subscription to provision
        triggered_by: Source of the trigger
        force: Force re-provisioning even if already provisioned

    Returns:
        Dict with result status
    """
    task_name = "provision_subscription"
    logger.info(
        "task_started",
        task=task_name,
        subscription_id=subscription_id,
        force=force,
    )

    db = SessionLocal()
    try:
        subscription = db.get(Subscription, subscription_id)
        if not subscription:
            return {"status": "error", "reason": "subscription_not_found"}

        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)
        log = run_async(provisioner.provision(subscription, force=force))

        logger.info(
            "task_completed",
            task=task_name,
            subscription_id=subscription_id,
            status=log.status.value,
        )

        return {
            "status": "success",
            "subscription_id": subscription_id,
            "provisioning_status": log.status.value,
            "log_id": log.id,
        }

    except MikroTikError as e:
        logger.error(
            "provisioning_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def deprovision_subscription(
    self,
    subscription_id: int,
    triggered_by: str = "system",
):
    """
    Deprovision a subscription from its router.

    Args:
        subscription_id: ID of the subscription to deprovision
        triggered_by: Source of the trigger

    Returns:
        Dict with result status
    """
    task_name = "deprovision_subscription"
    logger.info(
        "task_started",
        task=task_name,
        subscription_id=subscription_id,
    )

    db = SessionLocal()
    try:
        subscription = db.get(Subscription, subscription_id)
        if not subscription:
            return {"status": "error", "reason": "subscription_not_found"}

        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)
        log = run_async(provisioner.deprovision(subscription))

        logger.info(
            "task_completed",
            task=task_name,
            subscription_id=subscription_id,
            status=log.status.value,
        )

        return {
            "status": "success",
            "subscription_id": subscription_id,
            "provisioning_status": log.status.value,
            "log_id": log.id,
        }

    except MikroTikError as e:
        logger.error(
            "deprovisioning_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=15)
def disconnect_subscription_session(
    self,
    subscription_id: int,
    triggered_by: str = "system",
):
    """
    Disconnect an active session for a subscription.

    Used for forcing reconnect or as part of suspension.

    Args:
        subscription_id: ID of the subscription
        triggered_by: Source of the trigger

    Returns:
        Dict with result status
    """
    task_name = "disconnect_subscription_session"
    logger.info(
        "task_started",
        task=task_name,
        subscription_id=subscription_id,
    )

    db = SessionLocal()
    try:
        subscription = db.get(Subscription, subscription_id)
        if not subscription:
            return {"status": "error", "reason": "subscription_not_found"}

        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)
        log = run_async(provisioner.disconnect(subscription))

        logger.info(
            "task_completed",
            task=task_name,
            subscription_id=subscription_id,
            status=log.status.value,
        )

        return {
            "status": "success",
            "subscription_id": subscription_id,
            "provisioning_status": log.status.value,
            "log_id": log.id,
        }

    except MikroTikError as e:
        logger.error(
            "disconnect_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        raise self.retry(exc=e)

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def update_subscription_provisioning(
    self,
    subscription_id: int,
    triggered_by: str = "system",
):
    """
    Update an existing provisioned subscription.

    Called when subscription details change (IP, speed, etc.).

    Args:
        subscription_id: ID of the subscription
        triggered_by: Source of the trigger

    Returns:
        Dict with result status
    """
    task_name = "update_subscription_provisioning"
    logger.info(
        "task_started",
        task=task_name,
        subscription_id=subscription_id,
    )

    db = SessionLocal()
    try:
        subscription = db.get(Subscription, subscription_id)
        if not subscription:
            return {"status": "error", "reason": "subscription_not_found"}

        # Only update if currently provisioned
        if not subscription.provisioned_at:
            logger.info(
                "skipping_not_provisioned",
                subscription_id=subscription_id,
            )
            return {"status": "skipped", "reason": "not_provisioned"}

        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)
        log = run_async(provisioner.update(subscription))

        logger.info(
            "task_completed",
            task=task_name,
            subscription_id=subscription_id,
            status=log.status.value,
        )

        return {
            "status": "success",
            "subscription_id": subscription_id,
            "provisioning_status": log.status.value,
            "log_id": log.id,
        }

    except MikroTikError as e:
        logger.error(
            "update_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def test_router_connection(
    self,
    router_id: int,
):
    """
    Test connection to a router.

    Args:
        router_id: ID of the router to test

    Returns:
        Dict with connection status and system info
    """
    task_name = "test_router_connection"
    logger.info("task_started", task=task_name, router_id=router_id)

    db = SessionLocal()
    try:
        router = db.get(Router, router_id)
        if not router:
            return {"status": "error", "reason": "router_not_found"}

        provisioner = SubscriptionProvisioner(db)
        result = run_async(provisioner.test_router_connection(router))

        logger.info(
            "task_completed",
            task=task_name,
            router_id=router_id,
            connected=result.get("connected"),
        )

        return result

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {
            "status": "error",
            "router_id": router_id,
            "error": str(e),
        }

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def retry_failed_provisioning(
    self,
    log_id: int,
    triggered_by: str = "system",
):
    """
    Retry a failed provisioning operation.

    Args:
        log_id: ID of the ProvisioningLog to retry
        triggered_by: Source of the trigger

    Returns:
        Dict with result status
    """
    from app.models.provisioning_log import ProvisioningLog, ProvisioningAction

    task_name = "retry_failed_provisioning"
    logger.info("task_started", task=task_name, log_id=log_id)

    db = SessionLocal()
    try:
        log = db.get(ProvisioningLog, log_id)
        if not log:
            return {"status": "error", "reason": "log_not_found"}

        if not log.can_retry:
            return {"status": "error", "reason": "cannot_retry"}

        subscription = db.get(Subscription, log.subscription_id)
        if not subscription:
            return {"status": "error", "reason": "subscription_not_found"}

        # Mark original log as retrying
        log.mark_retrying()
        db.commit()

        provisioner = SubscriptionProvisioner(db, triggered_by=triggered_by)

        # Execute the appropriate action
        new_log = None
        if log.action == ProvisioningAction.CREATE:
            new_log = run_async(provisioner.provision(subscription, force=True))
        elif log.action == ProvisioningAction.DELETE:
            new_log = run_async(provisioner.deprovision(subscription))
        elif log.action == ProvisioningAction.UPDATE:
            new_log = run_async(provisioner.update(subscription))
        elif log.action == ProvisioningAction.DISCONNECT:
            new_log = run_async(provisioner.disconnect(subscription))
        elif log.action == ProvisioningAction.SUSPEND:
            new_log = run_async(provisioner.suspend(subscription))
        elif log.action == ProvisioningAction.UNSUSPEND:
            new_log = run_async(provisioner.unsuspend(subscription))

        if new_log:
            logger.info(
                "task_completed",
                task=task_name,
                log_id=log_id,
                new_log_id=new_log.id,
                status=new_log.status.value,
            )
            return {
                "status": "success",
                "original_log_id": log_id,
                "new_log_id": new_log.id,
                "provisioning_status": new_log.status.value,
            }
        else:
            return {"status": "error", "reason": "unknown_action"}

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@celery_app.task
def bulk_provision_subscriptions(
    subscription_ids: list[int],
    triggered_by: str = "system",
):
    """
    Provision multiple subscriptions.

    Queues individual provisioning tasks for each subscription.

    Args:
        subscription_ids: List of subscription IDs to provision
        triggered_by: Source of the trigger

    Returns:
        Dict with queued task info
    """
    logger.info(
        "bulk_provision_started",
        count=len(subscription_ids),
        triggered_by=triggered_by,
    )

    queued = []
    for sub_id in subscription_ids:
        result = provision_subscription.delay(sub_id, triggered_by=triggered_by)
        queued.append({"subscription_id": sub_id, "task_id": result.id})

    logger.info("bulk_provision_queued", count=len(queued))

    return {
        "status": "queued",
        "count": len(queued),
        "tasks": queued,
    }
