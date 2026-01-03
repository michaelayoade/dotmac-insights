"""
DHCP Access Method

Manages static DHCP bindings and address list entries on MikroTik routers.
Used for MAC-based authentication where the subscriber's MAC address is
bound to a specific IP address.
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


class DHCPAccessMethod(AccessMethod):
    """
    DHCP static binding access method.

    Creates static DHCP leases that bind a MAC address to a specific IP.
    Also adds the IP to an allowed address list for firewall rules.

    This method doesn't require username/password - access is controlled
    by the device's MAC address.

    Typical setup:
    1. Static DHCP lease binds MAC to IP
    2. Address list entry allows the IP through firewall
    3. Bandwidth controlled via simple queue or RADIUS (if using user manager)
    """

    method_name = "dhcp"
    label = "DHCP Binding"
    requires_credentials = False
    requires_mac = True

    # Address list name for allowed customers
    ALLOWED_LIST = "allowed-customers"

    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Create static DHCP binding and address list entry."""
        self.validate_subscription(subscription)

        if not subscription.ipv4_address:
            raise ProvisioningError(
                "DHCP binding requires ipv4_address",
                subscription_id=subscription.id,
                access_method=self.method_name,
            )
        if not subscription.mac_address:
            raise ProvisioningError(
                "DHCP binding requires mac_address",
                subscription_id=subscription.id,
                access_method=self.method_name,
            )

        results = []

        try:
            # Create static DHCP lease
            lease_result = await client.create_dhcp_static(
                mac_address=subscription.mac_address,
                address=subscription.ipv4_address,
                comment=self.get_comment(subscription),
                always_broadcast=True,
                disabled=False,
            )

            results.append({
                "resource": "ip/dhcp-server/lease",
                "mikrotik_id": lease_result.get(".id"),
            })

            logger.info(
                "DHCP static lease created",
                extra={
                    "subscription_id": subscription.id,
                    "mac": subscription.mac_address,
                    "ip": subscription.ipv4_address,
                    "router_id": client.router_id,
                },
            )

        except ResourceExistsError:
            logger.info(
                "DHCP lease exists, updating",
                extra={
                    "subscription_id": subscription.id,
                    "mac": subscription.mac_address,
                },
            )

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
                "mikrotik_id": list_result.get(".id"),
            })

            logger.info(
                "Address list entry added",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                    "list": self.ALLOWED_LIST,
                    "router_id": client.router_id,
                },
            )

        except ResourceExistsError:
            logger.info(
                "Address list entry exists",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                },
            )

        return {
            "action": "created",
            "resource": "dhcp+address-list",
            "mac": subscription.mac_address,
            "ip": subscription.ipv4_address,
            "results": results,
        }

    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Remove DHCP binding and address list entry."""
        success = True

        # Remove DHCP lease
        if subscription.mac_address:
            try:
                await client.delete_dhcp_lease(subscription.mac_address)
                logger.info(
                    "DHCP lease deleted",
                    extra={
                        "subscription_id": subscription.id,
                        "mac": subscription.mac_address,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to delete DHCP lease: {e}")
                success = False

        # Remove from address list
        if subscription.ipv4_address:
            try:
                await client.remove_from_address_list(
                    self.ALLOWED_LIST,
                    subscription.ipv4_address,
                )
                logger.info(
                    "Address list entry removed",
                    extra={
                        "subscription_id": subscription.id,
                        "ip": subscription.ipv4_address,
                        "router_id": client.router_id,
                    },
                )
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove address list entry: {e}")
                success = False

        return success

    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """Update DHCP binding and address list entry."""
        self.validate_subscription(subscription)

        # For DHCP, we typically deprovision and re-provision
        # to handle IP/MAC changes cleanly
        await self.deprovision(client, subscription)
        return await self.provision(client, subscription)

    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Disconnect a DHCP client.

        For DHCP, we can't really disconnect - we remove from address list
        which will block the client until they renew.
        """
        if not subscription.ipv4_address:
            return True

        try:
            # Remove from allowed list to block traffic
            await client.remove_from_address_list(
                self.ALLOWED_LIST,
                subscription.ipv4_address,
            )

            logger.info(
                "DHCP client blocked (removed from address list)",
                extra={
                    "subscription_id": subscription.id,
                    "ip": subscription.ipv4_address,
                    "router_id": client.router_id,
                },
            )

            return True

        except Exception as e:
            logger.warning(
                f"Failed to block DHCP client: {e}",
                extra={"subscription_id": subscription.id},
            )
            return False

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """Check if DHCP binding exists."""
        if not subscription.mac_address:
            return False

        lease = await client.get_dhcp_lease(subscription.mac_address)
        return lease is not None

    async def get_session(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """
        Get DHCP lease info.

        Note: DHCP doesn't have "sessions" like PPP - we return the lease info.
        """
        if not subscription.mac_address:
            return None

        return await client.get_dhcp_lease(subscription.mac_address)
