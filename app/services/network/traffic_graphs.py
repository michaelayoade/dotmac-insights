"""Traffic Graph Service.

Provides traffic data retrieval and aggregation for visualization.
Supports multiple time ranges and resolutions for bandwidth graphs.

Usage:
    async with async_session_maker() as db:
        service = TrafficGraphService(db)
        data = await service.get_interface_traffic(
            router_id=1,
            interface_index=1,
            start_time=datetime.now() - timedelta(hours=24),
            end_time=datetime.now(),
        )
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, TYPE_CHECKING

from sqlalchemy import and_, select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.snmp_metrics import (
    DeviceMetric,
    InterfaceMetric,
    InterfaceMetricRollup,
    InterfaceState,
    SNMPPollingConfig,
    MetricAggregation,
)
from app.models.router import Router
from app.models.pop import Pop
from app.models.alerts import Alert, AlertStatus
from app.models.network_incident import NetworkIncident, IncidentStatus
from app.services.network.traffic_types import (
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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TrafficGraphService:
    """Service for traffic visualization and NOC dashboard data."""

    def __init__(self, db: AsyncSession):
        """Initialize the traffic graph service.

        Args:
            db: Async database session
        """
        self.db = db

    # =========================================================================
    # Interface Traffic Data
    # =========================================================================

    async def get_interface_traffic(
        self,
        router_id: int,
        interface_index: int,
        start_time: datetime,
        end_time: datetime,
        resolution: str = "auto",
    ) -> TrafficGraphData:
        """Get traffic data for a specific interface.

        Args:
            router_id: Router ID
            interface_index: Interface index
            start_time: Start of time range
            end_time: End of time range
            resolution: Data resolution (auto, 5min, hourly, daily)

        Returns:
            TrafficGraphData with data points
        """
        # Determine resolution based on time range if auto
        if resolution == "auto":
            resolution = self._determine_resolution(start_time, end_time)

        data = TrafficGraphData(
            router_id=router_id,
            interface_index=interface_index,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
        )

        # Get interface name
        state_result = await self.db.execute(
            select(InterfaceState).where(
                and_(
                    InterfaceState.router_id == router_id,
                    InterfaceState.interface_index == interface_index,
                )
            )
        )
        state = state_result.scalar_one_or_none()
        if state:
            data.interface_name = state.interface_name

        # Query appropriate table based on resolution
        if resolution == "5min":
            data.data_points = await self._get_raw_metrics(
                router_id, interface_index, start_time, end_time
            )
        else:
            aggregation = (
                MetricAggregation.HOURLY.value
                if resolution == "hourly"
                else MetricAggregation.DAILY.value
            )
            data.data_points = await self._get_rollup_metrics(
                router_id, interface_index, start_time, end_time, aggregation
            )

        # Calculate summary stats
        if data.data_points:
            rx_rates = [dp.rx_rate_bps for dp in data.data_points]
            tx_rates = [dp.tx_rate_bps for dp in data.data_points]

            data.avg_rx_rate_bps = int(sum(rx_rates) / len(rx_rates))
            data.avg_tx_rate_bps = int(sum(tx_rates) / len(tx_rates))
            data.max_rx_rate_bps = max(rx_rates)
            data.max_tx_rate_bps = max(tx_rates)
            data.total_rx_bytes = sum(dp.rx_bytes for dp in data.data_points)
            data.total_tx_bytes = sum(dp.tx_bytes for dp in data.data_points)

            # Calculate P95
            sorted_rx = sorted(rx_rates)
            sorted_tx = sorted(tx_rates)
            p95_idx = int(len(sorted_rx) * 0.95)
            data.p95_rx_rate_bps = sorted_rx[p95_idx] if sorted_rx else 0
            data.p95_tx_rate_bps = sorted_tx[p95_idx] if sorted_tx else 0

        return data

    async def get_router_traffic(
        self,
        router_id: int,
        start_time: datetime,
        end_time: datetime,
        resolution: str = "auto",
    ) -> RouterTrafficSummary:
        """Get aggregate traffic data for a router.

        Args:
            router_id: Router ID
            start_time: Start of time range
            end_time: End of time range
            resolution: Data resolution

        Returns:
            RouterTrafficSummary with per-interface data
        """
        # Get router info
        router_result = await self.db.execute(
            select(Router)
            .options(selectinload(Router.pop))
            .where(Router.id == router_id)
        )
        router = router_result.scalar_one_or_none()
        if not router:
            return RouterTrafficSummary(router_id=router_id, router_name="Unknown")

        summary = RouterTrafficSummary(
            router_id=router_id,
            router_name=router.name or f"Router {router_id}",
            pop_name=router.pop.name if router.pop else None,
        )

        # Get interface states
        states_result = await self.db.execute(
            select(InterfaceState).where(InterfaceState.router_id == router_id)
        )
        states = list(states_result.scalars().all())

        summary.total_interfaces = len(states)
        summary.up_interfaces = sum(1 for s in states if s.oper_status == "up")
        summary.down_interfaces = summary.total_interfaces - summary.up_interfaces

        # Get traffic for each interface
        for state in states:
            traffic = await self.get_interface_traffic(
                router_id,
                state.interface_index,
                start_time,
                end_time,
                resolution,
            )

            interface_summary = InterfaceTrafficSummary(
                router_id=router_id,
                interface_index=state.interface_index,
                interface_name=state.interface_name,
                oper_status=state.oper_status or "unknown",
                avg_rx_rate_bps=traffic.avg_rx_rate_bps,
                avg_tx_rate_bps=traffic.avg_tx_rate_bps,
                max_rx_rate_bps=traffic.max_rx_rate_bps,
                max_tx_rate_bps=traffic.max_tx_rate_bps,
                total_rx_bytes=traffic.total_rx_bytes,
                total_tx_bytes=traffic.total_tx_bytes,
                last_updated=state.last_updated,
            )

            # Get current rate from latest metric
            if traffic.data_points:
                latest = traffic.data_points[-1]
                interface_summary.current_rx_rate_bps = latest.rx_rate_bps
                interface_summary.current_tx_rate_bps = latest.tx_rate_bps

            summary.interfaces.append(interface_summary)
            summary.aggregate_rx_rate_bps += interface_summary.current_rx_rate_bps
            summary.aggregate_tx_rate_bps += interface_summary.current_tx_rate_bps

        # Get last poll info
        poll_config_result = await self.db.execute(
            select(SNMPPollingConfig).where(SNMPPollingConfig.router_id == router_id)
        )
        poll_config = poll_config_result.scalar_one_or_none()
        if poll_config:
            summary.last_poll = poll_config.last_poll_at
            summary.poll_status = poll_config.last_poll_status or "unknown"

        return summary

    async def get_top_interfaces(
        self,
        limit: int = 10,
        pop_id: Optional[int] = None,
        metric: str = "total_rate",  # total_rate, rx_rate, tx_rate
    ) -> List[TopInterface]:
        """Get top interfaces by traffic.

        Args:
            limit: Max interfaces to return
            pop_id: Optional POP filter
            metric: Metric to rank by

        Returns:
            List of TopInterface sorted by metric
        """
        # Get latest interface metrics with router info
        query = (
            select(
                InterfaceMetric,
                Router.id.label("router_id"),
                Router.name.label("router_name"),
            )
            .join(Router, Router.id == InterfaceMetric.router_id)
            .where(InterfaceMetric.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=10))
        )

        if pop_id:
            query = query.where(Router.pop_id == pop_id)

        # Order by metric
        if metric == "rx_rate":
            query = query.order_by(desc(InterfaceMetric.rx_rate_bps))
        elif metric == "tx_rate":
            query = query.order_by(desc(InterfaceMetric.tx_rate_bps))
        else:
            query = query.order_by(
                desc(InterfaceMetric.rx_rate_bps + InterfaceMetric.tx_rate_bps)
            )

        query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        return [
            TopInterface(
                router_id=row.router_id,
                router_name=row.router_name or f"Router {row.router_id}",
                interface_index=row.InterfaceMetric.interface_index,
                interface_name=row.InterfaceMetric.interface_name,
                rx_rate_bps=row.InterfaceMetric.rx_rate_bps or 0,
                tx_rate_bps=row.InterfaceMetric.tx_rate_bps or 0,
                total_rate_bps=(row.InterfaceMetric.rx_rate_bps or 0)
                + (row.InterfaceMetric.tx_rate_bps or 0),
            )
            for row in rows
        ]

    # =========================================================================
    # NOC Dashboard Data
    # =========================================================================

    async def get_noc_dashboard_stats(self) -> NOCDashboardStats:
        """Get aggregate statistics for NOC dashboard.

        Returns:
            NOCDashboardStats with all metrics
        """
        stats = NOCDashboardStats()

        # Router counts
        router_counts = await self.db.execute(
            select(
                func.count(Router.id).label("total"),
            ).where(Router.is_deleted == False)
        )
        row = router_counts.first()
        stats.total_routers = row.total if row else 0

        # Get online/offline from polling configs
        poll_stats = await self.db.execute(
            select(
                SNMPPollingConfig.last_poll_status,
                func.count(SNMPPollingConfig.id),
            )
            .where(SNMPPollingConfig.is_enabled == True)
            .group_by(SNMPPollingConfig.last_poll_status)
        )
        for status, count in poll_stats:
            if status == "success":
                stats.online_routers = count
            elif status in ("timeout", "error", "unreachable"):
                stats.offline_routers += count

        # Alert counts
        alert_counts = await self.db.execute(
            select(
                Alert.severity,
                func.count(Alert.id),
            )
            .where(Alert.status == AlertStatus.ACTIVE.value)
            .group_by(Alert.severity)
        )
        for severity, count in alert_counts:
            stats.total_active_alerts += count
            if severity == "critical":
                stats.critical_alerts = count
            elif severity == "warning":
                stats.warning_alerts = count
            elif severity == "info":
                stats.info_alerts = count

        # Incident counts
        incident_counts = await self.db.execute(
            select(
                NetworkIncident.status,
                func.count(NetworkIncident.id),
            )
            .where(NetworkIncident.status != IncidentStatus.RESOLVED.value)
            .group_by(NetworkIncident.status)
        )
        for status, count in incident_counts:
            stats.active_incidents += count
            if status == IncidentStatus.INVESTIGATING.value:
                stats.investigating_incidents = count

        # Resolved today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        resolved_today = await self.db.execute(
            select(func.count(NetworkIncident.id)).where(
                and_(
                    NetworkIncident.status == IncidentStatus.RESOLVED.value,
                    NetworkIncident.resolved_at >= today_start,
                )
            )
        )
        stats.resolved_today = resolved_today.scalar() or 0

        # Interface counts
        interface_counts = await self.db.execute(
            select(
                InterfaceState.oper_status,
                func.count(InterfaceState.id),
            ).group_by(InterfaceState.oper_status)
        )
        for status, count in interface_counts:
            stats.total_interfaces += count
            if status == "up":
                stats.up_interfaces = count
            else:
                stats.down_interfaces += count

        # Aggregate traffic from latest metrics
        traffic_stats = await self.db.execute(
            select(
                func.sum(InterfaceMetric.rx_rate_bps),
                func.sum(InterfaceMetric.tx_rate_bps),
            ).where(
                InterfaceMetric.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=10)
            )
        )
        row = traffic_stats.first()
        if row:
            stats.total_rx_rate_bps = row[0] or 0
            stats.total_tx_rate_bps = row[1] or 0

        return stats

    async def get_device_status_cards(
        self,
        pop_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[DeviceStatusCard]:
        """Get device status cards for NOC grid display.

        Args:
            pop_id: Optional POP filter
            status_filter: Optional status filter (online, offline, warning)
            limit: Max devices to return

        Returns:
            List of DeviceStatusCard
        """
        # Build query
        query = (
            select(Router, SNMPPollingConfig, Pop)
            .outerjoin(SNMPPollingConfig, SNMPPollingConfig.router_id == Router.id)
            .outerjoin(Pop, Pop.id == Router.pop_id)
            .where(Router.is_deleted == False)
        )

        if pop_id:
            query = query.where(Router.pop_id == pop_id)

        query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        cards = []
        for router, poll_config, pop in rows:
            # Determine status
            if not poll_config or not poll_config.is_enabled:
                status = "unknown"
            elif poll_config.last_poll_status == "success":
                status = "online"
            elif poll_config.last_poll_status in ("timeout", "error", "unreachable"):
                status = "offline"
            else:
                status = "warning"

            # Get latest device metrics
            metrics_result = await self.db.execute(
                select(DeviceMetric)
                .where(DeviceMetric.router_id == router.id)
                .order_by(desc(DeviceMetric.timestamp))
                .limit(1)
            )
            latest_metrics = metrics_result.scalar_one_or_none()

            # Get active alert count
            alert_count_result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.router_id == router.id,
                        Alert.status == AlertStatus.ACTIVE.value,
                    )
                )
            )
            active_alerts = alert_count_result.scalar() or 0

            card = DeviceStatusCard(
                router_id=router.id,
                router_name=router.name or f"Router {router.id}",
                pop_name=pop.name if pop else None,
                ip_address=router.ip_host,
                status=status,
                active_alerts=active_alerts,
                last_poll=poll_config.last_poll_at if poll_config else None,
                poll_status=poll_config.last_poll_status if poll_config else "unknown",
            )

            if latest_metrics:
                card.cpu_percent = latest_metrics.cpu_percent
                card.memory_percent = latest_metrics.memory_percent
                card.temperature = latest_metrics.temperature
                card.uptime_seconds = latest_metrics.uptime_seconds

            # Apply status filter
            if status_filter and card.status != status_filter:
                continue

            cards.append(card)

        return cards

    async def get_recent_alerts(
        self,
        limit: int = 20,
        severity: Optional[str] = None,
    ) -> List[AlertSummaryCard]:
        """Get recent alerts for NOC display.

        Args:
            limit: Max alerts to return
            severity: Optional severity filter

        Returns:
            List of AlertSummaryCard
        """
        query = (
            select(Alert, Router)
            .outerjoin(Router, Router.id == Alert.router_id)
            .where(Alert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]))
            .order_by(desc(Alert.triggered_at))
        )

        if severity:
            query = query.where(Alert.severity == severity)

        query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        now = datetime.now(timezone.utc)
        return [
            AlertSummaryCard(
                alert_id=alert.id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                status=alert.status,
                title=alert.title,
                router_name=router.name if router else None,
                interface_name=alert.interface_name,
                triggered_at=alert.triggered_at,
                duration_minutes=int((now - alert.triggered_at).total_seconds() / 60)
                if alert.triggered_at
                else None,
                acknowledged=alert.acknowledged_at is not None,
            )
            for alert, router in rows
        ]

    async def get_active_incidents(
        self,
        limit: int = 10,
    ) -> List[IncidentSummaryCard]:
        """Get active incidents for NOC display.

        Args:
            limit: Max incidents to return

        Returns:
            List of IncidentSummaryCard
        """
        query = (
            select(NetworkIncident)
            .where(NetworkIncident.status != IncidentStatus.RESOLVED.value)
            .order_by(desc(NetworkIncident.started_at))
            .limit(limit)
        )
        result = await self.db.execute(query)
        incidents = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        return [
            IncidentSummaryCard(
                incident_id=inc.id,
                title=inc.title,
                severity=inc.severity,
                status=inc.status,
                affected_routers=len(inc.affected_router_ids or []),
                affected_customers=inc.affected_subscription_count,
                started_at=inc.started_at,
                duration_minutes=int((now - inc.started_at).total_seconds() / 60)
                if inc.started_at
                else None,
            )
            for inc in incidents
        ]

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _determine_resolution(self, start_time: datetime, end_time: datetime) -> str:
        """Determine appropriate resolution based on time range.

        Args:
            start_time: Start of range
            end_time: End of range

        Returns:
            Resolution string (5min, hourly, daily)
        """
        delta = end_time - start_time

        if delta <= timedelta(hours=6):
            return "5min"
        elif delta <= timedelta(days=7):
            return "hourly"
        else:
            return "daily"

    async def _get_raw_metrics(
        self,
        router_id: int,
        interface_index: int,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TrafficDataPoint]:
        """Get raw 5-minute interval metrics.

        Args:
            router_id: Router ID
            interface_index: Interface index
            start_time: Start of range
            end_time: End of range

        Returns:
            List of TrafficDataPoint
        """
        query = (
            select(InterfaceMetric)
            .where(
                and_(
                    InterfaceMetric.router_id == router_id,
                    InterfaceMetric.interface_index == interface_index,
                    InterfaceMetric.timestamp >= start_time,
                    InterfaceMetric.timestamp <= end_time,
                )
            )
            .order_by(InterfaceMetric.timestamp)
        )
        result = await self.db.execute(query)
        metrics = list(result.scalars().all())

        return [
            TrafficDataPoint(
                timestamp=m.timestamp,
                rx_rate_bps=m.rx_rate_bps or 0,
                tx_rate_bps=m.tx_rate_bps or 0,
                rx_bytes=m.rx_bytes or 0,
                tx_bytes=m.tx_bytes or 0,
            )
            for m in metrics
        ]

    async def _get_rollup_metrics(
        self,
        router_id: int,
        interface_index: int,
        start_time: datetime,
        end_time: datetime,
        aggregation: str,
    ) -> List[TrafficDataPoint]:
        """Get rolled-up metrics (hourly or daily).

        Args:
            router_id: Router ID
            interface_index: Interface index
            start_time: Start of range
            end_time: End of range
            aggregation: Aggregation level

        Returns:
            List of TrafficDataPoint
        """
        query = (
            select(InterfaceMetricRollup)
            .where(
                and_(
                    InterfaceMetricRollup.router_id == router_id,
                    InterfaceMetricRollup.interface_index == interface_index,
                    InterfaceMetricRollup.aggregation == aggregation,
                    InterfaceMetricRollup.period_start >= start_time,
                    InterfaceMetricRollup.period_start <= end_time,
                )
            )
            .order_by(InterfaceMetricRollup.period_start)
        )
        result = await self.db.execute(query)
        rollups = list(result.scalars().all())

        return [
            TrafficDataPoint(
                timestamp=r.period_start,
                rx_rate_bps=r.avg_rx_rate_bps or 0,
                tx_rate_bps=r.avg_tx_rate_bps or 0,
                rx_bytes=r.total_rx_bytes or 0,
                tx_bytes=r.total_tx_bytes or 0,
            )
            for r in rollups
        ]
