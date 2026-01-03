"""
Base Access Method Class

Abstract base class for all MikroTik access method implementations.
Each access method (PPPoE, Hotspot, DHCP, IPoE, Static) must implement
the core provisioning operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.integrations.mikrotik.client import MikroTikClient
    from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class AccessMethod(ABC):
    """
    Abstract base class for MikroTik access method handlers.

    Each subclass implements provisioning logic for a specific access type:
    - PPPoE: Create/manage PPPoE secrets
    - Hotspot: Create/manage hotspot users
    - DHCP: Create/manage static DHCP bindings
    - IPoE: IP binding without authentication
    - Static: Static IP assignment via address lists
    """

    # Access method identifier (matches Subscription.access_method values)
    method_name: str = ""

    # Human-readable label
    label: str = ""

    # Whether this method requires PPP credentials
    requires_credentials: bool = False

    # Whether this method requires MAC address
    requires_mac: bool = False

    @abstractmethod
    async def provision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """
        Provision a subscription on the router.

        This creates the necessary resources on the MikroTik router
        to allow the subscriber to connect.

        Args:
            client: MikroTik API client
            subscription: Subscription to provision

        Returns:
            Dict with provisioning result details

        Raises:
            ProvisioningError: If provisioning fails
        """
        pass

    @abstractmethod
    async def deprovision(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Remove a subscription from the router.

        This removes all resources associated with the subscriber.

        Args:
            client: MikroTik API client
            subscription: Subscription to deprovision

        Returns:
            True if successfully deprovisioned

        Raises:
            DeprovisioningError: If deprovisioning fails
        """
        pass

    @abstractmethod
    async def update(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """
        Update an existing provisioned subscription.

        This updates the resources on the router to reflect changes
        in the subscription (e.g., new IP, new speed).

        Args:
            client: MikroTik API client
            subscription: Subscription with updated values

        Returns:
            Dict with update result details

        Raises:
            ProvisioningError: If update fails
        """
        pass

    @abstractmethod
    async def disconnect(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Disconnect an active session without removing provisioning.

        Used for suspension - the subscriber's credentials remain
        but their current session is terminated.

        Args:
            client: MikroTik API client
            subscription: Subscription to disconnect

        Returns:
            True if session was disconnected (or no active session)

        Raises:
            DisconnectError: If disconnect fails
        """
        pass

    async def is_provisioned(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> bool:
        """
        Check if a subscription is currently provisioned on the router.

        Args:
            client: MikroTik API client
            subscription: Subscription to check

        Returns:
            True if provisioned
        """
        # Default implementation - subclasses should override
        return False

    async def get_session(
        self,
        client: MikroTikClient,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """
        Get active session information for a subscription.

        Args:
            client: MikroTik API client
            subscription: Subscription to check

        Returns:
            Session data if active, None otherwise
        """
        # Default implementation - subclasses should override
        return None

    def get_comment(self, subscription: Subscription) -> str:
        """
        Generate a comment string for MikroTik resources.

        Used to tag resources for tracking and cleanup.

        Args:
            subscription: The subscription

        Returns:
            Comment string
        """
        return f"sub:{subscription.id}"

    def validate_subscription(self, subscription: Subscription) -> None:
        """
        Validate that a subscription has all required fields for this method.

        Args:
            subscription: Subscription to validate

        Raises:
            ValidationError: If required fields are missing
        """
        from app.integrations.mikrotik.exceptions import ValidationError

        if self.requires_credentials:
            if not subscription.ppp_username:
                raise ValidationError(
                    f"{self.label} requires ppp_username",
                    code="missing_username",
                )
            if not subscription.ppp_password:
                raise ValidationError(
                    f"{self.label} requires ppp_password",
                    code="missing_password",
                )

        if self.requires_mac:
            if not subscription.mac_address:
                raise ValidationError(
                    f"{self.label} requires mac_address",
                    code="missing_mac",
                )
