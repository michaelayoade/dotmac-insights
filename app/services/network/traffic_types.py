"""Traffic Graph Service Type Definitions.

Data classes for traffic visualization and analytics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class TrafficDataPoint:
    """Single data point for traffic graphs."""

    timestamp: datetime
    rx_rate_bps: int = 0
    tx_rate_bps: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0


@dataclass
class TrafficGraphData:
    """Complete traffic graph dataset."""

    router_id: int
    interface_name: Optional[str] = None
    interface_index: Optional[int] = None
    start_time: datetime = None
    end_time: datetime = None
    resolution: str = "5min"  # 5min, hourly, daily
    data_points: List[TrafficDataPoint] = field(default_factory=list)

    # Summary statistics
    avg_rx_rate_bps: int = 0
    avg_tx_rate_bps: int = 0
    max_rx_rate_bps: int = 0
    max_tx_rate_bps: int = 0
    p95_rx_rate_bps: int = 0
    p95_tx_rate_bps: int = 0
    total_rx_bytes: int = 0
    total_tx_bytes: int = 0

    def to_chart_data(self) -> Dict[str, Any]:
        """Convert to Chart.js compatible format."""
        return {
            "labels": [dp.timestamp.isoformat() for dp in self.data_points],
            "datasets": [
                {
                    "label": "Inbound (RX)",
                    "data": [dp.rx_rate_bps for dp in self.data_points],
                    "borderColor": "#22c55e",
                    "backgroundColor": "rgba(34, 197, 94, 0.1)",
                    "fill": True,
                },
                {
                    "label": "Outbound (TX)",
                    "data": [dp.tx_rate_bps for dp in self.data_points],
                    "borderColor": "#3b82f6",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "fill": True,
                },
            ],
        }


@dataclass
class InterfaceTrafficSummary:
    """Traffic summary for a single interface."""

    router_id: int
    interface_index: int
    interface_name: str
    oper_status: str
    current_rx_rate_bps: int = 0
    current_tx_rate_bps: int = 0
    avg_rx_rate_bps: int = 0
    avg_tx_rate_bps: int = 0
    max_rx_rate_bps: int = 0
    max_tx_rate_bps: int = 0
    total_rx_bytes: int = 0
    total_tx_bytes: int = 0
    utilization_percent: float = 0.0
    interface_speed_bps: Optional[int] = None
    last_updated: Optional[datetime] = None


@dataclass
class RouterTrafficSummary:
    """Traffic summary for a router."""

    router_id: int
    router_name: str
    pop_name: Optional[str] = None
    total_interfaces: int = 0
    up_interfaces: int = 0
    down_interfaces: int = 0
    aggregate_rx_rate_bps: int = 0
    aggregate_tx_rate_bps: int = 0
    peak_rx_rate_bps: int = 0
    peak_tx_rate_bps: int = 0
    total_rx_bytes_24h: int = 0
    total_tx_bytes_24h: int = 0
    interfaces: List[InterfaceTrafficSummary] = field(default_factory=list)
    last_poll: Optional[datetime] = None
    poll_status: str = "unknown"


@dataclass
class TopInterface:
    """Interface ranked by traffic."""

    router_id: int
    router_name: str
    interface_index: int
    interface_name: str
    rx_rate_bps: int = 0
    tx_rate_bps: int = 0
    total_rate_bps: int = 0
    utilization_percent: float = 0.0


@dataclass
class TrafficFilters:
    """Filters for traffic queries."""

    router_id: Optional[int] = None
    pop_id: Optional[int] = None
    interface_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    resolution: str = "auto"  # auto, 5min, hourly, daily


@dataclass
class NOCDashboardStats:
    """Statistics for NOC dashboard."""

    # Device counts
    total_routers: int = 0
    online_routers: int = 0
    offline_routers: int = 0
    warning_routers: int = 0

    # Alert counts
    total_active_alerts: int = 0
    critical_alerts: int = 0
    warning_alerts: int = 0
    info_alerts: int = 0

    # Incident counts
    active_incidents: int = 0
    investigating_incidents: int = 0
    resolved_today: int = 0

    # Interface counts
    total_interfaces: int = 0
    up_interfaces: int = 0
    down_interfaces: int = 0

    # Traffic summary
    total_rx_rate_bps: int = 0
    total_tx_rate_bps: int = 0
    peak_rx_rate_24h_bps: int = 0
    peak_tx_rate_24h_bps: int = 0

    # Recent activity
    last_poll_time: Optional[datetime] = None
    poll_success_rate: float = 100.0


@dataclass
class DeviceStatusCard:
    """Device status for NOC grid display."""

    router_id: int
    router_name: str
    pop_name: Optional[str] = None
    ip_address: Optional[str] = None
    status: str = "unknown"  # online, offline, warning, maintenance
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    temperature: Optional[float] = None
    uptime_seconds: Optional[int] = None
    active_alerts: int = 0
    last_poll: Optional[datetime] = None
    poll_status: str = "unknown"


@dataclass
class AlertSummaryCard:
    """Alert summary for NOC display."""

    alert_id: int
    alert_type: str
    severity: str
    status: str
    title: str
    router_name: Optional[str] = None
    interface_name: Optional[str] = None
    triggered_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    acknowledged: bool = False


@dataclass
class IncidentSummaryCard:
    """Incident summary for NOC display."""

    incident_id: int
    title: str
    severity: str
    status: str
    affected_routers: int = 0
    affected_customers: int = 0
    started_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    assigned_to: Optional[str] = None
