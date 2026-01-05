"""Alert Service Type Definitions.

Data classes for alert service inputs and outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class AlertCreateData:
    """Data for creating a new alert."""

    alert_type: str
    severity: str
    title: str
    message: str
    router_id: Optional[int] = None
    pop_id: Optional[int] = None
    interface_index: Optional[int] = None
    interface_name: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    rule_id: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class AlertEvaluationResult:
    """Result of evaluating a metric against alert rules."""

    triggered_alerts: List[AlertCreateData] = field(default_factory=list)
    resolved_alert_ids: List[int] = field(default_factory=list)
    skipped_rules: int = 0  # Rules on cooldown or suppressed
    evaluated_rules: int = 0


@dataclass
class AlertFilters:
    """Filters for querying alerts."""

    status: Optional[str] = None
    statuses: Optional[List[str]] = None
    severity: Optional[str] = None
    severities: Optional[List[str]] = None
    alert_type: Optional[str] = None
    router_id: Optional[int] = None
    pop_id: Optional[int] = None
    incident_id: Optional[int] = None
    acknowledged: Optional[bool] = None
    auto_resolved: Optional[bool] = None
    triggered_after: Optional[datetime] = None
    triggered_before: Optional[datetime] = None


@dataclass
class AlertStats:
    """Alert statistics summary."""

    total_active: int = 0
    total_acknowledged: int = 0
    total_resolved_24h: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    mean_time_to_acknowledge_minutes: Optional[float] = None
    mean_time_to_resolve_minutes: Optional[float] = None


@dataclass
class AlertRuleFilters:
    """Filters for querying alert rules."""

    is_enabled: Optional[bool] = None
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    router_id: Optional[int] = None
    pop_id: Optional[int] = None


@dataclass
class DeviceAlertCheck:
    """Data for checking device-level alerts."""

    router_id: int
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    temperature: Optional[float] = None
    is_reachable: bool = True
    poll_error: Optional[str] = None


@dataclass
class InterfaceAlertCheck:
    """Data for checking interface-level alerts."""

    router_id: int
    interface_index: int
    interface_name: str
    oper_status: str  # "up", "down"
    rx_errors: int = 0
    tx_errors: int = 0
    rx_rate_bps: int = 0
    tx_rate_bps: int = 0
    interface_speed_bps: Optional[int] = None


@dataclass
class SuppressionCheck:
    """Result of checking if an alert is suppressed."""

    is_suppressed: bool
    suppression_id: Optional[int] = None
    reason: Optional[str] = None
    ends_at: Optional[datetime] = None


@dataclass
class AlertNotificationRequest:
    """Request to send alert notification."""

    alert_id: int
    channels: List[str]
    recipients: List[str]
    is_escalation: bool = False
    escalation_level: int = 0


@dataclass
class AlertNotificationResult:
    """Result of sending alert notification."""

    success: bool
    channels_sent: List[str] = field(default_factory=list)
    channels_failed: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class AlertBatchResult:
    """Result of batch alert processing."""

    alerts_created: int = 0
    alerts_resolved: int = 0
    alerts_escalated: int = 0
    notifications_sent: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
