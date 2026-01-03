"""
Hotspot Access Method

Manages Hotspot users on MikroTik routers for captive portal authentication.
Commonly used for WiFi access points and public internet access.
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


class HotspotAccessMethod(AccessMethod):
    """
    Hotspot access method.

    Creates hotspot users for captive portal authentication.
    Users connect to a hotspot network and authenticate via
    a web portal before gaining internet access.

    Supports:
    - Username/password authentication
    - Optional MAC binding
    - Optional IP binding
    - RADIUS profile for bandwidth control
    """

    method_name = "hotspot"
    label = "Hotspot"
    requires_credentials = True
    requires_mac = False  # Optional but recommended

    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Create hotspot user for the subscriber."""
        self.validate_subscription(subscription)
        if not subscription.ppp_username or not subscription.ppp_password:
            raise ProvisioningError(
                "Hotspot username/password required for provisioning",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )
        username = subscription.ppp_username
        password = subscription.ppp_password

        try:
            result = await client.create_hotspot_user(
                name=username,
                password=password,
                profile="radius",  # Use RADIUS for bandwidth control
                address=subscription.ipv4_address,
                mac_address=subscription.mac_address,
                comment=self.get_comment(subscription),
                disabled=False,
            )

            logger.info(
                "Hotspot user created",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                    "router_id": client.router_id,
                },
            )

            return {
                "action": "created",
                "resource": "ip/hotspot/user",
                "name": username,
                "mikrotik_id": result.get(".id"),
            }

        except ResourceExistsError:
            # User already exists - update it
            logger.info(
                "Hotspot user exists, updating",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                },
            )
            return await self.update(client, subscription)

        except Exception as e:
            raise ProvisioningError(
                f"Failed to create hotspot user: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Remove hotspot user and disconnect any active session."""
        if not subscription.ppp_username:
            return True

        try:
            # First disconnect any active session
            await self.disconnect(client, subscription)

            # Then delete the user
            deleted = await client.delete_hotspot_user(subscription.ppp_username)

            if deleted:
                logger.info(
                    "Hotspot user deleted",
                    extra={
                        "subscription_id": subscription.id,
                        "username": subscription.ppp_username,
                        "router_id": client.router_id,
                    },
                )

            return True

        except ResourceNotFoundError:
            return True

        except Exception as e:
            raise DeprovisioningError(
                f"Failed to delete hotspot user: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Update existing hotspot user."""
        self.validate_subscription(subscription)
        if not subscription.ppp_username or not subscription.ppp_password:
            raise ProvisioningError(
                "Hotspot username/password required for update",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )
        username = subscription.ppp_username
        password = subscription.ppp_password

        try:
            user = await client.get_hotspot_user(username)

            if not user:
                return await self.provision(client, subscription)

            # Update via patch
            data = {
                "password": password,
                "comment": self.get_comment(subscription),
                "disabled": "no",
            }
            if subscription.ipv4_address:
                data["address"] = subscription.ipv4_address
            if subscription.mac_address:
                data["mac-address"] = subscription.mac_address

            await client.patch("/ip/hotspot/user", user[".id"], data)

            logger.info(
                "Hotspot user updated",
                extra={
                    "subscription_id": subscription.id,
                    "username": username,
                    "router_id": client.router_id,
                },
            )

            return {
                "action": "updated",
                "resource": "ip/hotspot/user",
                "name": username,
                "mikrotik_id": user[".id"],
            }

        except Exception as e:
            raise ProvisioningError(
                f"Failed to update hotspot user: {e}",
                subscription_id=subscription.id,
                access_method=self.method_name,
                router_id=client.router_id,
            )

    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Disconnect active hotspot session."""
        if not subscription.ppp_username:
            return True

        try:
            disconnected = await client.disconnect_hotspot_session(subscription.ppp_username)

            if disconnected:
                logger.info(
                    "Hotspot session disconnected",
                    extra={
                        "subscription_id": subscription.id,
                        "username": subscription.ppp_username,
                        "router_id": client.router_id,
                    },
                )

            return True

        except Exception as e:
            logger.warning(
                f"Failed to disconnect hotspot session: {e}",
                extra={
                    "subscription_id": subscription.id,
                    "username": subscription.ppp_username,
                },
            )
            return False

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Check if hotspot user exists."""
        if not subscription.ppp_username:
            return False

        user = await client.get_hotspot_user(subscription.ppp_username)
        return user is not None

    async def get_session(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """Get active hotspot session info."""
        if not subscription.ppp_username:
            return None

        sessions = await client.get_hotspot_active(user=subscription.ppp_username)
        return sessions[0] if sessions else None
