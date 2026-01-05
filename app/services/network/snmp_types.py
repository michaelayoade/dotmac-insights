"""SNMP Poller Service Types.

Type definitions for the SNMP polling service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class PollingBatchResult:
    """Result of polling a batch of routers."""

    timestamp: datetime
    total_routers: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    errors: Dict[int, str] = field(default_factory=dict)


@dataclass
class RollupResult:
    """Result of a metrics rollup operation."""

    aggregation: str  # hourly, daily, monthly
    period_start: datetime
    records_created: int = 0
    routers_processed: int = 0
    interfaces_processed: int = 0
    duration_seconds: float = 0.0


@dataclass
class CleanupResult:
    """Result of metrics cleanup operation."""

    deleted_device_metrics: int = 0
    deleted_interface_metrics: int = 0
    retained_rollups: int = 0
    duration_seconds: float = 0.0


@dataclass
class RouterPollConfig:
    """Configuration for polling a single router."""

    router_id: int
    ip_address: str
    snmp_version: str = "2c"
    community: Optional[str] = None
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    port: int = 161
    timeout_seconds: int = 5
    retries: int = 2


@dataclass
class PollStatistics:
    """Polling statistics for monitoring dashboard."""

    total_configs: int = 0
    enabled_configs: int = 0
    successful_polls_24h: int = 0
    failed_polls_24h: int = 0
    avg_poll_duration_ms: float = 0.0
    routers_with_errors: List[int] = field(default_factory=list)
