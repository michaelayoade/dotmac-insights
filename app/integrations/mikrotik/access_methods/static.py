"""
Static IP Access Method

Manages static IP assignments via address lists and optional queues.
Used for subscribers with statically configured IP addresses on their equipment.
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


class StaticAccessMethod(AccessMethod):
    """
    Static IP access method.

    For subscribers with statically configured equipment where the
    router just needs to know which IPs are authorized.

    Implementation:
    1. Add IP(s) to allowed address list
    2. Optionally add IP(s) to a routing table
    3. Create bandwidth queue if needed

    Useful for:
    - Leased line customers
    - Business customers with static blocks
    - VPN endpoints
    """

    method_name = "static"
    label = "Static IP"
    requires_credentials = False
    requires_mac = False

    # Address list for allowed static IPs
    ALLOWED_LIST = "static-allowed"

    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Add static IP to allowed list and create queue."""
        if not subscription.ipv4_address:
            raise ProvisioningError(
                "Static IP method requires ipv4_address",
                subscription_id=subscription.id,
                access_method=self.method_name,
            )

        results = []

        # Add IPv4 to allowed list
        try:
            ipv4_result = await client.add_to_address_list(
                list_name=self.ALLOWED_LIST,
                address=subscription.ipv4_address,
                comment=self.get_comment(subscription),
                disabled=False,
            )

            results.append({
                "resource": "ip/firewall/address-list",
                "address": subscription.ipv4_address,
                "mikrotik_id": ipv4_result.get(".id"),
            })

            logger.info(
                "Static IPv4 added to allowed list",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                    "router_id": client.router_id,
                },
            )

        except ResourceExistsError:
            logger.info(
                "Static IPv4 already in list",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                },
            )

        # Add IPv6 if present
        if subscription.ipv6_address:
            try:
                ipv6_result = await client.add_to_address_list(
                    list_name=self.ALLOWED_LIST,
                    address=subscription.ipv6_address,
                    comment=self.get_comment(subscription),
                    disabled=False,
                )

                results.append({
                    "resource": "ip/firewall/address-list",
                    "address": subscription.ipv6_address,
                    "mikrotik_id": ipv6_result.get(".id"),
                })

                logger.info(
                    "Static IPv6 added to allowed list",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv6_address,
                        "router_id": client.router_id,
                    },
                )

            except ResourceExistsError:
                pass

        # Create bandwidth queue
        if subscription.download_speed and subscription.upload_speed:
            try:
                queue_name = f"static-{subscription.id}"
                max_limit = f"{subscription.download_speed}M/{subscription.upload_speed}M"

                queue_result = await client.create_simple_queue(
                    name=queue_name,
                    target=subscription.ipv4_address,
                    max_limit=max_limit,
                    comment=self.get_comment(subscription),
                    disabled=False,
                )

                results.append({
                    "resource": "queue/simple",
                    "name": queue_name,
                    "mikrotik_id": queue_result.get(".id"),
                })

                logger.info(
                    "Static IP queue created",
                    extra={
                        "subscription_id": subscription.id,
                        "queue": queue_name,
                        "limit": max_limit,
                        "router_id": client.router_id,
                    },
                )

            except ResourceExistsError:
                # Queue exists - update it
                pass

        return {
            "action": "created",
            "resource": "static",
            "ip": subscription.ipv4_address,
            "ipv6": subscription.ipv6_address,
            "results": results,
        }

    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Remove static IP from allowed list and delete queue."""
        success = True

        # Remove IPv4 from address list
        if subscription.ipv4_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv4_address,
                )
                logger.info(
                    "Static IPv4 removed from allowed list",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv4_address,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove static IPv4: {e}")
                success = False

        # Remove IPv6 from address list
        if subscription.ipv6_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv6_address,
                )
                logger.info(
                    "Static IPv6 removed from allowed list",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv6_address,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove static IPv6: {e}")

        # Delete queue
        try:
            queue_name = f"static-{subscription.id}"
            await client.delete_simple_queue(queue_name)
            logger.info(
                "Static IP queue deleted",
                extra={
                    "subscription_id": subscription.id,
                    "queue": queue_name,
                    "router_id": client.router_id,
                },
            )
        except ResourceNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to delete static IP queue: {e}")

        return success

    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Update static IP provisioning."""
        # Re-provision to handle changes
        await self.deprovision(client, subscription)
        return await self.provision(client, subscription)

    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Block static IP by removing from allowed list.

        This effectively blocks the subscriber until re-provisioned.
        """
        success = True

        if subscription.ipv4_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv4_address,
                )
                logger.info(
                    "Static IP client disconnected",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv4_address,
                        "router_id": client.router_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to disconnect static IP: {e}")
                success = False

        if subscription.ipv6_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv6_address,
                )
            except Exception as e:
                logger.warning(f"Failed to disconnect static IPv6: {e}")

        return success

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Check if static IP is in allowed list."""
        if not subscription.ipv4_address:
            return False

        entries = await client.get_address_list_entries(
            self.ALLOWED_LIST,
            address=subscription.ipv4_address,
        )
        return len(entries) > 0

    async def get_session(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """
        Get static IP provisioning info.

        Static IPs don't have sessions - return the address list entry.
        """
        if not subscription.ipv4_address:
            return None

        entries = await client.get_address_list_entries(
            self.ALLOWED_LIST,
            address=subscription.ipv4_address,
        )
        return entries[0] if entries else None
