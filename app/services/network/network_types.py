"""Type definitions for network services.

These dataclasses define the contract for network operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


__all__ = [
    # POP
    "PopFilters",
    "PopCreateData",
    "PopUpdateData",
    "PopStats",
    # Router
    "RouterFilters",
    "RouterCreateData",
    "RouterUpdateData",
    "RouterStats",
    # IPv4Network
    "IPv4NetworkFilters",
    # IPv6Network
    "IPv6NetworkFilters",
    # IPv4Address
    "IPv4AddressFilters",
]


# =============================================================================
# POP Types
# =============================================================================

@dataclass
class PopFilters:
    """Filters for listing POPs."""

    search: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_active: Optional[bool] = None
    has_routers: Optional[bool] = None


@dataclass
class PopCreateData:
    """Data for creating a POP."""

    name: str
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True
    splynx_id: Optional[int] = None

    # Optional: link to Party as organization
    org_party_id: Optional[int] = None


@dataclass
class PopUpdateData:
    """Data for updating a POP."""

    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None
    org_party_id: Optional[int] = None


@dataclass
class PopStats:
    """Statistics for a POP."""

    pop_id: int
    pop_name: str
    customer_count: int = 0
    active_subscriptions: int = 0
    router_count: int = 0
    mrr: Decimal = field(default_factory=lambda: Decimal("0"))
    open_tickets: int = 0


# =============================================================================
# Router Types
# =============================================================================

@dataclass
class RouterFilters:
    """Filters for listing routers."""

    search: Optional[str] = None
    pop_id: Optional[int] = None
    status: Optional[str] = None
    nas_type: Optional[int] = None


@dataclass
class RouterCreateData:
    """Data for creating a router."""

    title: str
    splynx_id: int

    model: Optional[str] = None
    ip: Optional[str] = None
    nas_ip: Optional[str] = None
    nas_type: Optional[int] = None

    pop_id: Optional[int] = None
    location_id: Optional[int] = None
    address: Optional[str] = None
    gps: Optional[str] = None

    # RADIUS
    radius_secret: Optional[str] = None
    radius_coa_port: Optional[int] = None
    radius_accounting_interval: Optional[int] = None
    authorization_method: Optional[str] = None
    accounting_method: Optional[str] = None

    # API/SSH
    api_login: Optional[str] = None
    api_password: Optional[str] = None
    api_port: Optional[int] = None
    ssh_port: Optional[int] = None

    status: str = "active"


@dataclass
class RouterUpdateData:
    """Data for updating a router."""

    title: Optional[str] = None
    model: Optional[str] = None
    ip: Optional[str] = None
    nas_ip: Optional[str] = None
    nas_type: Optional[int] = None
    pop_id: Optional[int] = None
    status: Optional[str] = None

    radius_secret: Optional[str] = None
    api_login: Optional[str] = None
    api_password: Optional[str] = None


@dataclass
class RouterStats:
    """Statistics for a router."""

    router_id: int
    router_title: str
    active_subscriptions: int = 0
    total_subscriptions: int = 0


# =============================================================================
# IP Network Types
# =============================================================================

@dataclass
class IPv4NetworkFilters:
    """Filters for listing IPv4 networks."""

    search: Optional[str] = None
    network_type: Optional[str] = None  # rootnet, endnet
    type_of_usage: Optional[str] = None  # pool, static, management
    location_id: Optional[int] = None
    parent_id: Optional[int] = None


@dataclass
class IPv6NetworkFilters:
    """Filters for listing IPv6 networks."""

    search: Optional[str] = None
    network_type: Optional[str] = None
    type_of_usage: Optional[str] = None
    location_id: Optional[int] = None


# =============================================================================
# IP Address Types
# =============================================================================

@dataclass
class IPv4AddressFilters:
    """Filters for listing IPv4 addresses."""

    search: Optional[str] = None
    is_used: Optional[bool] = None
    status: Optional[str] = None
    network_id: Optional[int] = None
    party_id: Optional[int] = None
    module: Optional[str] = None
