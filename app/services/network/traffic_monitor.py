"""Traffic Monitoring Service - Real-time bandwidth monitoring."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy import and_, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.router import Router
from app.models.traffic_metrics import TrafficMetric, TrafficThreshold, TrafficAlert
from app.models.subscription import Subscription
from app.utils.datetime_utils import utc_now
from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class TrafficSample:
    """Single traffic sample from polling."""
    interface: str
    interface_index: int
    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int
    rx_errors: int
    tx_errors: int
    oper_status: str
    admin_status: str


@dataclass
class InterfaceStats:
    """Calculated interface statistics."""
    interface: str
    current_rx_rate: int  # bps
    current_tx_rate: int  # bps
    avg_rx_rate: int
    avg_tx_rate: int
    peak_rx_rate: int
    peak_tx_rate: int
    total_rx_bytes: int
    total_tx_bytes: int
    utilization_percent: float


@dataclass
class TrafficDashboardStats:
    """Aggregate traffic statistics for dashboard."""
    total_interfaces: int
    interfaces_up: int
    interfaces_down: int
    total_rx_rate: int  # bps
    total_tx_rate: int  # bps
    total_rx_bytes_24h: int
    total_tx_bytes_24h: int
    active_alerts: int
    top_interfaces: List[InterfaceStats]


class TrafficMonitorService:
    """Service for traffic monitoring and alerting."""

    def __init__(self, session: AsyncSession, event_bus: Optional[EventBus] = None):
        self.session = session
        self.event_bus = event_bus
        self._last_samples: Dict[str, TrafficSample] = {}

    # =========================================================================
    # Sample Recording
    # =========================================================================

    async def record_samples(
        self,
        router_id: int,
        samples: List[TrafficSample],
        timestamp: Optional[datetime] = None,
    ) -> List[TrafficMetric]:
        """Record traffic samples from polling.

        Calculates rates from counter deltas between samples.
        """
        timestamp = timestamp or utc_now()
        metrics = []

        for sample in samples:
            # Calculate rates from previous sample
            sample_key = f"{router_id}:{sample.interface}"
            prev_sample = self._last_samples.get(sample_key)

            rx_rate = tx_rate = 0
            if prev_sample:
                # Calculate delta (handle counter wrap)
                rx_delta = sample.rx_bytes - prev_sample.rx_bytes
                tx_delta = sample.tx_bytes - prev_sample.tx_bytes

                if rx_delta < 0:
                    rx_delta = sample.rx_bytes  # Counter wrapped
                if tx_delta < 0:
                    tx_delta = sample.tx_bytes

                # Assume 5-minute polling interval (300 seconds)
                # Convert bytes to bits per second
                rx_rate = (rx_delta * 8) // 300
                tx_rate = (tx_delta * 8) // 300

            metric = TrafficMetric(
                router_id=router_id,
                interface=sample.interface,
                interface_index=sample.interface_index,
                timestamp=timestamp,
                rx_bytes=sample.rx_bytes,
                tx_bytes=sample.tx_bytes,
                rx_rate=rx_rate,
                tx_rate=tx_rate,
                rx_packets=sample.rx_packets,
                tx_packets=sample.tx_packets,
                rx_errors=sample.rx_errors,
                tx_errors=sample.tx_errors,
                oper_status=sample.oper_status,
                admin_status=sample.admin_status,
                aggregation="raw",
            )

            self.session.add(metric)
            metrics.append(metric)

            # Store for next calculation
            self._last_samples[sample_key] = sample

        await self.session.flush()

        # Check thresholds
        await self._check_thresholds(router_id, metrics)

        return metrics

    # =========================================================================
    # Threshold Management
    # =========================================================================

    async def create_threshold(
        self,
        name: str,
        metric: str,
        value: int,
        operator: str = "gt",
        router_id: Optional[int] = None,
        interface: Optional[str] = None,
        severity: str = "warning",
        duration_seconds: int = 300,
    ) -> TrafficThreshold:
        """Create a traffic threshold for alerting."""
        threshold = TrafficThreshold(
            router_id=router_id,
            interface=interface,
            name=name,
            metric=metric,
            operator=operator,
            value=value,
            severity=severity,
            duration_seconds=duration_seconds,
            is_active=True,
        )
        self.session.add(threshold)
        await self.session.flush()
        return threshold

    async def list_thresholds(
        self,
        router_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[TrafficThreshold]:
        """List traffic thresholds."""
        q = select(TrafficThreshold)

        if router_id:
            q = q.where(TrafficThreshold.router_id == router_id)
        if is_active is not None:
            q = q.where(TrafficThreshold.is_active == is_active)

        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def _check_thresholds(
        self,
        router_id: int,
        metrics: List[TrafficMetric],
    ) -> List[TrafficAlert]:
        """Check metrics against thresholds and create alerts."""
        # Get active thresholds for this router
        q = select(TrafficThreshold).where(
            and_(
                TrafficThreshold.is_active == True,
                (TrafficThreshold.router_id == router_id) | (TrafficThreshold.router_id.is_(None)),
            )
        )
        result = await self.session.execute(q)
        thresholds = list(result.scalars().all())

        alerts = []
        for metric in metrics:
            for threshold in thresholds:
                # Check if threshold applies to this interface
                if threshold.interface and threshold.interface != metric.interface:
                    continue

                # Get the metric value
                actual_value = getattr(metric, threshold.metric, None)
                if actual_value is None:
                    continue

                # Check threshold condition
                triggered = False
                if threshold.operator == "gt" and actual_value > threshold.value:
                    triggered = True
                elif threshold.operator == "lt" and actual_value < threshold.value:
                    triggered = True
                elif threshold.operator == "eq" and actual_value == threshold.value:
                    triggered = True

                if triggered:
                    alert = await self._create_alert(threshold, metric, actual_value)
                    alerts.append(alert)

        return alerts

    async def _create_alert(
        self,
        threshold: TrafficThreshold,
        metric: TrafficMetric,
        actual_value: int,
    ) -> TrafficAlert:
        """Create a traffic alert."""
        message = (
            f"{threshold.name}: {metric.interface} {threshold.metric} is "
            f"{actual_value} ({threshold.operator} threshold {threshold.value})"
        )

        alert = TrafficAlert(
            threshold_id=threshold.id,
            router_id=metric.router_id,
            interface=metric.interface,
            metric=threshold.metric,
            threshold_value=threshold.value,
            actual_value=actual_value,
            severity=threshold.severity,
            message=message,
            status="active",
        )

        self.session.add(alert)

        # Update threshold stats
        threshold.last_triggered_at = utc_now()
        threshold.trigger_count += 1

        await self.session.flush()

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "traffic.alert_triggered",
                {
                    "alert_id": alert.id,
                    "router_id": metric.router_id,
                    "interface": metric.interface,
                    "severity": threshold.severity,
                    "message": message,
                },
            )

        logger.warning(
            "Traffic alert triggered",
            extra={
                "alert_id": alert.id,
                "interface": metric.interface,
                "metric": threshold.metric,
                "value": actual_value,
            },
        )

        return alert

    # =========================================================================
    # Alert Management
    # =========================================================================

    async def list_alerts(
        self,
        router_id: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[TrafficAlert]:
        """List traffic alerts."""
        q = select(TrafficAlert).order_by(TrafficAlert.triggered_at.desc()).limit(limit)

        if router_id:
            q = q.where(TrafficAlert.router_id == router_id)
        if status:
            q = q.where(TrafficAlert.status == status)
        if severity:
            q = q.where(TrafficAlert.severity == severity)

        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def acknowledge_alert(
        self,
        alert_id: int,
        user_id: int,
    ) -> TrafficAlert:
        """Acknowledge a traffic alert."""
        alert = await self.session.get(TrafficAlert, alert_id)
        if alert:
            alert.status = "acknowledged"
            alert.acknowledged_by_id = user_id
            alert.acknowledged_at = utc_now()
            await self.session.flush()
        return alert

    async def resolve_alert(self, alert_id: int) -> TrafficAlert:
        """Resolve a traffic alert."""
        alert = await self.session.get(TrafficAlert, alert_id)
        if alert:
            alert.status = "resolved"
            alert.resolved_at = utc_now()
            await self.session.flush()
        return alert

    # =========================================================================
    # Statistics & Analytics
    # =========================================================================

    async def get_interface_stats(
        self,
        router_id: int,
        interface: str,
        period_hours: int = 24,
    ) -> InterfaceStats:
        """Get statistics for a specific interface."""
        cutoff = utc_now() - timedelta(hours=period_hours)

        q = select(
            func.avg(TrafficMetric.rx_rate).label("avg_rx"),
            func.avg(TrafficMetric.tx_rate).label("avg_tx"),
            func.max(TrafficMetric.rx_rate).label("peak_rx"),
            func.max(TrafficMetric.tx_rate).label("peak_tx"),
            func.sum(TrafficMetric.rx_bytes).label("total_rx"),
            func.sum(TrafficMetric.tx_bytes).label("total_tx"),
        ).where(
            and_(
                TrafficMetric.router_id == router_id,
                TrafficMetric.interface == interface,
                TrafficMetric.timestamp >= cutoff,
            )
        )

        result = await self.session.execute(q)
        row = result.first()

        # Get latest sample for current rate
        latest_q = select(TrafficMetric).where(
            and_(
                TrafficMetric.router_id == router_id,
                TrafficMetric.interface == interface,
            )
        ).order_by(TrafficMetric.timestamp.desc()).limit(1)

        latest_result = await self.session.execute(latest_q)
        latest = latest_result.scalar()

        return InterfaceStats(
            interface=interface,
            current_rx_rate=latest.rx_rate if latest else 0,
            current_tx_rate=latest.tx_rate if latest else 0,
            avg_rx_rate=int(row.avg_rx or 0),
            avg_tx_rate=int(row.avg_tx or 0),
            peak_rx_rate=int(row.peak_rx or 0),
            peak_tx_rate=int(row.peak_tx or 0),
            total_rx_bytes=int(row.total_rx or 0),
            total_tx_bytes=int(row.total_tx or 0),
            utilization_percent=0.0,  # Would need link speed to calculate
        )

    async def get_dashboard_stats(
        self,
        router_id: Optional[int] = None,
    ) -> TrafficDashboardStats:
        """Get aggregate traffic statistics for dashboard."""
        cutoff = utc_now() - timedelta(hours=24)

        # Base query
        base_filter = [TrafficMetric.timestamp >= cutoff]
        if router_id:
            base_filter.append(TrafficMetric.router_id == router_id)

        # Get latest metrics for each interface
        subq = (
            select(
                TrafficMetric.router_id,
                TrafficMetric.interface,
                func.max(TrafficMetric.timestamp).label("max_ts"),
            )
            .where(and_(*base_filter))
            .group_by(TrafficMetric.router_id, TrafficMetric.interface)
            .subquery()
        )

        latest_q = select(TrafficMetric).join(
            subq,
            and_(
                TrafficMetric.router_id == subq.c.router_id,
                TrafficMetric.interface == subq.c.interface,
                TrafficMetric.timestamp == subq.c.max_ts,
            ),
        )

        result = await self.session.execute(latest_q)
        latest_metrics = list(result.scalars().all())

        # Calculate stats
        interfaces_up = sum(1 for m in latest_metrics if m.oper_status == "up")
        interfaces_down = sum(1 for m in latest_metrics if m.oper_status == "down")
        total_rx_rate = sum(m.rx_rate for m in latest_metrics)
        total_tx_rate = sum(m.tx_rate for m in latest_metrics)

        # 24h totals
        totals_q = select(
            func.sum(TrafficMetric.rx_bytes).label("total_rx"),
            func.sum(TrafficMetric.tx_bytes).label("total_tx"),
        ).where(and_(*base_filter))

        totals_result = await self.session.execute(totals_q)
        totals = totals_result.first()

        # Active alerts
        alerts_q = select(func.count(TrafficAlert.id)).where(TrafficAlert.status == "active")
        if router_id:
            alerts_q = alerts_q.where(TrafficAlert.router_id == router_id)

        alerts_result = await self.session.execute(alerts_q)
        active_alerts = alerts_result.scalar() or 0

        # Top interfaces by traffic
        sorted_metrics = sorted(
            latest_metrics,
            key=lambda m: m.rx_rate + m.tx_rate,
            reverse=True,
        )[:10]

        top_interfaces = [
            InterfaceStats(
                interface=m.interface,
                current_rx_rate=m.rx_rate,
                current_tx_rate=m.tx_rate,
                avg_rx_rate=0,
                avg_tx_rate=0,
                peak_rx_rate=0,
                peak_tx_rate=0,
                total_rx_bytes=0,
                total_tx_bytes=0,
                utilization_percent=0.0,
            )
            for m in sorted_metrics
        ]

        return TrafficDashboardStats(
            total_interfaces=len(latest_metrics),
            interfaces_up=interfaces_up,
            interfaces_down=interfaces_down,
            total_rx_rate=total_rx_rate,
            total_tx_rate=total_tx_rate,
            total_rx_bytes_24h=int(totals.total_rx or 0),
            total_tx_bytes_24h=int(totals.total_tx or 0),
            active_alerts=active_alerts,
            top_interfaces=top_interfaces,
        )

    async def get_traffic_history(
        self,
        router_id: int,
        interface: str,
        period_hours: int = 24,
        aggregation: str = "raw",
    ) -> List[Dict[str, Any]]:
        """Get traffic history for graphing."""
        cutoff = utc_now() - timedelta(hours=period_hours)

        q = select(TrafficMetric).where(
            and_(
                TrafficMetric.router_id == router_id,
                TrafficMetric.interface == interface,
                TrafficMetric.timestamp >= cutoff,
                TrafficMetric.aggregation == aggregation,
            )
        ).order_by(TrafficMetric.timestamp)

        result = await self.session.execute(q)
        metrics = result.scalars().all()

        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "rx_rate": m.rx_rate,
                "tx_rate": m.tx_rate,
                "rx_bytes": m.rx_bytes,
                "tx_bytes": m.tx_bytes,
            }
            for m in metrics
        ]

    # =========================================================================
    # Data Retention
    # =========================================================================

    async def aggregate_hourly(self) -> int:
        """Aggregate raw metrics to hourly summaries."""
        # Get distinct router/interface combinations with raw data older than 1 hour
        cutoff = utc_now() - timedelta(hours=1)

        # For each combination, calculate hourly aggregates and insert
        # This would be implemented as a scheduled task
        # Returns count of metrics aggregated
        return 0

    async def cleanup_old_metrics(
        self,
        raw_retention_days: int = 7,
        hourly_retention_days: int = 90,
        daily_retention_days: int = 730,
    ) -> Dict[str, int]:
        """Clean up old traffic metrics based on retention policy."""
        counts = {}

        # Delete raw metrics older than retention
        raw_cutoff = utc_now() - timedelta(days=raw_retention_days)
        raw_q = delete(TrafficMetric).where(
            and_(
                TrafficMetric.aggregation == "raw",
                TrafficMetric.timestamp < raw_cutoff,
            )
        )
        result = await self.session.execute(raw_q)
        counts["raw"] = result.rowcount

        # Delete hourly metrics
        hourly_cutoff = utc_now() - timedelta(days=hourly_retention_days)
        hourly_q = delete(TrafficMetric).where(
            and_(
                TrafficMetric.aggregation == "hourly",
                TrafficMetric.timestamp < hourly_cutoff,
            )
        )
        result = await self.session.execute(hourly_q)
        counts["hourly"] = result.rowcount

        # Delete daily metrics
        daily_cutoff = utc_now() - timedelta(days=daily_retention_days)
        daily_q = delete(TrafficMetric).where(
            and_(
                TrafficMetric.aggregation == "daily",
                TrafficMetric.timestamp < daily_cutoff,
            )
        )
        result = await self.session.execute(daily_q)
        counts["daily"] = result.rowcount

        logger.info(
            "Traffic metrics cleanup complete",
            extra={"deleted": counts},
        )

        return counts
