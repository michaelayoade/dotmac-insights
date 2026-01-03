"""
MikroTik Integration Module

Provides real-time subscription provisioning to MikroTik routers
via the RouterOS REST API.

Components:
- client: MikroTik REST API client
- provisioner: High-level provisioning orchestrator
- access_methods: Handlers for different access types (PPPoE, Hotspot, etc.)
- radius: RADIUS attribute management
- exceptions: Custom exception classes
"""

from app.integrations.mikrotik.client import MikroTikClient
from app.integrations.mikrotik.exceptions import (
    MikroTikError,
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    APIError,
    ResourceNotFoundError,
    ResourceExistsError,
    ProvisioningError,
    DeprovisioningError,
    DisconnectError,
    RouterUnavailableError,
    CircuitBreakerOpenError,
)

__all__ = [
    "MikroTikClient",
    "MikroTikError",
    "ConnectionError",
    "AuthenticationError",
    "TimeoutError",
    "APIError",
    "ResourceNotFoundError",
    "ResourceExistsError",
    "ProvisioningError",
    "DeprovisioningError",
    "DisconnectError",
    "RouterUnavailableError",
    "CircuitBreakerOpenError",
]
