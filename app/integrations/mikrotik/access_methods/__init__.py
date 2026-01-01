"""
MikroTik Access Methods

Handlers for different subscriber access methods on MikroTik routers.
Each method implements provisioning, deprovisioning, and session management.

Supported methods:
- PPPoE: Point-to-Point Protocol over Ethernet
- Hotspot: Captive portal authentication
- DHCP: Static MAC-to-IP binding
- IPoE: IP over Ethernet (IP-based access)
- Static: Static IP assignment
"""

from typing import Dict, Type, Optional

from app.integrations.mikrotik.access_methods.base import AccessMethod
from app.integrations.mikrotik.access_methods.pppoe import PPPoEAccessMethod
from app.integrations.mikrotik.access_methods.hotspot import HotspotAccessMethod
from app.integrations.mikrotik.access_methods.dhcp import DHCPAccessMethod
from app.integrations.mikrotik.access_methods.ipoe import IPoEAccessMethod
from app.integrations.mikrotik.access_methods.static import StaticAccessMethod


# Registry of access methods
ACCESS_METHODS: Dict[str, Type[AccessMethod]] = {
    "pppoe": PPPoEAccessMethod,
    "hotspot": HotspotAccessMethod,
    "dhcp": DHCPAccessMethod,
    "ipoe": IPoEAccessMethod,
    "static": StaticAccessMethod,
}


def get_access_method(method_name: str) -> Optional[AccessMethod]:
    """
    Get an access method handler by name.

    Args:
        method_name: One of "pppoe", "hotspot", "dhcp", "ipoe", "static"

    Returns:
        AccessMethod instance or None if not found
    """
    method_class = ACCESS_METHODS.get(method_name)
    if method_class:
        return method_class()
    return None


def get_access_method_choices() -> list[tuple[str, str]]:
    """
    Get access method choices for form dropdowns.

    Returns:
        List of (value, label) tuples
    """
    return [
        ("pppoe", "PPPoE"),
        ("hotspot", "Hotspot"),
        ("dhcp", "DHCP Binding"),
        ("ipoe", "IPoE"),
        ("static", "Static IP"),
    ]


def get_access_method_options() -> list[dict]:
    """
    Get access method options for HTML select dropdowns.

    Returns:
        List of dicts with value, label, requires_credentials, requires_mac
    """
    return [
        {
            "value": "pppoe",
            "label": "PPPoE",
            "requires_credentials": True,
            "requires_mac": False,
        },
        {
            "value": "hotspot",
            "label": "Hotspot",
            "requires_credentials": True,
            "requires_mac": False,
        },
        {
            "value": "dhcp",
            "label": "DHCP Binding",
            "requires_credentials": False,
            "requires_mac": True,
        },
        {
            "value": "ipoe",
            "label": "IPoE",
            "requires_credentials": False,
            "requires_mac": False,
        },
        {
            "value": "static",
            "label": "Static IP",
            "requires_credentials": False,
            "requires_mac": False,
        },
    ]


__all__ = [
    "AccessMethod",
    "PPPoEAccessMethod",
    "HotspotAccessMethod",
    "DHCPAccessMethod",
    "IPoEAccessMethod",
    "StaticAccessMethod",
    "ACCESS_METHODS",
    "get_access_method",
    "get_access_method_choices",
    "get_access_method_options",
]
