"""
Subscription Event Handlers

SQLAlchemy event listeners that trigger provisioning tasks
when subscription status changes.
"""

from __future__ import annotations

import structlog
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionStatus

logger = structlog.get_logger()

# Track whether events are registered to avoid duplicate registration
_events_registered = False


def on_subscription_status_change(
    target: Subscription,
    value: SubscriptionStatus,
    oldvalue: SubscriptionStatus,
    initiator,
):
    """
    Handle subscription status change events.

    Triggered when a subscription's status field is set to a new value.
    Queues a Celery task to handle provisioning operations.

    Args:
        target: The Subscription instance
        value: The new status value
        oldvalue: The previous status value
        initiator: SQLAlchemy attribute change initiator
    """
    # Skip if no actual change or if this is initial load
    if value == oldvalue:
        return

    # Skip NEVER_SET (initial object creation before status is set)
    if oldvalue is None or oldvalue is inspect(target).attrs.status.history.unchanged:
        return

    # Skip if both are the same enum or string value
    old_val = oldvalue.value if isinstance(oldvalue, SubscriptionStatus) else str(oldvalue)
    new_val = value.value if isinstance(value, SubscriptionStatus) else str(value)

    if old_val == new_val:
        return

    logger.info(
        "subscription_status_change_detected",
        subscription_id=target.id,
        old_status=old_val,
        new_status=new_val,
    )

    # Queue provisioning task (import here to avoid circular imports)
    # The task will be executed asynchronously by Celery
    try:
        from app.tasks.provisioning_tasks import process_subscription_status_change

        # Determine trigger source
        triggered_by = "system"

        # Delay the task - it will run in the background
        result = process_subscription_status_change.delay(
            subscription_id=target.id,
            old_status=old_val,
            new_status=new_val,
            triggered_by=triggered_by,
        )

        logger.info(
            "provisioning_task_queued",
            subscription_id=target.id,
            task_id=result.id,
            old_status=old_val,
            new_status=new_val,
        )

    except Exception as e:
        # Don't fail the transaction if queuing fails
        logger.error(
            "failed_to_queue_provisioning_task",
            subscription_id=target.id,
            error=str(e),
        )


def on_subscription_after_update(mapper, connection, target: Subscription):
    """
    Handle subscription updates after they are committed.

    This is useful for detecting changes that require re-provisioning,
    such as IP address changes or speed changes.
    """
    # Get the session state
    state = inspect(target)

    # Check if key provisioning fields changed
    changed_fields = []

    for attr_name in ["ipv4_address", "ipv6_address", "download_speed", "upload_speed", "router_id"]:
        hist = state.attrs[attr_name].history
        if hist.has_changes():
            changed_fields.append(attr_name)

    if changed_fields and target.provisioned_at:
        logger.info(
            "subscription_provisioning_fields_changed",
            subscription_id=target.id,
            changed_fields=changed_fields,
        )

        try:
            from app.tasks.provisioning_tasks import update_subscription_provisioning

            result = update_subscription_provisioning.delay(
                subscription_id=target.id,
                triggered_by="field_change",
            )

            logger.info(
                "update_provisioning_task_queued",
                subscription_id=target.id,
                task_id=result.id,
                changed_fields=changed_fields,
            )

        except Exception as e:
            logger.error(
                "failed_to_queue_update_task",
                subscription_id=target.id,
                error=str(e),
            )


def register_subscription_events():
    """
    Register SQLAlchemy event listeners for subscription model.

    This should be called during application startup.
    Safe to call multiple times - will only register once.
    """
    global _events_registered

    if _events_registered:
        logger.debug("subscription_events_already_registered")
        return

    # Listen for status attribute changes
    event.listen(
        Subscription.status,
        "set",
        on_subscription_status_change,
        propagate=True,
    )

    # Listen for after_update to catch field changes
    event.listen(
        Subscription,
        "after_update",
        on_subscription_after_update,
    )

    _events_registered = True
    logger.info("subscription_events_registered")


def unregister_subscription_events():
    """
    Unregister SQLAlchemy event listeners.

    Useful for testing to avoid event duplication.
    """
    global _events_registered

    if not _events_registered:
        return

    try:
        event.remove(
            Subscription.status,
            "set",
            on_subscription_status_change,
        )
        event.remove(
            Subscription,
            "after_update",
            on_subscription_after_update,
        )
    except Exception:
        pass

    _events_registered = False
    logger.info("subscription_events_unregistered")
