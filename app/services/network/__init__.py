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
from .snmp_poller import SNMPPollerService
from .snmp_types import (
    PollingBatchResult,
    RollupResult,
    CleanupResult,
    RouterPollConfig,
    PollStatistics,
)
from .alerts import AlertService
from .alert_types import (
    AlertCreateData,
    AlertEvaluationResult,
    AlertFilters,
    AlertStats,
    AlertRuleFilters,
    DeviceAlertCheck,
    InterfaceAlertCheck,
    SuppressionCheck,
    AlertBatchResult,
)
from .traffic_graphs import TrafficGraphService
from .traffic_types import (
    TrafficDataPoint,
    TrafficGraphData,
    InterfaceTrafficSummary,
    RouterTrafficSummary,
    TopInterface,
    TrafficFilters,
    NOCDashboardStats,
    DeviceStatusCard,
    AlertSummaryCard,
    IncidentSummaryCard,
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
    # SNMP Polling
    "SNMPPollerService",
    "PollingBatchResult",
    "RollupResult",
    "CleanupResult",
    "RouterPollConfig",
    "PollStatistics",
    # Alert Service
    "AlertService",
    "AlertCreateData",
    "AlertEvaluationResult",
    "AlertFilters",
    "AlertStats",
    "AlertRuleFilters",
    "DeviceAlertCheck",
    "InterfaceAlertCheck",
    "SuppressionCheck",
    "AlertBatchResult",
    # Traffic Graph Service
    "TrafficGraphService",
    "TrafficDataPoint",
    "TrafficGraphData",
    "InterfaceTrafficSummary",
    "RouterTrafficSummary",
    "TopInterface",
    "TrafficFilters",
    "NOCDashboardStats",
    "DeviceStatusCard",
    "AlertSummaryCard",
    "IncidentSummaryCard",
]
