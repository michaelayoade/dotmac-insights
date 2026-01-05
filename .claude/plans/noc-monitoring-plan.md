# NOC & Monitoring Services Plan

## Priority Matrix

| Component              | Impact | Difficulty | Priority |
|------------------------|--------|------------|----------|
| SNMP Polling Engine    | HIGH   | Medium     | P1       |
| Traffic Graphs/History | HIGH   | Medium     | P1       |
| Alerting System        | HIGH   | Medium     | P1       |
| Outage Detection       | HIGH   | Medium     | P1       |
| Customer Usage Dashboard | HIGH | Low        | P1       |
| Network Topology Map   | MEDIUM | Medium     | P2       |
| TR-069/ACS             | MEDIUM | High       | P3       |
| SLA Enforcement        | MEDIUM | Low        | P2       |
| NetFlow/sFlow          | LOW    | High       | P4       |

---

## Part 1: SNMP Polling Engine

### 1.1 Models

**New file**: `app/models/snmp_metrics.py`

```python
class SNMPPollingConfig(Base):
    """Per-device SNMP configuration."""
    __tablename__ = "snmp_polling_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), unique=True)

    # SNMP Version
    snmp_version: Mapped[str]  # "2c", "3"

    # v2c settings
    community: Mapped[Optional[str]]  # Encrypted

    # v3 settings
    username: Mapped[Optional[str]]
    auth_protocol: Mapped[Optional[str]]  # MD5, SHA
    auth_password: Mapped[Optional[str]]  # Encrypted
    priv_protocol: Mapped[Optional[str]]  # DES, AES
    priv_password: Mapped[Optional[str]]  # Encrypted

    # Polling settings
    polling_interval_seconds: Mapped[int] = mapped_column(default=300)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    last_polled_at: Mapped[Optional[datetime]]
    last_poll_status: Mapped[Optional[str]]  # SUCCESS, TIMEOUT, ERROR
    consecutive_failures: Mapped[int] = mapped_column(default=0)


class DeviceMetric(Base):
    """Device-level metrics (CPU, memory, uptime)."""
    __tablename__ = "device_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(index=True)

    # System
    uptime_seconds: Mapped[Optional[int]]
    cpu_percent: Mapped[Optional[float]]
    memory_percent: Mapped[Optional[float]]
    temperature: Mapped[Optional[float]]

    # Aggregated traffic (all interfaces)
    total_rx_bytes: Mapped[int] = mapped_column(default=0)
    total_tx_bytes: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        Index("ix_device_metrics_router_time", "router_id", "timestamp"),
    )


class InterfaceMetric(Base):
    """Per-interface traffic metrics."""
    __tablename__ = "interface_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), index=True)
    interface_index: Mapped[int]
    interface_name: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(index=True)

    # Counters (from SNMP)
    rx_bytes: Mapped[int]
    tx_bytes: Mapped[int]
    rx_packets: Mapped[int]
    tx_packets: Mapped[int]
    rx_errors: Mapped[int]
    tx_errors: Mapped[int]
    rx_discards: Mapped[int]
    tx_discards: Mapped[int]

    # Calculated rates (bits per second)
    rx_rate_bps: Mapped[Optional[int]]
    tx_rate_bps: Mapped[Optional[int]]

    # Status
    oper_status: Mapped[str]  # UP, DOWN, TESTING
    admin_status: Mapped[str]  # UP, DOWN
    speed_bps: Mapped[Optional[int]]

    __table_args__ = (
        Index("ix_interface_metrics_router_if_time", "router_id", "interface_index", "timestamp"),
    )


class InterfaceState(Base):
    """Current interface state (latest snapshot)."""
    __tablename__ = "interface_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), index=True)
    interface_index: Mapped[int]
    interface_name: Mapped[str] = mapped_column(String(100))
    interface_alias: Mapped[Optional[str]] = mapped_column(String(255))
    interface_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Current state
    oper_status: Mapped[str]
    admin_status: Mapped[str]
    speed_bps: Mapped[Optional[int]]
    mtu: Mapped[Optional[int]]
    mac_address: Mapped[Optional[str]]

    # Latest counters
    last_rx_bytes: Mapped[int] = mapped_column(default=0)
    last_tx_bytes: Mapped[int] = mapped_column(default=0)

    # State tracking
    last_change_at: Mapped[Optional[datetime]]
    last_polled_at: Mapped[datetime]

    __table_args__ = (
        Index("ix_interface_states_router_if", "router_id", "interface_index", unique=True),
    )
```

---

### 1.2 SNMP Poller Service

**New file**: `app/services/network/snmp_poller.py`

```python
class SNMPPoller:
    """SNMP polling service for network devices."""

    # OIDs
    OIDS = {
        # System
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysName": "1.3.6.1.2.1.1.5.0",

        # Interfaces (table walk)
        "ifIndex": "1.3.6.1.2.1.2.2.1.1",
        "ifDescr": "1.3.6.1.2.1.2.2.1.2",
        "ifType": "1.3.6.1.2.1.2.2.1.3",
        "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
        "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7",
        "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
        "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
        "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",
        "ifInErrors": "1.3.6.1.2.1.2.2.1.14",
        "ifOutErrors": "1.3.6.1.2.1.2.2.1.20",

        # 64-bit counters (ifXTable)
        "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
        "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10",
        "ifAlias": "1.3.6.1.2.1.31.1.1.1.18",

        # MikroTik specific
        "mtxrHlCpuLoad": "1.3.6.1.4.1.14988.1.1.3.14.0",
        "mtxrHlTemperature": "1.3.6.1.4.1.14988.1.1.3.10.0",
        "mtxrHlActiveFan": "1.3.6.1.4.1.14988.1.1.3.9.0",
    }

    async def poll_device(self, router_id: int) -> PollResult
    async def poll_interfaces(self, router_id: int) -> List[InterfaceMetric]
    async def get_system_info(self, router_id: int) -> SystemInfo
    async def calculate_rates(self, current: InterfaceMetric, previous: InterfaceMetric) -> Tuple[int, int]

    # Batch operations
    async def poll_all_devices(self) -> BatchPollResult
    async def discover_interfaces(self, router_id: int) -> List[InterfaceState]
```

---

### 1.3 Polling Tasks

**New file**: `app/tasks/monitoring_tasks.py`

```python
@celery_app.task(name="monitoring.poll_devices")
def poll_all_devices():
    """Poll all enabled devices for metrics.

    Runs every 5 minutes (configurable).
    """

@celery_app.task(name="monitoring.poll_device")
def poll_single_device(router_id: int):
    """Poll a single device (for on-demand refresh)."""

@celery_app.task(name="monitoring.check_device_status")
def check_device_status():
    """Check for DOWN devices and trigger alerts.

    Runs every minute.
    """

@celery_app.task(name="monitoring.aggregate_metrics")
def aggregate_metrics():
    """Aggregate raw metrics into hourly/daily rollups.

    Runs hourly.
    """

@celery_app.task(name="monitoring.cleanup_old_metrics")
def cleanup_old_metrics():
    """Delete old raw metrics based on retention policy.

    Runs daily at 3 AM.
    - Raw (5-min): Keep 7 days
    - Hourly: Keep 90 days
    - Daily: Keep 2 years
    """
```

---

## Part 2: Traffic Graphs & History

### 2.1 Aggregated Metrics Models

**Add to**: `app/models/snmp_metrics.py`

```python
class MetricAggregation(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class InterfaceMetricRollup(Base):
    """Aggregated interface metrics for historical graphs."""
    __tablename__ = "interface_metric_rollups"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), index=True)
    interface_index: Mapped[int]
    aggregation: Mapped[MetricAggregation]
    period_start: Mapped[datetime] = mapped_column(index=True)

    # Aggregated values
    avg_rx_rate_bps: Mapped[int]
    avg_tx_rate_bps: Mapped[int]
    max_rx_rate_bps: Mapped[int]
    max_tx_rate_bps: Mapped[int]
    min_rx_rate_bps: Mapped[int]
    min_tx_rate_bps: Mapped[int]
    p95_rx_rate_bps: Mapped[int]
    p95_tx_rate_bps: Mapped[int]

    # Totals
    total_rx_bytes: Mapped[int]
    total_tx_bytes: Mapped[int]

    # Availability
    samples_count: Mapped[int]
    uptime_percent: Mapped[float]

    __table_args__ = (
        Index("ix_metric_rollup_lookup", "router_id", "interface_index", "aggregation", "period_start"),
    )


class SubscriptionUsageMetric(Base):
    """Per-subscription bandwidth usage (from RADIUS + traffic correlation)."""
    __tablename__ = "subscription_usage_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    period_date: Mapped[date] = mapped_column(index=True)

    # Usage
    download_bytes: Mapped[int]
    upload_bytes: Mapped[int]
    session_count: Mapped[int]
    session_duration_seconds: Mapped[int]

    # Peak rates
    peak_download_bps: Mapped[Optional[int]]
    peak_upload_bps: Mapped[Optional[int]]

    __table_args__ = (
        Index("ix_sub_usage_lookup", "subscription_id", "period_date"),
    )
```

---

### 2.2 Traffic Graph Service

**New file**: `app/services/network/traffic_graphs.py`

```python
class TrafficGraphService:
    """Service for generating traffic graph data."""

    async def get_interface_traffic(
        self,
        router_id: int,
        interface_index: int,
        start_time: datetime,
        end_time: datetime,
        resolution: str = "auto"  # 5min, hourly, daily
    ) -> TrafficGraphData

    async def get_device_traffic(
        self,
        router_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> TrafficGraphData

    async def get_pop_traffic(
        self,
        pop_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> TrafficGraphData

    async def get_subscription_usage(
        self,
        subscription_id: int,
        start_date: date,
        end_date: date,
    ) -> UsageGraphData

    async def get_top_interfaces(
        self,
        router_id: int,
        metric: str = "traffic",  # traffic, errors, utilization
        limit: int = 10,
    ) -> List[InterfaceRanking]

    async def get_bandwidth_utilization(
        self,
        router_id: int,
        interface_index: int,
    ) -> UtilizationData
```

---

### 2.3 Web Routes & Templates

**New file**: `app/modules/network/traffic_routes.py`

```python
# Routes
GET /network/traffic                     # Traffic dashboard
GET /network/traffic/router/{id}         # Router traffic detail
GET /network/traffic/router/{id}/interface/{idx}  # Interface detail
GET /network/traffic/pop/{id}            # POP aggregate traffic

# HTMX partials for live graphs
GET /network/traffic/graph/{router_id}   # Returns chart data (JSON)
GET /network/traffic/top-talkers         # Top bandwidth consumers
```

**Templates**:
```
app/modules/network/templates/traffic/
├── pages/
│   ├── dashboard.html      # Overview with top routers, alerts
│   ├── router_detail.html  # Per-router with interface list
│   └── interface_detail.html  # Single interface deep dive
└── partials/
    ├── traffic_chart.html  # Reusable chart component
    ├── interface_row.html  # Interface list item
    └── utilization_bar.html  # Bandwidth utilization bar
```

**Chart Library**: Chart.js with streaming plugin for real-time updates

---

## Part 3: Alerting System

### 3.1 Alert Models

**New file**: `app/models/alerts.py`

```python
class AlertSeverity(str, Enum):
    CRITICAL = "critical"  # Immediate action required
    WARNING = "warning"    # Attention needed
    INFO = "info"          # Informational

class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class AlertType(str, Enum):
    # Device alerts
    DEVICE_DOWN = "device_down"
    DEVICE_UNREACHABLE = "device_unreachable"
    DEVICE_HIGH_CPU = "device_high_cpu"
    DEVICE_HIGH_MEMORY = "device_high_memory"
    DEVICE_HIGH_TEMP = "device_high_temp"

    # Interface alerts
    INTERFACE_DOWN = "interface_down"
    INTERFACE_ERRORS = "interface_errors"
    INTERFACE_HIGH_UTILIZATION = "interface_high_utilization"
    INTERFACE_FLAPPING = "interface_flapping"

    # Threshold alerts
    BANDWIDTH_THRESHOLD = "bandwidth_threshold"
    LATENCY_THRESHOLD = "latency_threshold"
    PACKET_LOSS = "packet_loss"

    # Subscription alerts
    USAGE_THRESHOLD = "usage_threshold"
    BUNDLE_LOW = "bundle_low"
    SESSION_LIMIT = "session_limit"


class AlertRule(Base):
    """Configurable alert rules/thresholds."""
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    alert_type: Mapped[AlertType]
    severity: Mapped[AlertSeverity]

    # Scope (optional - if null, applies globally)
    router_id: Mapped[Optional[int]] = mapped_column(ForeignKey("routers.id"))
    pop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pops.id"))
    interface_pattern: Mapped[Optional[str]]  # Regex for interface names

    # Thresholds
    threshold_value: Mapped[float]
    threshold_operator: Mapped[str]  # >, <, >=, <=, ==
    threshold_duration_seconds: Mapped[int] = mapped_column(default=0)  # Must exceed for N seconds

    # Notifications
    notify_channels: Mapped[List[str]] = mapped_column(JSONB)  # ["email", "slack", "sms"]
    notify_roles: Mapped[List[str]] = mapped_column(JSONB)  # ["noc", "admin"]
    cooldown_seconds: Mapped[int] = mapped_column(default=300)  # Don't re-alert for N seconds

    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Alert(Base):
    """Active or historical alerts."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alert_rules.id"))
    alert_type: Mapped[AlertType]
    severity: Mapped[AlertSeverity]
    status: Mapped[AlertStatus] = mapped_column(default=AlertStatus.ACTIVE, index=True)

    # Source
    router_id: Mapped[Optional[int]] = mapped_column(ForeignKey("routers.id"), index=True)
    interface_index: Mapped[Optional[int]]
    subscription_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subscriptions.id"))

    # Details
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[Optional[float]]
    threshold_value: Mapped[Optional[float]]
    details: Mapped[Optional[Dict]] = mapped_column(JSONB)

    # Lifecycle
    triggered_at: Mapped[datetime] = mapped_column(index=True)
    acknowledged_at: Mapped[Optional[datetime]]
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    resolved_at: Mapped[Optional[datetime]]
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    auto_resolved: Mapped[bool] = mapped_column(default=False)

    # Incident link
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("network_incidents.id"))

    # Notification tracking
    notifications_sent: Mapped[List[Dict]] = mapped_column(JSONB, default=list)

    __table_args__ = (
        Index("ix_alerts_active", "status", "triggered_at"),
    )
```

---

### 3.2 Alert Service

**New file**: `app/services/network/alerts.py`

```python
class AlertService:
    """Alert management and notification service."""

    # Alert lifecycle
    async def create_alert(self, data: AlertCreate) -> Alert
    async def acknowledge_alert(self, alert_id: int, user_id: int, notes: str = None) -> Alert
    async def resolve_alert(self, alert_id: int, user_id: int = None, auto: bool = False) -> Alert
    async def escalate_alert(self, alert_id: int) -> Alert

    # Rule evaluation
    async def evaluate_device_metrics(self, router_id: int, metrics: DeviceMetric) -> List[Alert]
    async def evaluate_interface_metrics(self, router_id: int, metrics: List[InterfaceMetric]) -> List[Alert]
    async def check_interface_flapping(self, router_id: int, interface_index: int) -> Optional[Alert]

    # Notifications
    async def send_alert_notification(self, alert: Alert) -> None
    async def send_escalation(self, alert: Alert) -> None
    async def send_resolution_notification(self, alert: Alert) -> None

    # Queries
    async def get_active_alerts(self, filters: AlertFilters) -> List[Alert]
    async def get_alert_history(self, filters: AlertFilters, pagination: PaginationParams) -> PaginatedResult
    async def get_alert_stats(self, period: str) -> AlertStats

    # Auto-resolution
    async def check_auto_resolve(self, alert: Alert, current_value: float) -> bool


class AlertNotifier:
    """Multi-channel alert notification."""

    async def notify_email(self, alert: Alert, recipients: List[str]) -> None
    async def notify_slack(self, alert: Alert, channel: str) -> None
    async def notify_sms(self, alert: Alert, phones: List[str]) -> None
    async def notify_webhook(self, alert: Alert, url: str) -> None
```

---

### 3.3 Alert Settings

**Add to settings schema**:

```python
"alerting": {
    1: {
        "label": "Alert Settings",
        "properties": {
            # Default thresholds
            "cpu_warning_percent": {"type": "integer", "default": 80},
            "cpu_critical_percent": {"type": "integer", "default": 95},
            "memory_warning_percent": {"type": "integer", "default": 80},
            "memory_critical_percent": {"type": "integer", "default": 95},
            "interface_utilization_warning": {"type": "integer", "default": 80},
            "interface_utilization_critical": {"type": "integer", "default": 95},
            "interface_error_threshold": {"type": "integer", "default": 100},
            "device_down_after_failures": {"type": "integer", "default": 3},
            "interface_flap_count": {"type": "integer", "default": 5},
            "interface_flap_window_seconds": {"type": "integer", "default": 300},

            # Notification settings
            "notification_cooldown_seconds": {"type": "integer", "default": 300},
            "escalation_after_minutes": {"type": "integer", "default": 30},
            "auto_resolve_enabled": {"type": "boolean", "default": True},

            # Channels
            "slack_webhook_url": {"type": "string", "sensitive": True},
            "pagerduty_routing_key": {"type": "string", "sensitive": True},
            "default_email_recipients": {"type": "array", "default": []},
        }
    }
}
```

---

## Part 4: Outage Detection & Incidents

### 4.1 Incident Model

**New file**: `app/models/network_incident.py`

```python
class IncidentSeverity(str, Enum):
    CRITICAL = "critical"   # Major outage
    MAJOR = "major"         # Significant impact
    MINOR = "minor"         # Limited impact
    MAINTENANCE = "maintenance"

class IncidentStatus(str, Enum):
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class NetworkIncident(Base):
    """Network incidents/outages."""
    __tablename__ = "network_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Info
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[IncidentSeverity]
    status: Mapped[IncidentStatus] = mapped_column(default=IncidentStatus.INVESTIGATING, index=True)

    # Scope
    affected_pop_ids: Mapped[List[int]] = mapped_column(JSONB, default=list)
    affected_router_ids: Mapped[List[int]] = mapped_column(JSONB, default=list)
    affected_subscription_count: Mapped[int] = mapped_column(default=0)

    # Timeline
    started_at: Mapped[datetime] = mapped_column(index=True)
    detected_at: Mapped[datetime]
    identified_at: Mapped[Optional[datetime]]
    resolved_at: Mapped[Optional[datetime]]

    # Post-mortem
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text)

    # Metrics
    total_downtime_seconds: Mapped[Optional[int]]
    mttr_seconds: Mapped[Optional[int]]  # Mean time to resolve

    # Auto-created from alerts?
    source_alert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alerts.id"))
    auto_created: Mapped[bool] = mapped_column(default=False)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class IncidentUpdate(Base):
    """Timeline updates for an incident."""
    __tablename__ = "incident_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("network_incidents.id"), index=True)

    status: Mapped[IncidentStatus]
    message: Mapped[str] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=True)  # Show on status page?

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime]


class IncidentAlert(Base):
    """Links alerts to incidents."""
    __tablename__ = "incident_alerts"

    incident_id: Mapped[int] = mapped_column(ForeignKey("network_incidents.id"), primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), primary_key=True)
    added_at: Mapped[datetime]
```

---

### 4.2 Outage Detection Service

**New file**: `app/services/network/outage_detection.py`

```python
class OutageDetectionService:
    """Automatic outage detection and incident creation."""

    async def detect_device_outages(self) -> List[NetworkIncident]
    """Scan for DOWN devices and create/update incidents."""

    async def detect_pop_outages(self) -> List[NetworkIncident]
    """Detect when multiple devices in a POP are down."""

    async def correlate_alerts(self, alerts: List[Alert]) -> Optional[NetworkIncident]
    """Group related alerts into a single incident."""

    async def calculate_affected_customers(self, incident: NetworkIncident) -> int
    """Count subscriptions affected by an incident."""

    async def auto_resolve_incident(self, incident: NetworkIncident) -> None
    """Check if all alerts are resolved and close incident."""


class IncidentService:
    """Incident lifecycle management."""

    # CRUD
    async def create_incident(self, data: IncidentCreate) -> NetworkIncident
    async def update_incident(self, incident_id: int, data: IncidentUpdate) -> NetworkIncident
    async def add_update(self, incident_id: int, status: IncidentStatus, message: str) -> IncidentUpdate
    async def resolve_incident(self, incident_id: int, resolution: str) -> NetworkIncident

    # Queries
    async def get_active_incidents(self) -> List[NetworkIncident]
    async def get_incident_timeline(self, incident_id: int) -> List[IncidentUpdate]
    async def get_incident_alerts(self, incident_id: int) -> List[Alert]
    async def get_affected_subscriptions(self, incident_id: int) -> List[Subscription]

    # Analytics
    async def get_incident_stats(self, period: str) -> IncidentStats
    async def get_mttr_trend(self, period: str) -> List[MTTRDataPoint]
```

---

## Part 5: Customer Usage Dashboard (CRM)

### 5.1 Customer Bandwidth Routes

**Add to**: `app/modules/subscriptions/routes.py`

```python
# Customer usage views
GET /subscriptions/{id}/usage              # Usage dashboard for subscription
GET /subscriptions/{id}/usage/graph        # HTMX partial for usage chart
GET /subscriptions/{id}/sessions           # Session history
GET /subscriptions/{id}/sessions/{sid}     # Session detail
```

**New templates**:
```
app/modules/subscriptions/templates/
├── usage/
│   ├── pages/dashboard.html    # Usage overview with graphs
│   └── partials/
│       ├── usage_chart.html    # Daily/weekly/monthly chart
│       ├── usage_stats.html    # Summary cards
│       └── session_row.html    # Session list item
└── sessions/
    ├── pages/list.html         # Session history with search
    └── pages/detail.html       # Single session deep dive
```

---

### 5.2 Usage Alerts for Customers

**Add alert types**:

```python
# Customer-facing usage alerts
USAGE_80_PERCENT = "usage_80_percent"      # 80% of data cap
USAGE_95_PERCENT = "usage_95_percent"      # 95% of data cap
UNUSUAL_USAGE = "unusual_usage"            # Usage spike detection
SESSION_LIMIT_REACHED = "session_limit"    # Max concurrent sessions
```

**Alert delivery**: Email, SMS, in-app notification

---

## Part 6: NOC Dashboard

### 6.1 NOC Overview Page

**New file**: `app/modules/network/noc_routes.py`

```python
GET /network/noc                  # NOC dashboard
GET /network/noc/devices          # Device status grid
GET /network/noc/alerts           # Active alerts list
GET /network/noc/incidents        # Active incidents
GET /network/noc/map              # Network topology (future)
```

**Dashboard Components**:
1. **Device Status Grid** - All routers with status indicators
2. **Active Alerts Panel** - Sorted by severity
3. **Active Incidents Panel** - With affected customer counts
4. **Traffic Overview** - Aggregate bandwidth graphs
5. **Top Issues** - Most common alert types

---

## Implementation Order

### Phase 1: Core Monitoring
1. SNMP models and migration
2. SNMP poller service (pysnmp integration)
3. Polling scheduled tasks
4. Basic device metrics collection

### Phase 2: Traffic & Visualization
5. Traffic graph service
6. Metric aggregation (rollups)
7. Traffic dashboard UI
8. Interface detail pages

### Phase 3: Alerting
9. Alert models and migration
10. Alert service and rule evaluation
11. Notification channels (email first)
12. Alert management UI

### Phase 4: Incidents
13. Incident models
14. Outage detection service
15. Incident dashboard
16. Customer impact calculation

### Phase 5: CRM Integration
17. Customer usage dashboard
18. Usage alerts
19. Session history UI

---

## Key Files Summary

| Component | File Path | Priority |
|-----------|-----------|----------|
| SNMP Models | `app/models/snmp_metrics.py` | P1 |
| Alert Models | `app/models/alerts.py` | P1 |
| Incident Models | `app/models/network_incident.py` | P1 |
| SNMP Poller | `app/services/network/snmp_poller.py` | P1 |
| Traffic Graphs | `app/services/network/traffic_graphs.py` | P1 |
| Alert Service | `app/services/network/alerts.py` | P1 |
| Outage Detection | `app/services/network/outage_detection.py` | P1 |
| Incident Service | `app/services/network/incidents.py` | P1 |
| Monitoring Tasks | `app/tasks/monitoring_tasks.py` | P1 |
| NOC Routes | `app/modules/network/noc_routes.py` | P1 |
| Traffic Routes | `app/modules/network/traffic_routes.py` | P1 |
| NOC Dashboard | `app/modules/network/templates/noc/` | P1 |
| Traffic Templates | `app/modules/network/templates/traffic/` | P1 |

---

## Dependencies

**Python packages**:
```
pysnmp>=5.0.0          # SNMP polling
pysnmp-lextudio>=5.0   # Updated SNMP library
chart.js               # Frontend charting (via CDN)
```

**Settings groups to add**:
- `snmp` - SNMP polling configuration
- `alerting` - Alert thresholds and notifications
- `monitoring` - Retention policies, polling intervals
