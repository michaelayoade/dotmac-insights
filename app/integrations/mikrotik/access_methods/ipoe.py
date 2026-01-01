"""
IPoE Access Method

IP over Ethernet (IPoE) access method - allows access based on IP/MAC
binding without PPP or Hotspot authentication.

This is similar to DHCP binding but may use different network topology
where clients get their IP via DHCP relay or static assignment.
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


class IPoEAccessMethod(AccessMethod):
    """
    IPoE (IP over Ethernet) access method.

    IPoE provides internet access based on the subscriber's IP/MAC
    combination without requiring PPP or captive portal authentication.

    Implementation:
    1. Add IP to allowed address list
    2. Optionally create simple queue for bandwidth limiting
    3. Access controlled by firewall rules on the address list

    This is useful for:
    - Enterprise/business connections
    - Trusted networks
    - Scenarios where CPE handles authentication
    """

    method_name = "ipoe"
    label = "IPoE"
    requires_credentials = False
    requires_mac = False  # Optional - IP-only binding is supported

    # Address list for allowed IPoE clients
    ALLOWED_LIST = "ipoe-allowed"

    # Whether to create bandwidth queues (alternative to RADIUS)
    use_queues = False

    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Add subscriber to IPoE allowed list."""
        if not subscription.ipv4_address:
            raise ProvisioningError(
                "IPoE requires ipv4_address",
                subscription_id=subscription.id,
                access_method=self.method_name,
            )

        results = []

        try:
            # Add to allowed address list
            list_result = await client.add_to_address_list(
                list_name=self.ALLOWED_LIST,
                address=subscription.ipv4_address,
                comment=self.get_comment(subscription),
                disabled=False,
            )

            results.append({
                "resource": "ip/firewall/address-list",
                "list": self.ALLOWED_LIST,
                "mikrotik_id": list_result.get(".id"),
            })

            logger.info(
                "IPoE address added to allowed list",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                    "router_id": client.router_id,
                },
            )

        except ResourceExistsError:
            logger.info(
                "IPoE address already in list",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                },
            )

        # Optionally create bandwidth queue
        if self.use_queues and subscription.download_speed and subscription.upload_speed:
            try:
                queue_name = f"sub-{subscription.id}"
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
                    "IPoE bandwidth queue created",
                    extra={
                        "subscription_id": subscription.id,
                        "queue": queue_name,
                        "limit": max_limit,
                        "router_id": client.router_id,
                    },
                )

            except ResourceExistsError:
                pass

        return {
            "action": "created",
            "resource": "ipoe",
            "ip": subscription.ipv4_address,
            "results": results,
        }

    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Remove subscriber from IPoE allowed list."""
        success = True

        # Remove from address list
        if subscription.ipv4_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv4_address,
                )
                logger.info(
                    "IPoE address removed from allowed list",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv4_address,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove IPoE address: {e}")
                success = False

        # Remove queue if we created one
        if self.use_queues:
            try:
                queue_name = f"sub-{subscription.id}"
                await client.delete_simple_queue(queue_name)
                logger.info(
                    "IPoE bandwidth queue deleted",
                    extra={
                        "subscription_id": subscription.id,
                        "queue": queue_name,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to delete IPoE queue: {e}")

        return success

    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Update IPoE provisioning."""
        # Re-provision to handle any IP changes
        await self.deprovision(client, subscription)
        return await self.provision(client, subscription)

    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Block IPoE client by removing from allowed list.

        Note: This effectively deprovisioning for IPoE.
        Re-enabling requires re-provisioning.
        """
        if not subscription.ipv4_address:
            return True

        try:
            await client.remove_from_address_list(
                self.ALLOWED_LIST,
                subscription.ipv4_address,
            )

            logger.info(
                "IPoE client disconnected (removed from allowed list)",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                    "router_id": client.router_id,
                },
            )

            return True

        except Exception as e:
            logger.warning(
                f"Failed to disconnect IPoE client: {e}",
                extra={"subscription_id": subscription.id},
            )
            return False

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Check if IP is in allowed list."""
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
        Get IPoE "session" info.

        IPoE doesn't have sessions - we return the address list entry.
        """
        if not subscription.ipv4_address:
            return None

        entries = await client.get_address_list_entries(
            self.ALLOWED_LIST,
            address=subscription.ipv4_address,
        )
        return entries[0] if entries else None
