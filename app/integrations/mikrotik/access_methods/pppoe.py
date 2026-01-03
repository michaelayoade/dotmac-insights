"""
PPPoE Access Method

Manages PPPoE secrets on MikroTik routers for subscriber authentication.
PPPoE is the most common access method for DSL and fiber connections.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from app.integrations.mikrotik.access_methods.base import AccessMethod
from app.integrations.mikrotik.exceptions import (
    ProvisioningError,
    DeprovisioningError,
    ResourceExistsError,
    ResourceNotFoundError,
)

if TYPE_CHECKING:
    from app.integrations.mikrotik.client import MikroTikClient
    from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class PPPoEAccessMethod(AccessMethod):
    """
    PPPoE (Point-to-Point Protocol over Ethernet) access method.

    Creates PPPoE secrets on the router. When a subscriber connects,
    the router authenticates against the secret (or forwards to RADIUS).

    Typical flow:
    1. Subscriber's CPE initiates PPPoE discovery
    2. Router finds matching secret and authenticates
    3. If using RADIUS profile, router queries RADIUS for rate limits
    4. PPP session established with assigned IP
    """

    method_name = "pppoe"
    label = "PPPoE"
    requires_credentials = True
    requires_mac = False

    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Create PPPoE secret for the subscriber."""
        self.validate_subscription(subscription)
        if not subscription.ppp_username or not subscription.ppp_password:
            raise ProvisioningError(
                "PPPoE username/password required for provisioning",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )
        username = subscription.ppp_username
        password = subscription.ppp_password

        try:
            result = await client.create_ppp_secret(
                name=username,
                password=password,
                service="pppoe",
                profile="radius",  # Use RADIUS for bandwidth control
                remote_address=subscription.ipv4_address,
                comment=self.get_comment(subscription),
                disabled=False,
            )

            logger.info(
                "PPPoE secret created",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                    "router_id": client.router_id,
                },
            )

            return {
                "action": "created",
                "resource": "ppp/secret",
                "name": username,
                "mikrotik_id": result.get(".id"),
            }

        except ResourceExistsError:
            # Secret already exists - update it instead
            logger.info(
                "PPPoE secret exists, updating",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                },
            )
            return await self.update(client, subscription)

        except Exception as e:
            raise ProvisioningError(
                f"Failed to create PPPoE secret: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Remove PPPoE secret and disconnect any active session."""
        if not subscription.ppp_username:
            return True  # Nothing to deprovision

        try:
            # First disconnect any active session
            await self.disconnect(client, subscription)

            # Then delete the secret
            deleted = await client.delete_ppp_secret(subscription.ppp_username)

            if deleted:
                logger.info(
                    "PPPoE secret deleted",
                    extra={
                        "subscription_id": subscription.id,
                        "username": subscription.ppp_username,
                        "router_id": client.router_id,
                    },
                )

            return True

        except ResourceNotFoundError:
            # Already deleted
            return True

        except Exception as e:
            raise DeprovisioningError(
                f"Failed to delete PPPoE secret: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Update existing PPPoE secret."""
        self.validate_subscription(subscription)
        if not subscription.ppp_username or not subscription.ppp_password:
            raise ProvisioningError(
                "PPPoE username/password required for update",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )
        username = subscription.ppp_username
        password = subscription.ppp_password

        try:
            secret = await client.get_ppp_secret(username)

            if not secret:
                # Secret doesn't exist - create it
                return await self.provision(client, subscription)

            # Update the secret
            await client.update_ppp_secret(
                secret[".id"],
                password=password,
                remote_address=subscription.ipv4_address,
                comment=self.get_comment(subscription),
                disabled=False,
            )

            logger.info(
                "PPPoE secret updated",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                    "router_id": client.router_id,
                },
            )

            return {
                "action": "updated",
                "resource": "ppp/secret",
                "name": username,
                "mikrotik_id": secret[".id"],
            }

        except Exception as e:
            raise ProvisioningError(
                f"Failed to update PPPoE secret: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Disconnect active PPPoE session."""
        if not subscription.ppp_username:
            return True

        try:
            disconnected = await client.disconnect_ppp_session(subscription.ppp_username)

            if disconnected:
                logger.info(
                    "PPPoE session disconnected",
                    extra={
                        "subscription_id": subscription.id,
                        "username": subscription.ppp_username,
                        "router_id": client.router_id,
                    },
                )

            return True

        except Exception as e:
            logger.warning(
                f"Failed to disconnect PPPoE session: {e}",
                extra={
                    "subscription_id": subscription.id,
                    "username": subscription.ppp_username,
                },
            )
            # Don't raise - disconnect failure shouldn't block other operations
            return False

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Check if PPPoE secret exists."""
        if not subscription.ppp_username:
            return False

        secret = await client.get_ppp_secret(subscription.ppp_username)
        return secret is not None

    async def get_session(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """Get active PPPoE session info."""
        if not subscription.ppp_username:
            return None

        sessions = await client.get_ppp_active(name=subscription.ppp_username)
        return sessions[0] if sessions else None
