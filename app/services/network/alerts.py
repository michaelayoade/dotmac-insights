"""Alert Service.

Handles alert evaluation, creation, acknowledgement, and resolution.
Integrates with the notification system for alerting.

Usage:
    async with async_session_maker() as db:
        service = AlertService(db)

        # Evaluate device metrics against rules
        result = await service.evaluate_device_metrics(device_check)

        # Acknowledge an alert
        await service.acknowledge_alert(alert_id, employee_id, note)

        # Resolve an alert
        await service.resolve_alert(alert_id, employee_id, note, auto=False)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import and_, or_, select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alerts import (
    Alert,
    AlertRule,
    AlertEscalation,
    AlertSuppression,
    AlertType,
    AlertSeverity,
    AlertStatus,
)
from app.models.notification import NotificationEventType
from app.services.network.alert_types import (
    AlertCreateData,
    AlertEvaluationResult,
    AlertFilters,
    AlertStats,
    AlertRuleFilters,
    DeviceAlertCheck,
    InterfaceAlertCheck,
    SuppressionCheck,
    AlertNotificationRequest,
    AlertNotificationResult,
    AlertBatchResult,
)

if TYPE_CHECKING:
    from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing network alerts."""

    def __init__(self, db: AsyncSession, event_bus: Optional["EventBus"] = None):
        """Initialize the alert service.

        Args:
            db: Async database session
            event_bus: Optional event bus for publishing notifications
        """
        self.db = db
        self.event_bus = event_bus

    # =========================================================================
    # Alert CRUD Operations
    # =========================================================================

    async def create_alert(self, data: AlertCreateData) -> Alert:
        """Create a new alert.

        Args:
            data: Alert creation data

        Returns:
            Created Alert instance
        """
        now = datetime.now(timezone.utc)
        alert = Alert(
            rule_id=data.rule_id,
            alert_type=data.alert_type,
            severity=data.severity,
            status=AlertStatus.ACTIVE.value,
            router_id=data.router_id,
            pop_id=data.pop_id,
            interface_index=data.interface_index,
            interface_name=data.interface_name,
            title=data.title,
            message=data.message,
            metric_name=data.metric_name,
            metric_value=data.metric_value,
            threshold_value=data.threshold_value,
            triggered_at=now,
            first_occurrence_at=now,
            last_occurrence_at=now,
            occurrence_count=1,
            extra_data=data.extra_data,
        )
        self.db.add(alert)
        await self.db.flush()

        logger.info(
            "alert_created",
            alert_id=alert.id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            router_id=alert.router_id,
        )

        # Publish notification event if event bus available
        if self.event_bus:
            await self._publish_alert_event(alert, NotificationEventType.ALERT_TRIGGERED)

        return alert

    async def get_alert(self, alert_id: int) -> Optional[Alert]:
        """Get an alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert instance or None
        """
        result = await self.db.execute(
            select(Alert)
            .options(selectinload(Alert.rule))
            .where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def list_alerts(
        self,
        filters: Optional[AlertFilters] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Alert]:
        """List alerts with optional filters.

        Args:
            filters: Optional filter criteria
            limit: Max results to return
            offset: Result offset

        Returns:
            List of Alert instances
        """
        query = select(Alert).order_by(desc(Alert.triggered_at))

        if filters:
            conditions = []
            if filters.status:
                conditions.append(Alert.status == filters.status)
            if filters.statuses:
                conditions.append(Alert.status.in_(filters.statuses))
            if filters.severity:
                conditions.append(Alert.severity == filters.severity)
            if filters.severities:
                conditions.append(Alert.severity.in_(filters.severities))
            if filters.alert_type:
                conditions.append(Alert.alert_type == filters.alert_type)
            if filters.router_id:
                conditions.append(Alert.router_id == filters.router_id)
            if filters.pop_id:
                conditions.append(Alert.pop_id == filters.pop_id)
            if filters.incident_id:
                conditions.append(Alert.incident_id == filters.incident_id)
            if filters.acknowledged is not None:
                if filters.acknowledged:
                    conditions.append(Alert.acknowledged_at.isnot(None))
                else:
                    conditions.append(Alert.acknowledged_at.is_(None))
            if filters.auto_resolved is not None:
                conditions.append(Alert.auto_resolved == filters.auto_resolved)
            if filters.triggered_after:
                conditions.append(Alert.triggered_at >= filters.triggered_after)
            if filters.triggered_before:
                conditions.append(Alert.triggered_at <= filters.triggered_before)

            if conditions:
                query = query.where(and_(*conditions))

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_alerts(self, filters: Optional[AlertFilters] = None) -> int:
        """Count alerts with optional filters.

        Args:
            filters: Optional filter criteria

        Returns:
            Alert count
        """
        query = select(func.count(Alert.id))

        if filters:
            conditions = []
            if filters.status:
                conditions.append(Alert.status == filters.status)
            if filters.statuses:
                conditions.append(Alert.status.in_(filters.statuses))
            if filters.severity:
                conditions.append(Alert.severity == filters.severity)
            if filters.router_id:
                conditions.append(Alert.router_id == filters.router_id)

            if conditions:
                query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        return result.scalar() or 0

    # =========================================================================
    # Alert Lifecycle Management
    # =========================================================================

    async def acknowledge_alert(
        self,
        alert_id: int,
        employee_id: int,
        note: Optional[str] = None,
    ) -> Optional[Alert]:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID
            employee_id: ID of employee acknowledging
            note: Optional acknowledgement note

        Returns:
            Updated Alert or None if not found
        """
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        if alert.status == AlertStatus.RESOLVED.value:
            logger.warning("alert_already_resolved", alert_id=alert_id)
            return alert

        now = datetime.now(timezone.utc)
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = now
        alert.acknowledged_by_id = employee_id
        alert.acknowledgement_note = note

        await self.db.flush()

        logger.info(
            "alert_acknowledged",
            alert_id=alert_id,
            employee_id=employee_id,
        )

        if self.event_bus:
            await self._publish_alert_event(alert, NotificationEventType.ALERT_ACKNOWLEDGED)

        return alert

    async def resolve_alert(
        self,
        alert_id: int,
        employee_id: Optional[int] = None,
        note: Optional[str] = None,
        auto: bool = False,
    ) -> Optional[Alert]:
        """Resolve an alert.

        Args:
            alert_id: Alert ID
            employee_id: ID of employee resolving (None if auto)
            note: Optional resolution note
            auto: Whether this is auto-resolution

        Returns:
            Updated Alert or None if not found
        """
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        if alert.status == AlertStatus.RESOLVED.value:
            return alert

        now = datetime.now(timezone.utc)
        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = now
        alert.resolved_by_id = employee_id
        alert.resolution_note = note
        alert.auto_resolved = auto

        await self.db.flush()

        logger.info(
            "alert_resolved",
            alert_id=alert_id,
            auto=auto,
            duration_seconds=alert.duration_seconds,
        )

        if self.event_bus:
            await self._publish_alert_event(alert, NotificationEventType.ALERT_RESOLVED)

        return alert

    async def suppress_alert(
        self,
        alert_id: int,
        until: datetime,
        reason: str,
    ) -> Optional[Alert]:
        """Suppress an alert until a specified time.

        Args:
            alert_id: Alert ID
            until: Suppress until this time
            reason: Reason for suppression

        Returns:
            Updated Alert or None if not found
        """
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.SUPPRESSED.value
        alert.suppressed_until = until
        alert.suppression_reason = reason

        await self.db.flush()

        logger.info(
            "alert_suppressed",
            alert_id=alert_id,
            until=until.isoformat(),
        )

        return alert

    async def update_occurrence(self, alert_id: int) -> Optional[Alert]:
        """Update an alert's occurrence count and last occurrence time.

        Used when an alert condition continues to fire.

        Args:
            alert_id: Alert ID

        Returns:
            Updated Alert or None if not found
        """
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        alert.occurrence_count += 1
        alert.last_occurrence_at = datetime.now(timezone.utc)

        await self.db.flush()
        return alert

    # =========================================================================
    # Alert Rule Management
    # =========================================================================

    async def get_active_rules(
        self,
        alert_type: Optional[str] = None,
        router_id: Optional[int] = None,
        pop_id: Optional[int] = None,
    ) -> List[AlertRule]:
        """Get active alert rules, optionally filtered.

        Args:
            alert_type: Filter by alert type
            router_id: Filter by router scope
            pop_id: Filter by POP scope

        Returns:
            List of AlertRule instances
        """
        conditions = [AlertRule.is_enabled == True]

        if alert_type:
            conditions.append(AlertRule.alert_type == alert_type)

        # Scope filtering: include global rules + scoped rules
        if router_id is not None or pop_id is not None:
            scope_conditions = [
                and_(AlertRule.router_id.is_(None), AlertRule.pop_id.is_(None))  # Global
            ]
            if router_id:
                scope_conditions.append(AlertRule.router_id == router_id)
            if pop_id:
                scope_conditions.append(AlertRule.pop_id == pop_id)
            conditions.append(or_(*scope_conditions))

        query = select(AlertRule).where(and_(*conditions))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_rule(
        self,
        name: str,
        alert_type: str,
        threshold_value: float,
        threshold_operator: str = "gt",
        severity: str = "warning",
        router_id: Optional[int] = None,
        pop_id: Optional[int] = None,
        threshold_duration_seconds: int = 0,
        cooldown_seconds: int = 300,
        notification_config: Optional[Dict] = None,
        created_by_id: Optional[int] = None,
    ) -> AlertRule:
        """Create a new alert rule.

        Args:
            name: Rule name
            alert_type: Type of alert
            threshold_value: Threshold value
            threshold_operator: Comparison operator (gt, lt, gte, lte, eq, ne)
            severity: Alert severity
            router_id: Optional router scope
            pop_id: Optional POP scope
            threshold_duration_seconds: Sustained duration before alerting
            cooldown_seconds: Minimum time between repeat alerts
            notification_config: Notification settings
            created_by_id: User creating the rule

        Returns:
            Created AlertRule instance
        """
        rule = AlertRule(
            name=name,
            alert_type=alert_type,
            threshold_value=threshold_value,
            threshold_operator=threshold_operator,
            severity=severity,
            router_id=router_id,
            pop_id=pop_id,
            threshold_duration_seconds=threshold_duration_seconds,
            cooldown_seconds=cooldown_seconds,
            notification_config=notification_config,
            created_by_id=created_by_id,
        )
        self.db.add(rule)
        await self.db.flush()

        logger.info("alert_rule_created", rule_id=rule.id, name=name, alert_type=alert_type)
        return rule

    # =========================================================================
    # Alert Evaluation
    # =========================================================================

    async def evaluate_device_metrics(self, check: DeviceAlertCheck) -> AlertEvaluationResult:
        """Evaluate device metrics against alert rules.

        Args:
            check: Device metrics to check

        Returns:
            Evaluation result with triggered/resolved alerts
        """
        result = AlertEvaluationResult()

        # Get applicable rules
        rules = await self.get_active_rules(router_id=check.router_id)

        for rule in rules:
            result.evaluated_rules += 1

            # Check suppression
            suppression = await self._check_suppression(
                rule.alert_type, check.router_id, None
            )
            if suppression.is_suppressed:
                result.skipped_rules += 1
                continue

            # Check cooldown
            if await self._is_on_cooldown(rule):
                result.skipped_rules += 1
                continue

            # Evaluate based on alert type
            should_alert = False
            metric_value = None

            if rule.alert_type == AlertType.DEVICE_DOWN.value:
                should_alert = not check.is_reachable
                metric_value = 0 if not check.is_reachable else 1
            elif rule.alert_type == AlertType.DEVICE_HIGH_CPU.value and check.cpu_percent is not None:
                should_alert = rule.matches_threshold(check.cpu_percent)
                metric_value = check.cpu_percent
            elif rule.alert_type == AlertType.DEVICE_HIGH_MEMORY.value and check.memory_percent is not None:
                should_alert = rule.matches_threshold(check.memory_percent)
                metric_value = check.memory_percent
            elif rule.alert_type == AlertType.DEVICE_HIGH_TEMPERATURE.value and check.temperature is not None:
                should_alert = rule.matches_threshold(check.temperature)
                metric_value = check.temperature

            if should_alert:
                # Check for existing active alert
                existing = await self._find_existing_alert(
                    rule.alert_type, check.router_id, None
                )
                if existing:
                    await self.update_occurrence(existing.id)
                else:
                    alert_data = AlertCreateData(
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title=self._generate_title(rule.alert_type, check.router_id),
                        message=self._generate_message(rule, metric_value),
                        router_id=check.router_id,
                        metric_name=rule.alert_type,
                        metric_value=metric_value,
                        threshold_value=float(rule.threshold_value),
                        rule_id=rule.id,
                    )
                    result.triggered_alerts.append(alert_data)

        return result

    async def evaluate_interface_status(self, check: InterfaceAlertCheck) -> AlertEvaluationResult:
        """Evaluate interface status against alert rules.

        Args:
            check: Interface data to check

        Returns:
            Evaluation result with triggered/resolved alerts
        """
        result = AlertEvaluationResult()

        rules = await self.get_active_rules(router_id=check.router_id)

        for rule in rules:
            result.evaluated_rules += 1

            # Check suppression
            suppression = await self._check_suppression(
                rule.alert_type, check.router_id, None
            )
            if suppression.is_suppressed:
                result.skipped_rules += 1
                continue

            should_alert = False
            metric_value = None

            if rule.alert_type == AlertType.INTERFACE_DOWN.value:
                should_alert = check.oper_status.lower() != "up"
                metric_value = 0 if should_alert else 1
            elif rule.alert_type == AlertType.INTERFACE_ERRORS.value:
                total_errors = check.rx_errors + check.tx_errors
                should_alert = rule.matches_threshold(total_errors)
                metric_value = total_errors

            if should_alert:
                existing = await self._find_existing_alert(
                    rule.alert_type,
                    check.router_id,
                    check.interface_index,
                )
                if existing:
                    await self.update_occurrence(existing.id)
                else:
                    alert_data = AlertCreateData(
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title=f"{check.interface_name} {rule.alert_type.replace('_', ' ').title()}",
                        message=self._generate_message(rule, metric_value),
                        router_id=check.router_id,
                        interface_index=check.interface_index,
                        interface_name=check.interface_name,
                        metric_value=metric_value,
                        threshold_value=float(rule.threshold_value),
                        rule_id=rule.id,
                    )
                    result.triggered_alerts.append(alert_data)

        return result

    async def check_auto_resolve(self) -> List[int]:
        """Check for alerts that can be auto-resolved.

        Finds active alerts where the condition is no longer true.

        Returns:
            List of resolved alert IDs
        """
        # Find active device_down alerts where device is now reachable
        # This would typically be called after polling confirms device is up
        resolved_ids = []

        # Get active alerts that might be auto-resolvable
        active_alerts = await self.list_alerts(
            AlertFilters(
                statuses=[AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value],
            ),
            limit=500,
        )

        for alert in active_alerts:
            # Auto-resolve logic would check current state
            # This is a placeholder - actual implementation would query current metrics
            pass

        return resolved_ids

    # =========================================================================
    # Suppression Management
    # =========================================================================

    async def create_suppression(
        self,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        router_id: Optional[int] = None,
        pop_id: Optional[int] = None,
        alert_types: Optional[List[str]] = None,
        incident_id: Optional[int] = None,
        created_by_id: Optional[int] = None,
    ) -> AlertSuppression:
        """Create an alert suppression window.

        Args:
            starts_at: Suppression start time
            ends_at: Suppression end time
            reason: Reason for suppression
            router_id: Optional router scope
            pop_id: Optional POP scope
            alert_types: Optional list of alert types to suppress
            incident_id: Related incident ID
            created_by_id: User creating suppression

        Returns:
            Created AlertSuppression instance
        """
        suppression = AlertSuppression(
            router_id=router_id,
            pop_id=pop_id,
            alert_types=alert_types,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            incident_id=incident_id,
            created_by_id=created_by_id,
        )
        self.db.add(suppression)
        await self.db.flush()

        logger.info(
            "alert_suppression_created",
            suppression_id=suppression.id,
            starts_at=starts_at.isoformat(),
            ends_at=ends_at.isoformat(),
        )

        return suppression

    async def get_active_suppressions(self) -> List[AlertSuppression]:
        """Get currently active suppressions.

        Returns:
            List of active AlertSuppression instances
        """
        now = datetime.now(timezone.utc)
        query = select(AlertSuppression).where(
            and_(
                AlertSuppression.starts_at <= now,
                AlertSuppression.ends_at >= now,
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> AlertStats:
        """Get alert statistics.

        Returns:
            AlertStats with counts and metrics
        """
        stats = AlertStats()

        # Active count
        stats.total_active = await self.count_alerts(
            AlertFilters(status=AlertStatus.ACTIVE.value)
        )

        # Acknowledged count
        stats.total_acknowledged = await self.count_alerts(
            AlertFilters(status=AlertStatus.ACKNOWLEDGED.value)
        )

        # Resolved in last 24h
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        stats.total_resolved_24h = await self.count_alerts(
            AlertFilters(
                status=AlertStatus.RESOLVED.value,
                triggered_after=yesterday,
            )
        )

        # By severity
        for severity in AlertSeverity:
            count = await self.count_alerts(
                AlertFilters(
                    statuses=[AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value],
                    severity=severity.value,
                )
            )
            stats.by_severity[severity.value] = count

        return stats

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _check_suppression(
        self,
        alert_type: str,
        router_id: Optional[int],
        pop_id: Optional[int],
    ) -> SuppressionCheck:
        """Check if an alert would be suppressed.

        Args:
            alert_type: Type of alert
            router_id: Router ID
            pop_id: POP ID

        Returns:
            SuppressionCheck result
        """
        suppressions = await self.get_active_suppressions()

        for suppression in suppressions:
            if suppression.matches_alert(alert_type, router_id, pop_id):
                return SuppressionCheck(
                    is_suppressed=True,
                    suppression_id=suppression.id,
                    reason=suppression.reason,
                    ends_at=suppression.ends_at,
                )

        return SuppressionCheck(is_suppressed=False)

    async def _is_on_cooldown(self, rule: AlertRule) -> bool:
        """Check if a rule is on cooldown from recent alert.

        Args:
            rule: Alert rule to check

        Returns:
            True if on cooldown
        """
        cooldown_time = datetime.now(timezone.utc) - timedelta(seconds=rule.cooldown_seconds)

        query = select(func.count(Alert.id)).where(
            and_(
                Alert.rule_id == rule.id,
                Alert.triggered_at >= cooldown_time,
            )
        )
        result = await self.db.execute(query)
        count = result.scalar() or 0

        return count > 0

    async def _find_existing_alert(
        self,
        alert_type: str,
        router_id: Optional[int],
        interface_index: Optional[int],
    ) -> Optional[Alert]:
        """Find existing active alert matching criteria.

        Args:
            alert_type: Alert type
            router_id: Router ID
            interface_index: Interface index (optional)

        Returns:
            Existing Alert or None
        """
        conditions = [
            Alert.alert_type == alert_type,
            Alert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]),
        ]

        if router_id:
            conditions.append(Alert.router_id == router_id)
        if interface_index is not None:
            conditions.append(Alert.interface_index == interface_index)

        query = select(Alert).where(and_(*conditions)).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _generate_title(self, alert_type: str, router_id: Optional[int]) -> str:
        """Generate alert title.

        Args:
            alert_type: Alert type
            router_id: Router ID

        Returns:
            Generated title
        """
        type_titles = {
            AlertType.DEVICE_DOWN.value: "Device Down",
            AlertType.DEVICE_UP.value: "Device Recovered",
            AlertType.DEVICE_HIGH_CPU.value: "High CPU Usage",
            AlertType.DEVICE_HIGH_MEMORY.value: "High Memory Usage",
            AlertType.DEVICE_HIGH_TEMPERATURE.value: "High Temperature",
            AlertType.INTERFACE_DOWN.value: "Interface Down",
            AlertType.INTERFACE_UP.value: "Interface Recovered",
            AlertType.SNMP_UNREACHABLE.value: "SNMP Unreachable",
        }
        title = type_titles.get(alert_type, alert_type.replace("_", " ").title())
        if router_id:
            title = f"Router {router_id}: {title}"
        return title

    def _generate_message(self, rule: AlertRule, metric_value: Optional[float]) -> str:
        """Generate alert message.

        Args:
            rule: Alert rule
            metric_value: Actual metric value

        Returns:
            Generated message
        """
        op_text = {
            "gt": "exceeded",
            "gte": "reached or exceeded",
            "lt": "dropped below",
            "lte": "dropped to or below",
            "eq": "equals",
            "ne": "changed from",
        }.get(rule.threshold_operator, "triggered")

        if metric_value is not None:
            return (
                f"{rule.name}: Value {metric_value:.1f} {op_text} "
                f"threshold {float(rule.threshold_value):.1f}"
            )
        return f"{rule.name}: Alert condition {op_text} threshold"

    async def _publish_alert_event(
        self,
        alert: Alert,
        event_type: NotificationEventType,
    ) -> None:
        """Publish alert event to event bus.

        Args:
            alert: Alert instance
            event_type: Notification event type
        """
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                event_type=event_type.value,
                entity_type="alert",
                entity_id=alert.id,
                payload={
                    "alert_id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "status": alert.status,
                    "title": alert.title,
                    "router_id": alert.router_id,
                    "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                },
            )
        except Exception as e:
            logger.warning("alert_event_publish_failed", alert_id=alert.id, error=str(e))
