"""Network services module.

This module provides services for managing network infrastructure:
- PopService: Points of Presence management
- RouterService: Router/NAS management
- IPv4NetworkService: IPv4 network management
- IPv6NetworkService: IPv6 network management
- IPAddressService: IP address management
"""
from .pops import PopService
from .routers import RouterService
from .ip_networks import IPv4NetworkService, IPv6NetworkService
from .ip_addresses import IPAddressService

from .network_types import (
    # POP types
    PopFilters,
    PopCreateData,
    PopUpdateData,
    PopStats,
    # Router types
    RouterFilters,
    RouterCreateData,
    RouterUpdateData,
    RouterStats,
    # IP Network types
    IPv4NetworkFilters,
    IPv6NetworkFilters,
    # IP Address types
    IPv4AddressFilters,
)

__all__ = [
    # Services
    "PopService",
    "RouterService",
    "IPv4NetworkService",
    "IPv6NetworkService",
    "IPAddressService",
    # POP types
    "PopFilters",
    "PopCreateData",
    "PopUpdateData",
    "PopStats",
    # Router types
    "RouterFilters",
    "RouterCreateData",
    "RouterUpdateData",
    "RouterStats",
    # IP Network types
    "IPv4NetworkFilters",
    "IPv6NetworkFilters",
    # IP Address types
    "IPv4AddressFilters",
]
