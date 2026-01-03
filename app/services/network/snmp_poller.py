"""SNMP Poller Service.

Orchestrates SNMP polling of network devices and stores metrics.
Handles batch polling, rate calculation, and metric persistence.

Usage:
    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        result = await poller.poll_all_devices()
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, TYPE_CHECKING

from sqlalchemy import and_, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.snmp import (
    SNMPClient,
    DevicePollingResult,
    InterfaceData,
    PYSNMP_AVAILABLE,
)
from app.integrations.snmp.exceptions import SNMPError
from app.models.snmp_metrics import (
    SNMPPollingConfig,
    DeviceMetric,
    InterfaceMetric,
    InterfaceState,
    InterfaceMetricRollup,
    PollStatus,
    MetricAggregation,
    InterfaceOperStatus,
)
from app.models.router import Router
from app.services.network.snmp_types import (
    PollingBatchResult,
    RollupResult,
    CleanupResult,
    PollStatistics,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SNMPPollerService:
    """Service for SNMP polling and metric storage.

    Polls network devices via SNMP, calculates rates, and stores
    time-series metrics for monitoring and visualization.
    """

    # Default polling settings
    DEFAULT_BATCH_SIZE = 50
    DEFAULT_CONCURRENCY = 10

    # Retention periods (in days)
    RAW_RETENTION_DAYS = 7
    HOURLY_RETENTION_DAYS = 90
    DAILY_RETENTION_DAYS = 730  # 2 years

    def __init__(self, db: AsyncSession):
        """Initialize the poller service.

        Args:
            db: Async database session
        """
        self.db = db

    async def poll_all_devices(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> PollingBatchResult:
        """Poll all enabled devices.

        Args:
            batch_size: Number of devices per batch
            concurrency: Max concurrent polls

        Returns:
            PollingBatchResult with statistics
        """
        if not PYSNMP_AVAILABLE:
            logger.warning("SNMP polling skipped: pysnmp not available")
            return PollingBatchResult(
                timestamp=datetime.now(timezone.utc),
                skipped=1,
            )

        start_time = time.monotonic()
        result = PollingBatchResult(timestamp=datetime.now(timezone.utc))

        # Get all enabled polling configs
        configs = await self._get_enabled_configs()
        result.total_routers = len(configs)

        if not configs:
            return result

        # Process in batches with concurrency limit
        semaphore = asyncio.Semaphore(concurrency)

        async def poll_with_semaphore(config: SNMPPollingConfig):
            async with semaphore:
                return await self._poll_device(config)

        # Create tasks for all configs
        tasks = [poll_with_semaphore(config) for config in configs]

        # Execute all polls
        poll_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for config, poll_result in zip(configs, poll_results):
            if isinstance(poll_result, Exception):
                result.failed += 1
                result.errors[config.router_id] = str(poll_result)
            elif poll_result and poll_result.success:
                result.successful += 1
            else:
                result.failed += 1
                if poll_result and poll_result.error:
                    result.errors[config.router_id] = poll_result.error

        result.duration_seconds = time.monotonic() - start_time

        logger.info(
            "SNMP polling batch complete",
            extra={
                "total": result.total_routers,
                "successful": result.successful,
                "failed": result.failed,
                "duration_seconds": result.duration_seconds,
            },
        )

        return result

    async def poll_device(self, router_id: int) -> Optional[DevicePollingResult]:
        """Poll a single device by router ID.

        Args:
            router_id: Router ID to poll

        Returns:
            DevicePollingResult or None if not configured
        """
        if not PYSNMP_AVAILABLE:
            logger.warning(f"SNMP polling skipped for router {router_id}: pysnmp not available")
            return None

        config = await self._get_config(router_id)
        if not config:
            logger.warning(f"No SNMP config found for router {router_id}")
            return None

        return await self._poll_device(config)

    async def _poll_device(self, config: SNMPPollingConfig) -> Optional[DevicePollingResult]:
        """Execute poll for a single device and store metrics.

        Args:
            config: SNMP polling configuration

        Returns:
            DevicePollingResult
        """
        # Get router IP
        router = await self.db.get(Router, config.router_id)
        if not router or not router.ip:
            logger.warning(f"Router {config.router_id} not found or has no IP")
            await self._update_poll_status(
                config,
                PollStatus.ERROR,
                error="Router not found or has no IP address",
            )
            return None

        try:
            async with SNMPClient(router.ip, config, config.router_id) as client:
                result = await client.poll_device()

            if result.success:
                # Store metrics
                await self._store_device_metric(config.router_id, result)
                await self._store_interface_metrics(config.router_id, result)
                await self._update_interface_states(config.router_id, result)

                # Update config status
                await self._update_poll_status(config, PollStatus.SUCCESS)
            else:
                # Map error to status
                status = self._error_to_status(result.error)
                await self._update_poll_status(config, status, error=result.error)

            return result

        except SNMPError as e:
            status = self._error_to_status(str(e))
            await self._update_poll_status(config, status, error=str(e))
            return DevicePollingResult(
                router_id=config.router_id,
                timestamp=datetime.now(timezone.utc),
                success=False,
                error=str(e),
            )

        except Exception as e:
            logger.exception(f"Unexpected error polling router {config.router_id}")
            await self._update_poll_status(
                config,
                PollStatus.ERROR,
                error=f"Unexpected error: {e}",
            )
            return DevicePollingResult(
                router_id=config.router_id,
                timestamp=datetime.now(timezone.utc),
                success=False,
                error=str(e),
            )

    async def _store_device_metric(
        self,
        router_id: int,
        result: DevicePollingResult,
    ) -> None:
        """Store device-level metrics."""
        if not result.system_info:
            return

        info = result.system_info

        # Calculate total traffic from interfaces
        total_rx = sum(iface.rx_bytes for iface in result.interfaces)
        total_tx = sum(iface.tx_bytes for iface in result.interfaces)

        metric = DeviceMetric(
            router_id=router_id,
            timestamp=result.timestamp,
            uptime_seconds=info.sys_uptime_seconds,
            cpu_percent=info.cpu_load,
            memory_percent=info.memory_percent,
            memory_used_bytes=info.memory_used,
            memory_total_bytes=info.memory_total,
            temperature=info.temperature,
            total_rx_bytes=total_rx,
            total_tx_bytes=total_tx,
            active_ppp_sessions=result.active_ppp_sessions,
            active_hotspot_sessions=result.active_hotspot_sessions,
            active_dhcp_leases=result.active_dhcp_leases,
        )

        self.db.add(metric)
        await self.db.flush()

    async def _store_interface_metrics(
        self,
        router_id: int,
        result: DevicePollingResult,
    ) -> None:
        """Store interface metrics and calculate rates."""
        if not result.interfaces:
            return

        # Get previous interface states for rate calculation
        prev_states = await self._get_previous_states(router_id)

        for iface in result.interfaces:
            # Calculate rates if we have previous data
            rx_rate = None
            tx_rate = None

            if iface.index in prev_states:
                prev = prev_states[iface.index]
                interval = (result.timestamp - prev["timestamp"]).total_seconds()

                if interval > 0:
                    # Handle counter wraps (64-bit counters)
                    rx_delta = iface.rx_bytes - prev["rx_bytes"]
                    tx_delta = iface.tx_bytes - prev["tx_bytes"]

                    if rx_delta < 0:
                        rx_delta = 0  # Counter wrapped or reset
                    if tx_delta < 0:
                        tx_delta = 0

                    # Convert bytes/sec to bits/sec
                    rx_rate = int((rx_delta * 8) / interval)
                    tx_rate = int((tx_delta * 8) / interval)

            metric = InterfaceMetric(
                router_id=router_id,
                interface_index=iface.index,
                interface_name=iface.name,
                timestamp=result.timestamp,
                rx_bytes=iface.rx_bytes,
                tx_bytes=iface.tx_bytes,
                rx_packets=iface.rx_packets,
                tx_packets=iface.tx_packets,
                rx_errors=iface.rx_errors,
                tx_errors=iface.tx_errors,
                rx_discards=iface.rx_discards,
                tx_discards=iface.tx_discards,
                rx_rate_bps=rx_rate,
                tx_rate_bps=tx_rate,
                oper_status=self._map_oper_status(iface.oper_status),
                admin_status=self._map_oper_status(iface.admin_status),
                speed_bps=iface.speed_bps,
            )

            self.db.add(metric)

        await self.db.flush()

    async def _update_interface_states(
        self,
        router_id: int,
        result: DevicePollingResult,
    ) -> None:
        """Update current interface state snapshots."""
        if not result.interfaces:
            return

        for iface in result.interfaces:
            # Check if state exists
            state = await self.db.execute(
                select(InterfaceState).where(
                    and_(
                        InterfaceState.router_id == router_id,
                        InterfaceState.interface_index == iface.index,
                    )
                )
            )
            state = state.scalar_one_or_none()

            # Detect state change
            state_changed = False
            if state:
                old_status = state.oper_status.value if state.oper_status else "unknown"
                new_status = self._map_oper_status(iface.oper_status).value
                state_changed = old_status != new_status

            if state:
                # Update existing state
                state.interface_name = iface.name
                state.interface_alias = iface.alias or None
                state.oper_status = self._map_oper_status(iface.oper_status)
                state.admin_status = self._map_oper_status(iface.admin_status)
                state.speed_bps = iface.speed_bps
                state.mtu = iface.mtu or None
                state.mac_address = iface.mac_address or None
                state.last_rx_bytes = iface.rx_bytes
                state.last_tx_bytes = iface.tx_bytes
                state.last_polled_at = result.timestamp
                if state_changed:
                    state.last_state_change_at = result.timestamp
            else:
                # Create new state
                state = InterfaceState(
                    router_id=router_id,
                    interface_index=iface.index,
                    interface_name=iface.name,
                    interface_alias=iface.alias or None,
                    oper_status=self._map_oper_status(iface.oper_status),
                    admin_status=self._map_oper_status(iface.admin_status),
                    speed_bps=iface.speed_bps,
                    mtu=iface.mtu or None,
                    mac_address=iface.mac_address or None,
                    last_rx_bytes=iface.rx_bytes,
                    last_tx_bytes=iface.tx_bytes,
                    last_polled_at=result.timestamp,
                )
                self.db.add(state)

        await self.db.flush()

    async def aggregate_hourly(self) -> RollupResult:
        """Aggregate raw metrics into hourly rollups.

        Returns:
            RollupResult with statistics
        """
        start_time = time.monotonic()
        now = datetime.now(timezone.utc)

        # Calculate the hour to aggregate (previous complete hour)
        period_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        period_end = period_start + timedelta(hours=1)

        result = RollupResult(
            aggregation=MetricAggregation.HOURLY.value,
            period_start=period_start,
        )

        # Get distinct router/interface combinations with data in this period
        stmt = (
            select(
                InterfaceMetric.router_id,
                InterfaceMetric.interface_index,
            )
            .where(
                and_(
                    InterfaceMetric.timestamp >= period_start,
                    InterfaceMetric.timestamp < period_end,
                )
            )
            .distinct()
        )
        interfaces = (await self.db.execute(stmt)).all()

        for router_id, interface_index in interfaces:
            # Get metrics for this interface in this period
            metrics_stmt = select(InterfaceMetric).where(
                and_(
                    InterfaceMetric.router_id == router_id,
                    InterfaceMetric.interface_index == interface_index,
                    InterfaceMetric.timestamp >= period_start,
                    InterfaceMetric.timestamp < period_end,
                )
            )
            metrics = (await self.db.execute(metrics_stmt)).scalars().all()

            if not metrics:
                continue

            # Calculate aggregates
            rx_rates = [m.rx_rate_bps for m in metrics if m.rx_rate_bps is not None]
            tx_rates = [m.tx_rate_bps for m in metrics if m.tx_rate_bps is not None]

            # Check if rollup already exists
            existing = await self.db.execute(
                select(InterfaceMetricRollup).where(
                    and_(
                        InterfaceMetricRollup.router_id == router_id,
                        InterfaceMetricRollup.interface_index == interface_index,
                        InterfaceMetricRollup.aggregation == MetricAggregation.HOURLY,
                        InterfaceMetricRollup.period_start == period_start,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # Already processed

            rollup = InterfaceMetricRollup(
                router_id=router_id,
                interface_index=interface_index,
                aggregation=MetricAggregation.HOURLY,
                period_start=period_start,
                avg_rx_rate_bps=int(sum(rx_rates) / len(rx_rates)) if rx_rates else 0,
                avg_tx_rate_bps=int(sum(tx_rates) / len(tx_rates)) if tx_rates else 0,
                max_rx_rate_bps=max(rx_rates) if rx_rates else 0,
                max_tx_rate_bps=max(tx_rates) if tx_rates else 0,
                min_rx_rate_bps=min(rx_rates) if rx_rates else 0,
                min_tx_rate_bps=min(tx_rates) if tx_rates else 0,
                p95_rx_rate_bps=self._percentile(rx_rates, 95) if rx_rates else 0,
                p95_tx_rate_bps=self._percentile(tx_rates, 95) if tx_rates else 0,
                total_rx_bytes=max(m.rx_bytes for m in metrics) - min(m.rx_bytes for m in metrics),
                total_tx_bytes=max(m.tx_bytes for m in metrics) - min(m.tx_bytes for m in metrics),
                total_rx_errors=sum(m.rx_errors for m in metrics),
                total_tx_errors=sum(m.tx_errors for m in metrics),
                samples_count=len(metrics),
                uptime_percent=self._calculate_uptime(metrics),
            )

            self.db.add(rollup)
            result.records_created += 1
            result.interfaces_processed += 1

        await self.db.commit()
        result.duration_seconds = time.monotonic() - start_time

        logger.info(
            "Hourly aggregation complete",
            extra={
                "period": period_start.isoformat(),
                "records": result.records_created,
            },
        )

        return result

    async def cleanup_old_metrics(self) -> CleanupResult:
        """Delete old raw metrics based on retention policy.

        Returns:
            CleanupResult with statistics
        """
        start_time = time.monotonic()
        result = CleanupResult()

        now = datetime.now(timezone.utc)

        # Delete old device metrics
        cutoff = now - timedelta(days=self.RAW_RETENTION_DAYS)
        stmt = DeviceMetric.__table__.delete().where(
            DeviceMetric.timestamp < cutoff
        )
        device_result = await self.db.execute(stmt)
        result.deleted_device_metrics = device_result.rowcount

        # Delete old interface metrics
        stmt = InterfaceMetric.__table__.delete().where(
            InterfaceMetric.timestamp < cutoff
        )
        iface_result = await self.db.execute(stmt)
        result.deleted_interface_metrics = iface_result.rowcount

        # Delete old hourly rollups
        hourly_cutoff = now - timedelta(days=self.HOURLY_RETENTION_DAYS)
        stmt = InterfaceMetricRollup.__table__.delete().where(
            and_(
                InterfaceMetricRollup.aggregation == MetricAggregation.HOURLY,
                InterfaceMetricRollup.period_start < hourly_cutoff,
            )
        )
        await self.db.execute(stmt)

        await self.db.commit()
        result.duration_seconds = time.monotonic() - start_time

        logger.info(
            "Metrics cleanup complete",
            extra={
                "device_metrics_deleted": result.deleted_device_metrics,
                "interface_metrics_deleted": result.deleted_interface_metrics,
            },
        )

        return result

    async def get_poll_statistics(self) -> PollStatistics:
        """Get polling statistics for monitoring.

        Returns:
            PollStatistics with overview data
        """
        stats = PollStatistics()

        # Count configs
        total = await self.db.execute(select(func.count(SNMPPollingConfig.id)))
        stats.total_configs = total.scalar() or 0

        enabled = await self.db.execute(
            select(func.count(SNMPPollingConfig.id)).where(
                SNMPPollingConfig.is_enabled == True  # noqa: E712
            )
        )
        stats.enabled_configs = enabled.scalar() or 0

        # Count successes/failures in last 24h
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        success_count = await self.db.execute(
            select(func.count(SNMPPollingConfig.id)).where(
                and_(
                    SNMPPollingConfig.last_poll_status == PollStatus.SUCCESS,
                    SNMPPollingConfig.last_polled_at >= cutoff,
                )
            )
        )
        stats.successful_polls_24h = success_count.scalar() or 0

        failed_count = await self.db.execute(
            select(func.count(SNMPPollingConfig.id)).where(
                and_(
                    SNMPPollingConfig.last_poll_status != PollStatus.SUCCESS,
                    SNMPPollingConfig.last_poll_status.isnot(None),
                    SNMPPollingConfig.last_polled_at >= cutoff,
                )
            )
        )
        stats.failed_polls_24h = failed_count.scalar() or 0

        # Get routers with consecutive failures
        errors_stmt = select(SNMPPollingConfig.router_id).where(
            SNMPPollingConfig.consecutive_failures >= 3
        )
        error_routers = (await self.db.execute(errors_stmt)).scalars().all()
        stats.routers_with_errors = list(error_routers)

        return stats

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_enabled_configs(self) -> List[SNMPPollingConfig]:
        """Get all enabled SNMP polling configs."""
        stmt = select(SNMPPollingConfig).where(
            SNMPPollingConfig.is_enabled == True  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_config(self, router_id: int) -> Optional[SNMPPollingConfig]:
        """Get SNMP config for a router."""
        stmt = select(SNMPPollingConfig).where(
            SNMPPollingConfig.router_id == router_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_poll_status(
        self,
        config: SNMPPollingConfig,
        status: PollStatus,
        error: Optional[str] = None,
    ) -> None:
        """Update polling status on config."""
        config.last_polled_at = datetime.now(timezone.utc)
        config.last_poll_status = status
        config.last_poll_error = error

        if status == PollStatus.SUCCESS:
            config.consecutive_failures = 0
        else:
            config.consecutive_failures += 1

        await self.db.flush()

    async def _get_previous_states(
        self,
        router_id: int,
    ) -> Dict[int, Dict]:
        """Get previous interface states for rate calculation."""
        stmt = select(InterfaceState).where(
            InterfaceState.router_id == router_id
        )
        result = await self.db.execute(stmt)
        states = result.scalars().all()

        return {
            s.interface_index: {
                "rx_bytes": s.last_rx_bytes,
                "tx_bytes": s.last_tx_bytes,
                "timestamp": s.last_polled_at,
            }
            for s in states
        }

    def _map_oper_status(self, status: int) -> InterfaceOperStatus:
        """Map SNMP ifOperStatus to enum."""
        mapping = {
            1: InterfaceOperStatus.UP,
            2: InterfaceOperStatus.DOWN,
            3: InterfaceOperStatus.TESTING,
            4: InterfaceOperStatus.UNKNOWN,
            5: InterfaceOperStatus.DORMANT,
            6: InterfaceOperStatus.NOT_PRESENT,
            7: InterfaceOperStatus.LOWER_LAYER_DOWN,
        }
        return mapping.get(status, InterfaceOperStatus.UNKNOWN)

    def _error_to_status(self, error: Optional[str]) -> PollStatus:
        """Map error message to poll status."""
        if not error:
            return PollStatus.ERROR

        error_lower = error.lower()
        if "timeout" in error_lower:
            return PollStatus.TIMEOUT
        if "authentication" in error_lower or "auth" in error_lower:
            return PollStatus.AUTH_ERROR
        if "unreachable" in error_lower or "connection" in error_lower:
            return PollStatus.UNREACHABLE

        return PollStatus.ERROR

    def _percentile(self, data: List[int], percentile: int) -> int:
        """Calculate percentile of a list."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _calculate_uptime(self, metrics: List[InterfaceMetric]) -> float:
        """Calculate uptime percentage from metrics."""
        if not metrics:
            return 100.0

        up_count = sum(
            1 for m in metrics
            if m.oper_status == InterfaceOperStatus.UP
        )
        return (up_count / len(metrics)) * 100.0
