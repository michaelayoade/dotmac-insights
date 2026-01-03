"""
Subscription Provisioner

Central orchestrator for provisioning subscriptions to MikroTik routers.
Handles status transitions, access method selection, RADIUS sync, and logging.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.integrations.mikrotik.client import MikroTikClient
from app.integrations.mikrotik.access_methods import get_access_method
from app.integrations.mikrotik.radius import RADIUSService
from app.integrations.mikrotik.exceptions import (
    ProvisioningError,
    DeprovisioningError,
    DisconnectError,
    MikroTikError,
)
from app.models.provisioning_log import (
    ProvisioningLog,
    ProvisioningAction,
    ProvisioningStatus,
)
from app.sync.base import get_circuit_breaker, CircuitBreakerOpenError

if TYPE_CHECKING:
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.router import Router

logger = logging.getLogger(__name__)


class SubscriptionProvisioner:
    """
    Handles subscription provisioning to MikroTik routers.

    Responsibilities:
    - Select appropriate access method based on subscription.access_method
    - Provision/deprovision on router via MikroTik API
    - Sync credentials and rate limits to RADIUS
    - Log all operations for audit trail
    - Handle errors and retries

    Usage:
        provisioner = SubscriptionProvisioner(db)
        await provisioner.provision(subscription)
        await provisioner.on_status_change(subscription, old_status, new_status)
    """

    def __init__(
        self,
        db: Session,
        *,
        radius_db: Optional[Session] = None,
        triggered_by: str = "system",
    ):
        """
        Initialize the provisioner.

        Args:
            db: Main application database session
            radius_db: Optional separate RADIUS database session
            triggered_by: Source of the trigger (user, system, celery, etc.)
        """
        self.db = db
        self.radius_db = radius_db or db  # Use same DB if not separate
        self.triggered_by = triggered_by
        self._circuit_breaker = get_circuit_breaker("mikrotik")

    async def provision(
        self,
        subscription: Subscription,
        *,
        force: bool = False,
    ) -> ProvisioningLog:
        """
        Provision a subscription on its assigned router.

        Creates the necessary resources on the router to allow
        the subscriber to connect.

        Args:
            subscription: Subscription to provision
            force: Force re-provisioning even if already provisioned

        Returns:
            ProvisioningLog record

        Raises:
            ProvisioningError: If provisioning fails
        """
        # Validate
        if not subscription.router_id:
            raise ProvisioningError(
                "No router assigned to subscription",
                subscription_id=subscription.id,
            )

        if not subscription.access_method:
            raise ProvisioningError(
                "No access method specified",
                subscription_id=subscription.id,
            )

        router = self.db.get(Router, subscription.router_id)
        if not router:
            raise ProvisioningError(
                f"Router {subscription.router_id} not found",
                subscription_id=subscription.id,
            )

        # Get access method handler
        access_method = get_access_method(subscription.access_method)
        if not access_method:
            raise ProvisioningError(
                f"Unknown access method: {subscription.access_method}",
                subscription_id=subscription.id,
            )

        # Create log entry
        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=router.id,
            action=ProvisioningAction.CREATE,
            access_method=subscription.access_method,
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            # Check circuit breaker
            if self._circuit_breaker.is_open():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker open for router {router.title}"
                )

            # Provision on router
            async with MikroTikClient(router) as client:
                result = await self._circuit_breaker.execute(
                    access_method.provision(client, subscription)
                )

            # Update RADIUS
            if subscription.ppp_username:
                radius_service = RADIUSService(self.radius_db)
                await radius_service.create_user(
                    username=subscription.ppp_username,
                    password=subscription.ppp_password or "",
                    download_speed=subscription.download_speed,
                    upload_speed=subscription.upload_speed,
                    ip_address=subscription.ipv4_address,
                    subscription_id=subscription.id,
                )

            # Update subscription state
            subscription.provisioned_at = datetime.utcnow()
            subscription.provisioning_error = None

            # Mark log as success
            log.mark_success(json.dumps(result) if result else None)
            self.db.commit()

            logger.info(
                "Subscription provisioned",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                    "access_method": subscription.access_method,
                },
            )

            return log

        except Exception as e:
            # Mark log as failed
            log.mark_failed(str(e), type(e).__name__)
            subscription.provisioning_error = str(e)[:500]
            self.db.commit()

            logger.error(
                f"Provisioning failed: {e}",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                },
            )

            raise ProvisioningError(
                str(e),
                subscription_id=subscription.id,
                access_method=subscription.access_method,
                router_id=router.id,
            )

    async def deprovision(
        self,
        subscription: Subscription,
    ) -> ProvisioningLog:
        """
        Remove a subscription from its router.

        Deletes all resources associated with the subscriber.

        Args:
            subscription: Subscription to deprovision

        Returns:
            ProvisioningLog record

        Raises:
            DeprovisioningError: If deprovisioning fails
        """
        if not subscription.router_id:
            logger.warning(
                "No router assigned, nothing to deprovision",
                extra={"subscription_id": subscription.id},
            )
            # Return a success log
            log = ProvisioningLog(
                subscription_id=subscription.id,
                router_id=0,
                action=ProvisioningAction.DELETE,
                access_method=subscription.access_method or "unknown",
                status=ProvisioningStatus.SUCCESS,
                triggered_by=self.triggered_by,
            )
            self.db.add(log)
            self.db.commit()
            return log

        router = self.db.get(Router, subscription.router_id)
        if not router:
            raise DeprovisioningError(
                f"Router {subscription.router_id} not found",
                subscription_id=subscription.id,
            )

        access_method = get_access_method(subscription.access_method or "pppoe")
        if not access_method:
            raise DeprovisioningError(
                f"Unknown access method: {subscription.access_method}",
                subscription_id=subscription.id,
            )

        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=router.id,
            action=ProvisioningAction.DELETE,
            access_method=subscription.access_method or "unknown",
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            async with MikroTikClient(router) as client:
                await self._circuit_breaker.execute(
                    access_method.deprovision(client, subscription)
                )

            # Delete from RADIUS
            if subscription.ppp_username:
                radius_service = RADIUSService(self.radius_db)
                await radius_service.delete_user(subscription.ppp_username)

            # Clear provisioning state
            subscription.provisioned_at = None
            subscription.provisioning_error = None

            log.mark_success()
            self.db.commit()

            logger.info(
                "Subscription deprovisioned",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                },
            )

            return log

        except Exception as e:
            log.mark_failed(str(e), type(e).__name__)
            self.db.commit()

            logger.error(
                f"Deprovisioning failed: {e}",
                extra={"subscription_id": subscription.id},
            )

            raise DeprovisioningError(
                str(e),
                subscription_id=subscription.id,
                router_id=router.id,
            )

    async def suspend(
        self,
        subscription: Subscription,
    ) -> ProvisioningLog:
        """
        Suspend a subscription.

        Disconnects the active session and optionally blocks
        re-authentication in RADIUS.

        Args:
            subscription: Subscription to suspend

        Returns:
            ProvisioningLog record
        """
        if not subscription.router_id:
            log = ProvisioningLog(
                subscription_id=subscription.id,
                router_id=0,
                action=ProvisioningAction.SUSPEND,
                access_method=subscription.access_method or "unknown",
                status=ProvisioningStatus.SUCCESS,
                triggered_by=self.triggered_by,
            )
            self.db.add(log)
            self.db.commit()
            return log

        router = self.db.get(Router, subscription.router_id)
        if not router:
            raise ProvisioningError(
                f"Router {subscription.router_id} not found",
                subscription_id=subscription.id,
            )

        access_method = get_access_method(subscription.access_method or "pppoe")

        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=router.id,
            action=ProvisioningAction.SUSPEND,
            access_method=subscription.access_method or "unknown",
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            async with MikroTikClient(router) as client:
                # Disconnect active session
                if access_method:
                    await access_method.disconnect(client, subscription)

            # Suspend in RADIUS
            if subscription.ppp_username:
                radius_service = RADIUSService(self.radius_db)
                await radius_service.suspend_user(subscription.ppp_username)

            log.mark_success()
            self.db.commit()

            logger.info(
                "Subscription suspended",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                },
            )

            return log

        except Exception as e:
            log.mark_failed(str(e), type(e).__name__)
            self.db.commit()

            logger.error(
                f"Suspend failed: {e}",
                extra={"subscription_id": subscription.id},
            )

            raise

    async def unsuspend(
        self,
        subscription: Subscription,
    ) -> ProvisioningLog:
        """
        Unsuspend a subscription.

        Re-enables authentication in RADIUS.

        Args:
            subscription: Subscription to unsuspend

        Returns:
            ProvisioningLog record
        """
        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=subscription.router_id or 0,
            action=ProvisioningAction.UNSUSPEND,
            access_method=subscription.access_method or "unknown",
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            # Unsuspend in RADIUS
            if subscription.ppp_username:
                radius_service = RADIUSService(self.radius_db)
                await radius_service.unsuspend_user(subscription.ppp_username)

            log.mark_success()
            self.db.commit()

            logger.info(
                "Subscription unsuspended",
                extra={"subscription_id": subscription.id},
            )

            return log

        except Exception as e:
            log.mark_failed(str(e), type(e).__name__)
            self.db.commit()

            logger.error(
                f"Unsuspend failed: {e}",
                extra={"subscription_id": subscription.id},
            )

            raise

    async def disconnect(
        self,
        subscription: Subscription,
    ) -> ProvisioningLog:
        """
        Disconnect an active session without deprovisioning.

        Used for forcing reconnect or temporary disconnection.

        Args:
            subscription: Subscription to disconnect

        Returns:
            ProvisioningLog record
        """
        if not subscription.router_id:
            raise DisconnectError(
                "No router assigned",
                subscription_id=subscription.id,
            )

        router = self.db.get(Router, subscription.router_id)
        if not router:
            raise DisconnectError(
                f"Router {subscription.router_id} not found",
                subscription_id=subscription.id,
            )

        access_method = get_access_method(subscription.access_method or "pppoe")

        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=router.id,
            action=ProvisioningAction.DISCONNECT,
            access_method=subscription.access_method or "unknown",
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            async with MikroTikClient(router) as client:
                if access_method:
                    await access_method.disconnect(client, subscription)

            log.mark_success()
            self.db.commit()

            logger.info(
                "Session disconnected",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                },
            )

            return log

        except Exception as e:
            log.mark_failed(str(e), type(e).__name__)
            self.db.commit()

            raise DisconnectError(
                str(e),
                subscription_id=subscription.id,
                router_id=router.id,
            )

    async def update(
        self,
        subscription: Subscription,
    ) -> ProvisioningLog:
        """
        Update an existing provisioned subscription.

        Updates router config and RADIUS with new values.

        Args:
            subscription: Subscription with updated values

        Returns:
            ProvisioningLog record
        """
        if not subscription.router_id:
            raise ProvisioningError(
                "No router assigned",
                subscription_id=subscription.id,
            )

        router = self.db.get(Router, subscription.router_id)
        if not router:
            raise ProvisioningError(
                f"Router {subscription.router_id} not found",
                subscription_id=subscription.id,
            )

        access_method = get_access_method(subscription.access_method or "pppoe")

        log = ProvisioningLog(
            subscription_id=subscription.id,
            router_id=router.id,
            action=ProvisioningAction.UPDATE,
            access_method=subscription.access_method or "unknown",
            status=ProvisioningStatus.PENDING,
            triggered_by=self.triggered_by,
        )
        self.db.add(log)
        self.db.commit()

        try:
            async with MikroTikClient(router) as client:
                if access_method:
                    result = await access_method.update(client, subscription)

            # Update RADIUS
            if subscription.ppp_username:
                radius_service = RADIUSService(self.radius_db)
                await radius_service.update_user(
                    subscription.ppp_username,
                    password=subscription.ppp_password,
                    download_speed=subscription.download_speed,
                    upload_speed=subscription.upload_speed,
                    ip_address=subscription.ipv4_address,
                )

            log.mark_success(json.dumps(result) if result else None)
            self.db.commit()

            logger.info(
                "Subscription updated",
                extra={
                    "subscription_id": subscription.id,
                    "router_id": router.id,
                },
            )

            return log

        except Exception as e:
            log.mark_failed(str(e), type(e).__name__)
            self.db.commit()

            raise ProvisioningError(
                str(e),
                subscription_id=subscription.id,
                router_id=router.id,
            )

    async def on_status_change(
        self,
        subscription: Subscription,
        old_status: SubscriptionStatus,
        new_status: SubscriptionStatus,
    ) -> Optional[ProvisioningLog]:
        """
        Handle subscription status transitions.

        Called when a subscription's status changes. Determines
        the appropriate provisioning action.

        Args:
            subscription: The subscription
            old_status: Previous status
            new_status: New status

        Returns:
            ProvisioningLog if action was taken, None otherwise
        """
        from app.models.subscription import SubscriptionStatus

        logger.info(
            "Processing status change",
            extra={
                "subscription_id": subscription.id,
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        # PENDING -> ACTIVE: First-time provisioning
        if old_status == SubscriptionStatus.PENDING and new_status == SubscriptionStatus.ACTIVE:
            return await self.provision(subscription)

        # SUSPENDED -> ACTIVE: Unsuspend
        if old_status == SubscriptionStatus.SUSPENDED and new_status == SubscriptionStatus.ACTIVE:
            return await self.unsuspend(subscription)

        # ACTIVE -> SUSPENDED: Suspend
        if old_status == SubscriptionStatus.ACTIVE and new_status == SubscriptionStatus.SUSPENDED:
            return await self.suspend(subscription)

        # * -> CANCELLED: Deprovision
        if new_status == SubscriptionStatus.CANCELLED:
            return await self.deprovision(subscription)

        # No action needed
        return None

    async def get_session_info(
        self,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """
        Get active session information for a subscription.

        Args:
            subscription: Subscription to check

        Returns:
            Session info dict or None if no active session
        """
        if not subscription.router_id:
            return None

        router = self.db.get(Router, subscription.router_id)
        if not router:
            return None

        access_method = get_access_method(subscription.access_method or "pppoe")
        if not access_method:
            return None

        try:
            async with MikroTikClient(router) as client:
                return await access_method.get_session(client, subscription)
        except Exception as e:
            logger.warning(f"Failed to get session info: {e}")
            return None

    async def test_router_connection(
        self,
        router: Router,
    ) -> Dict[str, Any]:
        """
        Test connection to a router.

        Args:
            router: Router to test

        Returns:
            Dict with connection status and system info
        """
        try:
            async with MikroTikClient(router) as client:
                await client.test_connection()
                system_info = await client.get_system_info()

            return {
                "connected": True,
                "router_id": router.id,
                "system_info": system_info,
            }

        except Exception as e:
            return {
                "connected": False,
                "router_id": router.id,
                "error": str(e),
            }


# Type alias for Router model
from app.models.router import Router
